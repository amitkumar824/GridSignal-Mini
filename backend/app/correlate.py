import math
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Any, Optional
from app.config import MAX_DISTANCE_FT, MAX_TIME_GAP_MINUTES

def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into a timezone-aware datetime."""
    clean_str = dt_str.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def calculate_planar_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean planar distance in feet."""
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
    """
    if gas_x is None or gas_y is None or elec_x is None or elec_y is None:
        return False, 0.0, 0.0

    dist = calculate_planar_distance(gas_x, gas_y, elec_x, elec_y)
    gap_min = calculate_time_gap_minutes(gas_dt, elec_dt)

    # Boundaries are inclusive: dist <= 200.0 and gap_min <= 360.0
    matches = (dist <= max_dist) and (gap_min <= max_gap_min)
    return matches, round(dist, 4), round(gap_min, 4)

def run_correlation(conn: sqlite3.Connection) -> int:
    """
    Run correlation across all stored GAS and ELECTRIC incidents with coordinates.
    Idempotently populates the alerts table with unique (gas_incident_id, electric_incident_id) pairs.
    Returns the total number of alerts stored.
    """
    cursor = conn.cursor()

    # Fetch GAS incidents with coordinates
    cursor.execute("""
        SELECT incident_id, reported_at, x_ft, y_ft
        FROM incidents
        WHERE utility_type = 'GAS' AND x_ft IS NOT NULL AND y_ft IS NOT NULL
    """)
    gas_records = cursor.fetchall()

    # Fetch ELECTRIC incidents with coordinates
    cursor.execute("""
        SELECT incident_id, reported_at, x_ft, y_ft
        FROM incidents
        WHERE utility_type = 'ELECTRIC' AND x_ft IS NOT NULL AND y_ft IS NOT NULL
    """)
    elec_records = cursor.fetchall()

    # Pre-parse timestamps
    parsed_gas = []
    for g in gas_records:
        try:
            dt = parse_iso_datetime(g["reported_at"])
            parsed_gas.append((g["incident_id"], g["x_ft"], g["y_ft"], dt))
        except Exception:
            continue

    parsed_elec = []
    for e in elec_records:
        try:
            dt = parse_iso_datetime(e["reported_at"])
            parsed_elec.append((e["incident_id"], e["x_ft"], e["y_ft"], dt))
        except Exception:
            continue

    matched_pairs = []
    for g_id, g_x, g_y, g_dt in parsed_gas:
        for e_id, e_x, e_y, e_dt in parsed_elec:
            matches, dist, gap_min = is_correlated(g_x, g_y, g_dt, e_x, e_y, e_dt)
            if matches:
                matched_pairs.append((g_id, e_id, dist, gap_min))

    # Sync alerts table inside transaction
    # First, clear previous alerts or upsert
    cursor.execute("DELETE FROM alerts;")
    cursor.executemany("""
        INSERT INTO alerts (gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes)
        VALUES (?, ?, ?, ?)
    """, matched_pairs)
    conn.commit()

    return len(matched_pairs)
