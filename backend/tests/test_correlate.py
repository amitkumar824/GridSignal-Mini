import pytest
from datetime import datetime, timezone
from app.correlate import (
    is_correlated,
    calculate_planar_distance,
    calculate_time_gap_minutes,
    parse_iso_datetime,
    run_correlation
)

def test_exact_boundary_conditions():
    """
    Specification: A GAS and ELECTRIC incident match if planar distance <= 200 ft
    AND absolute reporting-time difference <= 6 hours (360 min). Both boundaries inclusive.
    """
    t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_6hr = datetime(2026, 10, 20, 6, 0, 0, tzinfo=timezone.utc)  # exactly 360.0 minutes

    # 1. Exactly 200 ft, exactly 6 hours (360 min) -> MATCH
    matches, dist, gap = is_correlated(
        gas_x=0.0, gas_y=0.0, gas_dt=t_base,
        elec_x=200.0, elec_y=0.0, elec_dt=t_6hr
    )
    assert matches is True
    assert dist == 200.0
    assert gap == 360.0

def test_boundary_distance_just_outside():
    """Planar distance just beyond 200 ft (e.g. 200.01 ft) must NOT match."""
    t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_1hr = datetime(2026, 10, 20, 1, 0, 0, tzinfo=timezone.utc)

    matches, dist, gap = is_correlated(
        gas_x=1000.0, gas_y=1000.0, gas_dt=t_base,
        elec_x=1200.01, elec_y=1000.0, elec_dt=t_1hr
    )
    assert matches is False
    assert dist == 200.01
    assert gap == 60.0

def test_boundary_time_just_outside():
    """Time gap just beyond 6 hours (e.g. 360.1 minutes) must NOT match."""
    t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
    t_over = datetime(2026, 10, 20, 6, 0, 1, tzinfo=timezone.utc)  # 360 minutes and 1 second

    matches, dist, gap = is_correlated(
        gas_x=0.0, gas_y=0.0, gas_dt=t_base,
        elec_x=0.0, elec_y=0.0, elec_dt=t_over
    )
    assert matches is False
    assert dist == 0.0
    assert gap > 360.0

def test_missing_coordinates_never_matches():
    """Incidents with missing coordinates can be stored but must never match."""
    t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)

    # Missing electric coordinates
    matches1, _, _ = is_correlated(
        gas_x=100.0, gas_y=100.0, gas_dt=t_base,
        elec_x=None, elec_y=None, elec_dt=t_base
    )
    assert matches1 is False

    # Missing gas coordinates
    matches2, _, _ = is_correlated(
        gas_x=None, gas_y=None, gas_dt=t_base,
        elec_x=100.0, elec_y=100.0, elec_dt=t_base
    )
    assert matches2 is False

    # Partially missing coordinates (x present, y missing)
    matches3, _, _ = is_correlated(
        gas_x=100.0, gas_y=100.0, gas_dt=t_base,
        elec_x=100.0, elec_y=None, elec_dt=t_base
    )
    assert matches3 is False

def test_time_ordering_reversibility():
    """Earlier report can be either GAS or ELECTRIC (absolute time difference)."""
    t_early = datetime(2026, 10, 20, 2, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 10, 20, 4, 30, 0, tzinfo=timezone.utc)

    # Gas earlier than Electric
    m1, _, gap1 = is_correlated(0, 0, t_early, 50, 0, t_late)
    assert m1 is True
    assert gap1 == 150.0

    # Electric earlier than Gas
    m2, _, gap2 = is_correlated(0, 0, t_late, 50, 0, t_early)
    assert m2 is True
    assert gap2 == 150.0

def test_correlation_ignores_severity_status_area(db_conn):
    """Specification: Do not filter pairs by area, severity, or OPEN/CLOSED status."""
    cursor = db_conn.cursor()
    cursor.execute("""
        INSERT INTO incidents (incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area)
        VALUES 
            ('G-TEST1', 'GAS', '2026-10-20T00:00:00Z', 10, 10, 'LOW', 'CLOSED', 'Sector-A'),
            ('E-TEST1', 'ELECTRIC', '2026-10-20T01:00:00Z', 20, 20, 'CRITICAL', 'OPEN', 'Sector-Z');
    """)
    db_conn.commit()

    alert_count = run_correlation(db_conn)
    assert alert_count == 1

    cursor.execute("SELECT gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes FROM alerts")
    row = cursor.fetchone()
    assert row["gas_incident_id"] == "G-TEST1"
    assert row["electric_incident_id"] == "E-TEST1"
    assert round(row["distance_ft"], 2) == 14.14
    assert row["time_gap_minutes"] == 60.0

def test_one_to_many_matches(db_conn):
    """A single incident may match multiple opposite-type incidents."""
    cursor = db_conn.cursor()
    cursor.execute("""
        INSERT INTO incidents (incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area)
        VALUES 
            ('G-HUB', 'GAS', '2026-10-20T00:00:00Z', 100, 100, 'HIGH', 'OPEN', 'Downtown'),
            ('E-LEAF1', 'ELECTRIC', '2026-10-20T01:00:00Z', 120, 100, 'MEDIUM', 'OPEN', 'Downtown'),
            ('E-LEAF2', 'ELECTRIC', '2026-10-20T02:00:00Z', 100, 150, 'LOW', 'OPEN', 'Downtown');
    """)
    db_conn.commit()

    alert_count = run_correlation(db_conn)
    assert alert_count == 2

