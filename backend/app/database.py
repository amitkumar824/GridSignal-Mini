import sqlite3
from pathlib import Path
from typing import Optional
import app.config as config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    utility_type TEXT NOT NULL,
    reported_at TEXT NOT NULL,
    x_ft REAL,
    y_ft REAL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    area TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incidents_utility ON incidents(utility_type);
CREATE INDEX IF NOT EXISTS idx_incidents_coords ON incidents(x_ft, y_ft);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gas_incident_id TEXT NOT NULL,
    electric_incident_id TEXT NOT NULL,
    distance_ft REAL NOT NULL,
    time_gap_minutes REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gas_incident_id, electric_incident_id),
    FOREIGN KEY(gas_incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE,
    FOREIGN KEY(electric_incident_id) REFERENCES incidents(incident_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alerts_pair ON alerts(gas_incident_id, electric_incident_id);
"""

def get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys and Row factory enabled."""
    target_path = str(db_path or config.DATABASE_PATH)
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str | Path] = None) -> None:
    """Initialize database tables and indices if not existing."""
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
