import csv
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from .database import get_connection
from .correlate import run_correlation

logger = logging.getLogger("gridsignal.ingest")

def parse_iso_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse standard ISO-8601 string into timezone-aware UTC datetime."""
    if not ts_str or not ts_str.strip():
        return None
    cleaned = ts_str.strip()
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Malformed timestamp '{ts_str}': {e}")
        return None

def parse_coordinate(val: Any) -> Optional[float]:
    """Parse coordinate string into float, returning None if empty or invalid."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == 'null' or s.lower() == 'none':
        return None
    try:
        return float(s)
    except ValueError:
        return None

def ingest_csv(csv_path: Path | str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """
    Ingest an incident CSV file into SQLite:
    - Identical duplicates are skipped (0 redundant writes).
    - Conflicting duplicates use Last-Write-Wins (LWW).
    - Malformed timestamps are skipped with logged warnings.
    - Re-evaluates alerts atomically upon completion.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    stats = {
        "status": "success",
        "file_processed": path.name,
        "total_rows": 0,
        "inserted_new": 0,
        "updated_conflicting": 0,
        "skipped_identical": 0,
        "skipped_malformed": 0,
        "alerts_count": 0,
    }

    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            row_idx = 1
            for row in reader:
                row_idx += 1
                stats["total_rows"] += 1

                incident_id = row.get("incident_id", "").strip()
                utility_type = row.get("utility_type", "").strip().upper()
                raw_reported = row.get("reported_at", "").strip()

                if not incident_id or not utility_type:
                    continue

                dt = parse_iso_timestamp(raw_reported)
                if dt is None:
                    print(f"Row {row_idx}: Skipping incident '{incident_id}' due to malformed timestamp '{raw_reported}'")
                    stats["skipped_malformed"] += 1
                    continue

                reported_at_iso = dt.isoformat()
                x_ft = parse_coordinate(row.get("x_ft"))
                y_ft = parse_coordinate(row.get("y_ft"))
                severity = (row.get("severity") or "MEDIUM").strip().upper()
                status = (row.get("status") or "OPEN").strip().upper()
                area = (row.get("area") or "").strip() or None

                # Check if incident already exists
                cursor.execute("""
                    SELECT utility_type, reported_at, x_ft, y_ft, severity, status, area
                    FROM incidents WHERE incident_id = ?
                """, (incident_id,))
                existing = cursor.fetchone()

                if existing is not None:
                    # Compare fields to check if identical
                    same_utility = existing["utility_type"] == utility_type
                    same_reported = existing["reported_at"] == reported_at_iso
                    same_x = (existing["x_ft"] is None and x_ft is None) or (existing["x_ft"] is not None and x_ft is not None and abs(existing["x_ft"] - x_ft) < 1e-6)
                    same_y = (existing["y_ft"] is None and y_ft is None) or (existing["y_ft"] is not None and y_ft is not None and abs(existing["y_ft"] - y_ft) < 1e-6)
                    same_sev = (existing["severity"] or "").upper() == severity
                    same_stat = (existing["status"] or "").upper() == status
                    same_area = (existing["area"] or "") == (area or "")

                    if same_utility and same_reported and same_x and same_y and same_sev and same_stat and same_area:
                        stats["skipped_identical"] += 1
                        continue
                    else:
                        # Conflicting duplicate -> Last-Write-Wins (LWW)
                        cursor.execute("""
                            UPDATE incidents
                            SET utility_type = ?, reported_at = ?, x_ft = ?, y_ft = ?,
                                severity = ?, status = ?, area = ?, updated_at = ?
                            WHERE incident_id = ?
                        """, (utility_type, reported_at_iso, x_ft, y_ft, severity, status, area, now_iso, incident_id))
                        stats["updated_conflicting"] += 1
                else:
                    # Insert new incident
                    cursor.execute("""
                        INSERT INTO incidents (incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (incident_id, utility_type, reported_at_iso, x_ft, y_ft, severity, status, area, now_iso, now_iso))
                    stats["inserted_new"] += 1

        conn.commit()
        # Trigger re-correlation across all incidents
        stats["alerts_count"] = run_correlation(conn)

    finally:
        if close_conn:
            conn.close()

    return stats
