import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest

from app.config import MAX_DISTANCE_FT, MAX_TIME_GAP_MINUTES
from app.database import init_db, get_connection
from app.correlate import (
    calculate_planar_distance,
    calculate_time_gap_minutes,
    is_correlated,
    run_correlation,
)
from app.ingest import ingest_csv
from app.main import (
    get_health,
    get_incidents,
    get_alerts,
    get_summary,
)

# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for isolated test execution."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        db_path = tf.name
    init_db(db_path)
    conn = get_connection(db_path)
    yield conn, db_path
    conn.close()
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass

# ---------------------------------------------------------
# 1. Boundary & Mathematical Correlation Tests
# ---------------------------------------------------------

class TestBoundaryAndCorrelation:
    def test_exact_boundary_conditions(self):
        """Exact 200.0 ft and exact 360.0 min (6.0 hrs) MUST MATCH (inclusive)."""
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        t_6hr = datetime(2026, 10, 20, 6, 0, 0, tzinfo=timezone.utc)

        matches, dist, gap = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=200.0, elec_y=0.0, elec_dt=t_6hr,
        )
        assert matches is True
        assert dist == 200.0
        assert gap == 360.0

    def test_boundary_distance_just_outside(self):
        """Distance of 200.01 ft MUST NOT MATCH."""
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        matches, dist, gap = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=200.01, elec_y=0.0, elec_dt=t_base,
        )
        assert matches is False
        assert dist == 200.01

    def test_boundary_time_just_outside(self):
        """Time difference of 6 hours + 1 second (360.016 min) MUST NOT MATCH."""
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        t_just_over = datetime(2026, 10, 20, 6, 0, 1, tzinfo=timezone.utc)

        matches, dist, gap = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=0.0, elec_y=0.0, elec_dt=t_just_over,
        )
        assert matches is False
        assert gap > 360.0

    def test_missing_coordinates_never_matches(self):
        """If either x or y is NULL, it should never correlate."""
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        matches, _, _ = is_correlated(
            gas_x=None, gas_y=0.0, gas_dt=t_base,
            elec_x=0.0, elec_y=0.0, elec_dt=t_base,
        )
        assert matches is False

        matches, _, _ = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=0.0, elec_y=None, elec_dt=t_base,
        )
        assert matches is False

    def test_time_ordering_reversibility(self):
        """Symmetry check: Gas before Electric OR Electric before Gas gives same result."""
        t_gas = datetime(2026, 10, 20, 1, 0, 0, tzinfo=timezone.utc)
        t_elec = datetime(2026, 10, 20, 4, 0, 0, tzinfo=timezone.utc)
        assert calculate_time_gap_minutes(t_gas, t_elec) == 180.0
        assert calculate_time_gap_minutes(t_elec, t_gas) == 180.0

    def test_correlation_ignores_severity_status_area(self, temp_db):
        """Matching must ignore severity, status, and area fields."""
        conn, _ = temp_db
        cursor = conn.cursor()
        now = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO incidents (incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area, created_at, updated_at)
            VALUES ('G1', 'GAS', ?, 0, 0, 'LOW', 'CLOSED', 'Area-A', ?, ?),
                   ('E1', 'ELECTRIC', ?, 10, 10, 'CRITICAL', 'INVESTIGATING', 'Area-B', ?, ?)
        """, (now, now, now, now, now, now))
        conn.commit()

        count = run_correlation(conn)
        assert count == 1

    def test_one_to_many_matches(self, temp_db):
        """A single Gas incident can match multiple Electric incidents."""
        conn, _ = temp_db
        cursor = conn.cursor()
        now = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO incidents (incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area, created_at, updated_at)
            VALUES ('G-HUB', 'GAS', ?, 100, 100, 'HIGH', 'OPEN', 'Central', ?, ?),
                   ('E-NEAR1', 'ELECTRIC', ?, 105, 100, 'MEDIUM', 'OPEN', 'Central', ?, ?),
                   ('E-NEAR2', 'ELECTRIC', ?, 100, 110, 'LOW', 'OPEN', 'Central', ?, ?)
        """, (now, now, now, now, now, now, now, now, now))
        conn.commit()

        count = run_correlation(conn)
        assert count == 2

# ---------------------------------------------------------
# 2. Ingestion & Deduplication Tests
# ---------------------------------------------------------

class TestIngestionAndDeduplication:
    def test_idempotent_ingestion(self, temp_db):
        """Re-importing identical CSV must skip rows (0 duplicate writes)."""
        conn, _ = temp_db
        csv_content = """incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area
INC-1,GAS,2026-10-20T00:00:00Z,10,20,HIGH,OPEN,North
INC-2,ELECTRIC,2026-10-20T01:00:00Z,15,25,MEDIUM,OPEN,North
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f_path = f.name

        try:
            stats1 = ingest_csv(f_path, conn)
            assert stats1["inserted_new"] == 2
            assert stats1["skipped_identical"] == 0

            # Second import -> identical rows skipped
            stats2 = ingest_csv(f_path, conn)
            assert stats2["inserted_new"] == 0
            assert stats2["skipped_identical"] == 2
        finally:
            Path(f_path).unlink(missing_ok=True)

    def test_conflicting_duplicates_last_write_wins(self, temp_db):
        """Conflicting updates must update the record (Last-Write-Wins)."""
        conn, _ = temp_db
        initial_csv = "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\nINC-C,GAS,2026-10-20T00:00:00Z,10,10,LOW,OPEN,A\n"
        update_csv = "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\nINC-C,GAS,2026-10-20T00:00:00Z,99,99,CRITICAL,RESOLVED,B\n"

        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(initial_csv)
            path1 = f.name
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(update_csv)
            path2 = f.name

        try:
            ingest_csv(path1, conn)
            stats = ingest_csv(path2, conn)
            assert stats["updated_conflicting"] == 1

            cursor = conn.cursor()
            cursor.execute("SELECT x_ft, y_ft, severity, status, area FROM incidents WHERE incident_id = 'INC-C'")
            row = cursor.fetchone()
            assert row["x_ft"] == 99.0
            assert row["y_ft"] == 99.0
            assert row["severity"] == "CRITICAL"
            assert row["status"] == "RESOLVED"
            assert row["area"] == "B"
        finally:
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

    def test_malformed_timestamp_gracefully_skipped(self, temp_db):
        """Malformed timestamps must log warning, skip row, and ingest valid rows."""
        conn, _ = temp_db
        csv_content = """incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area
E-GOOD,GAS,2026-10-20T00:00:00Z,10,10,LOW,OPEN,Area
E-BAD1,ELECTRIC,invalid-date-string,10,10,LOW,OPEN,Area
E-BAD2,ELECTRIC,2026/13/45,10,10,LOW,OPEN,Area
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            p = f.name

        try:
            stats = ingest_csv(p, conn)
            assert stats["inserted_new"] == 1
            assert stats["skipped_malformed"] == 2
        finally:
            Path(p).unlink(missing_ok=True)

    def test_missing_coordinates_stored_as_null(self, temp_db):
        """Incidents with blank coordinates are saved with NULL in SQLite."""
        conn, _ = temp_db
        csv_content = "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\nNO-COORD,GAS,2026-10-20T00:00:00Z,,,LOW,OPEN,Area\n"
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            p = f.name

        try:
            ingest_csv(p, conn)
            cursor = conn.cursor()
            cursor.execute("SELECT x_ft, y_ft FROM incidents WHERE incident_id = 'NO-COORD'")
            row = cursor.fetchone()
            assert row["x_ft"] is None
            assert row["y_ft"] is None
        finally:
            Path(p).unlink(missing_ok=True)

# ---------------------------------------------------------
# 3. REST API Endpoint Tests
# ---------------------------------------------------------

class TestApiEndpoints:
    def test_get_health(self, temp_db):
        conn, _ = temp_db
        res = get_health(conn=conn)
        assert res.status == "ok"
        assert res.service == "GridSignal Mini"
        assert res.database == "connected"

    def test_get_incidents(self, temp_db):
        conn, _ = temp_db
        csv_content = """incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area
G1,GAS,2026-10-20T00:00:00Z,10,10,HIGH,OPEN,Demo
E1,ELECTRIC,2026-10-20T01:00:00Z,20,20,LOW,OPEN,Demo
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            p = f.name
        try:
            ingest_csv(p, conn)
            # All incidents
            all_inc = get_incidents(utility_type=None, conn=conn)
            assert len(all_inc) == 2

            # Filtered by GAS
            gas_inc = get_incidents(utility_type="GAS", conn=conn)
            assert len(gas_inc) == 1
            assert gas_inc[0].incident_id == "G1"

            # Filtered by ELECTRIC
            elec_inc = get_incidents(utility_type="ELECTRIC", conn=conn)
            assert len(elec_inc) == 1
            assert elec_inc[0].incident_id == "E1"
        finally:
            Path(p).unlink(missing_ok=True)

    def test_get_alerts(self, temp_db):
        conn, _ = temp_db
        csv_content = """incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area
G1,GAS,2026-10-20T00:00:00Z,0,0,HIGH,OPEN,Demo
E1,ELECTRIC,2026-10-20T01:00:00Z,50,0,MEDIUM,OPEN,Demo
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            p = f.name
        try:
            ingest_csv(p, conn)
            alerts = get_alerts(conn=conn)
            assert len(alerts) == 1
            assert alerts[0].gas_incident_id == "G1"
            assert alerts[0].electric_incident_id == "E1"
            assert alerts[0].distance_ft == 50.0
            assert alerts[0].time_gap_minutes == 60.0
        finally:
            Path(p).unlink(missing_ok=True)

    def test_get_summary(self, temp_db):
        conn, _ = temp_db
        csv_content = """incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area
G1,GAS,2026-10-20T00:00:00Z,0,0,HIGH,OPEN,Demo
E1,ELECTRIC,2026-10-20T01:00:00Z,50,0,MEDIUM,OPEN,Demo
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            p = f.name
        try:
            ingest_csv(p, conn)
            summary = get_summary(conn=conn)
            assert summary.total_incidents == 2
            assert summary.total_gas == 1
            assert summary.total_electric == 1
            assert summary.total_alerts == 1
        finally:
            Path(p).unlink(missing_ok=True)
