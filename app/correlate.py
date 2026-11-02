import math
import sqlite3
from datetime import datetime, timezone
from typing import Tuple, Optional
from .config import MAX_DISTANCE_FT, MAX_TIME_GAP_MINUTES

def calculate_planar_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate 2D Euclidean distance in planar feet: sqrt((x1 - x2)^2 + (y1 - y2)^2)."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

def calculate_time_gap_minutes(dt1: datetime, dt2: datetime) -> float:
    """Calculate absolute difference between two datetimes in decimal minutes."""
    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    if dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    delta_seconds = abs((dt1 - dt2).total_seconds())
    return delta_seconds / 60.0

def is_correlated(
    gas_x: Optional[float],
    gas_y: Optional[float],
    gas_dt: datetime,
    elec_x: Optional[float],
    elec_y: Optional[float],
    elec_dt: datetime,
    max_distance_ft: float = MAX_DISTANCE_FT,
    max_time_gap_minutes: float = MAX_TIME_GAP_MINUTES,
) -> Tuple[bool, Optional[float], Optional[float]]:
    """
    Check if a Gas and Electric incident pair satisfies correlation criteria:
    1. Both must have non-null planar coordinates.
    2. Distance <= max_distance_ft (inclusive).
    3. Time gap <= max_time_gap_minutes (inclusive).
    Returns (matches, distance_ft, time_gap_minutes).
    """
    if gas_x is None or gas_y is None or elec_x is None or elec_y is None:
        return False, None, None

    dist = calculate_planar_distance(gas_x, gas_y, elec_x, elec_y)
    gap = calculate_time_gap_minutes(gas_dt, elec_dt)

    if dist <= max_distance_ft and gap <= max_time_gap_minutes:
        return True, round(dist, 2), round(gap, 2)
    return False, round(dist, 2), round(gap, 2)

def run_correlation(conn: sqlite3.Connection) -> int:
    """
    Evaluate all cross-utility pairs (GAS x ELECTRIC) in SQLite.
    Atomically sync the alerts table, returning total alerts count.
    """
    cursor = conn.cursor()
    # Fetch Gas incidents with coordinates
    cursor.execute("""
        SELECT incident_id, reported_at, x_ft, y_ft
        FROM incidents
        WHERE utility_type = 'GAS' AND x_ft IS NOT NULL AND y_ft IS NOT NULL
    """)
    gas_incidents = cursor.fetchall()

    # Fetch Electric incidents with coordinates
    cursor.execute("""
        SELECT incident_id, reported_at, x_ft, y_ft
        FROM incidents
        WHERE utility_type = 'ELECTRIC' AND x_ft IS NOT NULL AND y_ft IS NOT NULL
    """)
    elec_incidents = cursor.fetchall()

    matched_pairs = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for g in gas_incidents:
        g_dt = datetime.fromisoformat(g['reported_at'])
        for e in elec_incidents:
            e_dt = datetime.fromisoformat(e['reported_at'])
            matches, dist, gap = is_correlated(
                gas_x=g['x_ft'],
                gas_y=g['y_ft'],
                gas_dt=g_dt,
                elec_x=e['x_ft'],
                elec_y=e['y_ft'],
                elec_dt=e_dt,
            )
            if matches:
                matched_pairs.append((g['incident_id'], e['incident_id'], dist, gap, now_iso))

    with conn:
        cursor.execute("DELETE FROM alerts;")
        cursor.executemany("""
            INSERT INTO alerts (gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, matched_pairs)

    return len(matched_pairs)

