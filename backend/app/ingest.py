import csv
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure backend root is on sys.path for direct script execution
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

import app.config as config
from app.correlate import parse_iso_datetime, run_correlation
from app.database import get_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gridsignal.ingest")

def ingest_csv(
    file_path: str | Path,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[str | Path] = None
) -> Dict[str, Any]:
    """
    Ingest an incident CSV file into SQLite.
    
    Conflict & Deduplication Policy:
    1. Identical duplicate (same incident_id and matching attributes):
       Ignored as a no-op; database is untouched.
    2. Conflicting duplicate (same incident_id, differing attributes):
       Last-Write-Wins policy. The existing incident record is updated with 
       the incoming batch attributes, reflecting the latest operational telemetry.
    3. Malformed timestamps:
       Logged with a WARNING and skipped without crashing the import batch.
    4. Missing coordinates:
       Stored with NULL (None) x_ft/y_ft; displayed in inventory but omitted from correlation.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    close_conn = False
    if conn is None:
        init_db(db_path)
        conn = get_connection(db_path)
        close_conn = True

    stats = {
        "file_processed": str(path.name),
        "total_rows": 0,
        "inserted_new": 0,
        "updated_conflicting": 0,
        "skipped_identical": 0,
        "skipped_malformed": 0,
        "alerts_count": 0
    }

    try:
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            cursor = conn.cursor()

            for row_idx, row in enumerate(reader, start=1):
                stats["total_rows"] += 1
                incident_id = (row.get("incident_id") or "").strip()
                utility_type = (row.get("utility_type") or "").strip().upper()
                reported_at_raw = (row.get("reported_at") or "").strip()
                severity = (row.get("severity") or "").strip().upper()
                status = (row.get("status") or "").strip().upper()
                area = (row.get("area") or "").strip() or None

                if not incident_id:
                    logger.warning("Row %d: Missing incident_id. Skipping.", row_idx)
                    stats["skipped_malformed"] += 1
                    continue

                # Validate reported_at timestamp
                try:
                    dt = parse_iso_datetime(reported_at_raw)
                    reported_at_iso = dt.isoformat()
                except Exception as ex:
                    logger.warning(
                        "Row %d: Skipping incident '%s' due to malformed timestamp '%s': %s",
                        row_idx, incident_id, reported_at_raw, ex
                    )
                    stats["skipped_malformed"] += 1
                    continue

                # Parse coordinates (may be blank/missing)
                x_raw = (row.get("x_ft") or "").strip()
                y_raw = (row.get("y_ft") or "").strip()
                x_ft = float(x_raw) if x_raw else None
                y_ft = float(y_raw) if y_raw else None

                # Check for existing record
                cursor.execute("""
                    SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
                    FROM incidents
                    WHERE incident_id = ?
                """, (incident_id,))
                existing = cursor.fetchone()

                if existing:
                    # Compare for identical vs conflicting duplicate
                    # Notice float comparison with None handling
                    x_equal = (existing["x_ft"] == x_ft) or (existing["x_ft"] is None and x_ft is None)
                    y_equal = (existing["y_ft"] == y_ft) or (existing["y_ft"] is None and y_ft is None)
                    is_identical = (
                        existing["utility_type"] == utility_type and
                        existing["reported_at"] == reported_at_iso and
                        x_equal and
                        y_equal and
                        existing["severity"] == severity and
                        existing["status"] == status and
                        existing["area"] == area
                    )

                    if is_identical:
                        logger.debug("Row %d: Identical duplicate for '%s'. Skipping.", row_idx, incident_id)
                        stats["skipped_identical"] += 1
                    else:
                        logger.info(
                            "Row %d: Conflicting duplicate for '%s'. Updating record (Last-Write-Wins policy).",
                            row_idx, incident_id
                        )
                        cursor.execute("""
                            UPDATE incidents
                            SET utility_type = ?, reported_at = ?, x_ft = ?, y_ft = ?,
                                severity = ?, status = ?, area = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE incident_id = ?
                        """, (utility_type, reported_at_iso, x_ft, y_ft, severity, status, area, incident_id))
                        stats["updated_conflicting"] += 1
                else:
                    cursor.execute("""
                        INSERT INTO incidents (
                            incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (incident_id, utility_type, reported_at_iso, x_ft, y_ft, severity, status, area))
                    stats["inserted_new"] += 1

            conn.commit()

        # Recalculate alerts
        stats["alerts_count"] = run_correlation(conn)

    finally:
        if close_conn:
            conn.close()

    logger.info("Ingestion completed: %s", stats)
    return stats

def main():
    target_csv = sys.argv[1] if len(sys.argv) > 1 else config.SEED_CSV_PATH
    logger.info("Starting ingest CLI with target file: %s", target_csv)
    stats = ingest_csv(target_csv)
    print("\n--- INGESTION SUMMARY ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
