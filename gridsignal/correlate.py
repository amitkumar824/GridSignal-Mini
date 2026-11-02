import math
from datetime import datetime, timezone
from typing import Tuple, Optional
from django.conf import settings
from django.db import transaction
from .models import Incident, Alert

MAX_DISTANCE_FT = getattr(settings, 'MAX_DISTANCE_FT', 200.0)
MAX_TIME_GAP_MINUTES = getattr(settings, 'MAX_TIME_GAP_MINUTES', 360.0)

def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into a timezone-aware datetime."""
    clean_str = dt_str.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def calculate_planar_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean planar distance in feet: sqrt((x1-x2)^2 + (y1-y2)^2)."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

def calculate_time_gap_minutes(dt1: datetime, dt2: datetime) -> float:
    """Calculate absolute difference between two datetimes in minutes."""
    return abs((dt1 - dt2).total_seconds()) / 60.0

def is_correlated(
    gas_x: Optional[float],
    gas_y: Optional[float],
    gas_dt: datetime,
    elec_x: Optional[float],
    elec_y: Optional[float],
    elec_dt: datetime,
    max_dist: float = MAX_DISTANCE_FT,
    max_gap_min: float = MAX_TIME_GAP_MINUTES,
) -> Tuple[bool, float, float]:
    """
    Check if a GAS and ELECTRIC incident meet correlation rules.
    Returns (matches, distance_ft, time_gap_minutes).
    Missing coordinates immediately result in False.
    Boundaries are inclusive (<= max_dist and <= max_gap_min).
    """
    if gas_x is None or gas_y is None or elec_x is None or elec_y is None:
        return False, 0.0, 0.0

    dist = calculate_planar_distance(gas_x, gas_y, elec_x, elec_y)
    gap_min = calculate_time_gap_minutes(gas_dt, elec_dt)

    matches = (dist <= max_dist) and (gap_min <= max_gap_min)
    return matches, round(dist, 4), round(gap_min, 4)

def run_correlation() -> int:
    """
    Run correlation across all stored GAS and ELECTRIC incidents with coordinates.
    Idempotently populates the Alert table with unique (gas_incident, electric_incident) pairs.
    Returns the total number of alerts stored.
    """
    gas_records = list(
        Incident.objects.filter(
            utility_type=Incident.UTILITY_GAS,
            x_ft__isnull=False,
            y_ft__isnull=False
        )
    )

    elec_records = list(
        Incident.objects.filter(
            utility_type=Incident.UTILITY_ELECTRIC,
            x_ft__isnull=False,
            y_ft__isnull=False
        )
    )

    matched_alerts = []
    for g in gas_records:
        for e in elec_records:
            matches, dist, gap = is_correlated(g.x_ft, g.y_ft, g.reported_at, e.x_ft, e.y_ft, e.reported_at)
            if matches:
                matched_alerts.append(
                    Alert(
                        gas_incident=g,
                        electric_incident=e,
                        distance_ft=dist,
                        time_gap_minutes=gap
                    )
                )

    with transaction.atomic():
        Alert.objects.all().delete()
        Alert.objects.bulk_create(matched_alerts)

    return len(matched_alerts)
