import csv
import logging
from pathlib import Path
from typing import Dict, Any
from django.db import transaction
from django.utils.dateparse import parse_datetime
from .models import Incident
from .correlate import parse_iso_datetime, run_correlation

logger = logging.getLogger("gridsignal.ingest")

def ingest_csv(file_path: str | Path) -> Dict[str, Any]:
    """
    Ingest an incident CSV file into the database.
    
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
        raise FileNotFoundError(f"CSV file not found: {path}")

    stats = {
        "status": "success",
        "file_processed": str(path.name),
        "total_rows": 0,
        "inserted_new": 0,
        "updated_conflicting": 0,
        "skipped_identical": 0,
        "skipped_malformed": 0,
        "alerts_count": 0,
    }

    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

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

            # Check if record already exists
            try:
                existing = Incident.objects.get(incident_id=incident_id)

                x_equal = (existing.x_ft == x_ft) or (existing.x_ft is None and x_ft is None)
                y_equal = (existing.y_ft == y_ft) or (existing.y_ft is None and y_ft is None)
                is_identical = (
                    existing.utility_type == utility_type and
                    existing.reported_at == dt and
                    x_equal and
                    y_equal and
                    existing.severity == severity and
                    existing.status == status and
                    existing.area == area
                )

                if is_identical:
                    logger.debug("Row %d: Identical duplicate for '%s'. Skipping.", row_idx, incident_id)
                    stats["skipped_identical"] += 1
                else:
                    logger.info("Row %d: Conflicting duplicate for '%s'. Updating record (Last-Write-Wins).", row_idx, incident_id)
                    existing.utility_type = utility_type
                    existing.reported_at = dt
                    existing.x_ft = x_ft
                    existing.y_ft = y_ft
                    existing.severity = severity
                    existing.status = status
                    existing.area = area
                    existing.save()
                    stats["updated_conflicting"] += 1

            except Incident.DoesNotExist:
                Incident.objects.create(
                    incident_id=incident_id,
                    utility_type=utility_type,
                    reported_at=dt,
                    x_ft=x_ft,
                    y_ft=y_ft,
                    severity=severity,
                    status=status,
                    area=area
                )
                stats["inserted_new"] += 1

    # Recalculate alerts
    stats["alerts_count"] = run_correlation()
    logger.info("Ingestion completed: %s", stats)
    return stats
