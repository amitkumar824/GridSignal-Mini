import sqlite3
from typing import Optional
from pathlib import Path
from .config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    utility_type TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    x_ft REAL,
    y_ft REAL,
    severity TEXT DEFAULT 'MEDIUM',
    status TEXT DEFAULT 'OPEN',
    area TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_utility ON incidents(utility_type);
CREATE INDEX IF NOT EXISTS idx_incidents_reported ON incidents(reported_at);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gas_incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    electric_incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    distance_ft REAL NOT NULL,
    time_gap_minutes REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(gas_incident_id, electric_incident_id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_pair ON alerts(gas_incident_id, electric_incident_id);
"""

def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Return a configured sqlite3 Connection with foreign keys enabled and row factory."""
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize SQLite database tables and indexes."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
