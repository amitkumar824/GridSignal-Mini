import pytest
from pathlib import Path
from app.ingest import ingest_csv
from app.config import SEED_CSV_PATH, REPLAY_CSV_PATH

def test_idempotent_ingestion(db_conn):
    """
    Acceptance Check:
    1. Import seed CSV into SQLite.
    2. Re-importing must not duplicate incident IDs.
    3. Run the same import again; counts and pairs must remain unchanged.
    """
    stats1 = ingest_csv(SEED_CSV_PATH, conn=db_conn)
    assert stats1["total_rows"] == 11
    assert stats1["inserted_new"] == 11
    assert stats1["alerts_count"] == 6

    # Verify counts in DB
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM incidents;")
    assert cursor.fetchone()["c"] == 11
    cursor.execute("SELECT COUNT(*) AS c FROM alerts;")
    assert cursor.fetchone()["c"] == 6

    # Re-import same seed CSV
    stats2 = ingest_csv(SEED_CSV_PATH, conn=db_conn)
    assert stats2["total_rows"] == 11
    assert stats2["inserted_new"] == 0
    assert stats2["skipped_identical"] == 11
    assert stats2["alerts_count"] == 6

    # Verify counts remain strictly unchanged
    cursor.execute("SELECT COUNT(*) AS c FROM incidents;")
    assert cursor.fetchone()["c"] == 11
    cursor.execute("SELECT COUNT(*) AS c FROM alerts;")
    assert cursor.fetchone()["c"] == 6

def test_malformed_timestamp_handled_gracefully(db_conn, tmp_path):
    """
    Acceptance Check:
    Skip malformed timestamps with a logged warning, without crashing the entire import.
    """
    csv_file = tmp_path / "test_malformed.csv"
    csv_file.write_text(
        "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n"
        "G-VALID1,GAS,2026-10-20T00:00:00Z,0,0,HIGH,OPEN,Demo\n"
        "E-MALFORMED1,ELECTRIC,not-a-valid-timestamp,200,0,MEDIUM,OPEN,Demo\n"
        "E-MALFORMED2,ELECTRIC,2026-99-99T99:99:99Z,200,0,MEDIUM,OPEN,Demo\n"
        "E-VALID2,ELECTRIC,2026-10-20T02:00:00Z,50,0,LOW,OPEN,Demo\n"
    )

    stats = ingest_csv(csv_file, conn=db_conn)
    assert stats["total_rows"] == 4
    assert stats["inserted_new"] == 2
    assert stats["skipped_malformed"] == 2

    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM incidents;")
    assert cursor.fetchone()["c"] == 2

    # Verify that the two valid incidents (G-VALID1 and E-VALID2) matched
    cursor.execute("SELECT COUNT(*) AS c FROM alerts;")
    assert cursor.fetchone()["c"] == 1

def test_conflicting_duplicates_last_write_wins(db_conn, tmp_path):
    """
    Acceptance Check:
    Choose and document a policy for conflicting duplicates.
    Policy: Last-Write-Wins (updates existing record with new batch values).
    """
    batch1 = tmp_path / "batch1.csv"
    batch1.write_text(
        "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n"
        "G-100,GAS,2026-10-20T00:00:00Z,0,0,MEDIUM,OPEN,Sector-1\n"
    )
    ingest_csv(batch1, conn=db_conn)

    cursor = db_conn.cursor()
    cursor.execute("SELECT severity, status, area FROM incidents WHERE incident_id = 'G-100'")
    row1 = cursor.fetchone()
    assert row1["severity"] == "MEDIUM"
    assert row1["status"] == "OPEN"

    # Conflicting duplicate: same incident_id, updated status and severity
    batch2 = tmp_path / "batch2.csv"
    batch2.write_text(
        "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n"
        "G-100,GAS,2026-10-20T00:00:00Z,0,0,CRITICAL,RESOLVED,Sector-1-Updated\n"
    )
    stats2 = ingest_csv(batch2, conn=db_conn)
    assert stats2["inserted_new"] == 0
    assert stats2["updated_conflicting"] == 1

    # Total incidents count must remain 1 (no duplicate IDs)
    cursor.execute("SELECT COUNT(*) AS c FROM incidents;")
    assert cursor.fetchone()["c"] == 1

    cursor.execute("SELECT severity, status, area FROM incidents WHERE incident_id = 'G-100'")
    row2 = cursor.fetchone()
    assert row2["severity"] == "CRITICAL"
    assert row2["status"] == "RESOLVED"
    assert row2["area"] == "Sector-1-Updated"

def test_missing_coordinates_stored_with_nulls(db_conn, tmp_path):
    """
    Acceptance Check:
    Incidents with missing coordinates must be stored and displayed, but never matched.
    """
    csv_file = tmp_path / "missing_coords.csv"
    csv_file.write_text(
        "incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n"
        "G-NULL,GAS,2026-10-20T00:00:00Z,,,HIGH,OPEN,Demo\n"
        "E-VALID,ELECTRIC,2026-10-20T01:00:00Z,0,0,MEDIUM,OPEN,Demo\n"
    )
    ingest_csv(csv_file, conn=db_conn)

    cursor = db_conn.cursor()
    cursor.execute("SELECT x_ft, y_ft FROM incidents WHERE incident_id = 'G-NULL'")
    row = cursor.fetchone()
    assert row["x_ft"] is None
    assert row["y_ft"] is None

    cursor.execute("SELECT COUNT(*) AS c FROM alerts;")
    assert cursor.fetchone()["c"] == 0

def test_replay_batch_integration(db_conn):
    """
    Acceptance Check:
    Import the replay batch; valid new incidents should be included and malformed input handled
    without crashing the entire import.
    """
    # First import seed
    ingest_csv(SEED_CSV_PATH, conn=db_conn)

    # Then import replay batch containing duplicates, malformed timestamps, and new events
    stats = ingest_csv(REPLAY_CSV_PATH, conn=db_conn)

    assert stats["skipped_identical"] >= 2  # G-X1, E-X1
    assert stats["updated_conflicting"] >= 1  # G-X2
    assert stats["skipped_malformed"] >= 2  # BAD-TS1, BAD-TS2
    assert stats["inserted_new"] >= 3  # E-X8, G-X5, E-X9, E-X10

    # Total incidents must have grown by exactly inserted_new
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM incidents;")
    total = cursor.fetchone()["c"]
    assert total == 11 + stats["inserted_new"]

