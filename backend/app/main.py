from contextlib import asynccontextmanager
import os
import sqlite3
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.config as config
from app.database import get_connection, init_db
from app.ingest import ingest_csv
from app.schemas import (
    HealthResponse,
    Incident,
    Alert,
    SummaryResponse,
    IngestResponse,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database schema is created on startup."""
    init_db()
    yield

# Initialize FastAPI application
app = FastAPI(
    title="GridSignal Mini API",
    description="Utility Incident Intelligence and Cross-Type Analytics Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local dev and frontend deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Simple healthy/ready response indicating service status and DB connectivity."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1;").fetchone()
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="ok",
        service="GridSignal Mini",
        database=db_status
    )

@app.get("/incidents", response_model=List[Incident], tags=["Incidents"])
def list_incidents(
    utility_type: Optional[str] = Query(
        default=None,
        description="Filter by utility type: GAS or ELECTRIC"
    )
):
    """
    Return all valid imported incidents, including those with missing coordinates.
    Optionally filter by utility_type.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        filter_val = utility_type if isinstance(utility_type, str) else None
        if filter_val and filter_val.strip():
            cursor.execute("""
                SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
                FROM incidents
                WHERE UPPER(utility_type) = UPPER(?)
                ORDER BY reported_at ASC
            """, (filter_val.strip(),))
        else:
            cursor.execute("""
                SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
                FROM incidents
                ORDER BY reported_at ASC
            """)
        rows = cursor.fetchall()
        return [Incident(**dict(row)) for row in rows]
    finally:
        conn.close()

@app.get("/alerts", response_model=List[Alert], tags=["Alerts"])
def list_alerts():
    """
    Return list of unique GAS/ELECTRIC matched pairs.
    Includes gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes,
    plus joined incident details (severity, status, timestamp) for rich UI visualization.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                a.gas_incident_id,
                a.electric_incident_id,
                a.distance_ft,
                a.time_gap_minutes,
                g.reported_at AS gas_reported_at,
                e.reported_at AS electric_reported_at,
                g.severity AS gas_severity,
                e.severity AS electric_severity,
                g.status AS gas_status,
                e.status AS electric_status
            FROM alerts a
            JOIN incidents g ON a.gas_incident_id = g.incident_id
            JOIN incidents e ON a.electric_incident_id = e.incident_id
            ORDER BY a.distance_ft ASC, a.time_gap_minutes ASC
        """)
        rows = cursor.fetchall()
        return [Alert(**dict(row)) for row in rows]
    finally:
        conn.close()

@app.get("/summary", response_model=SummaryResponse, tags=["Analytics"])
def get_summary():
    """
    Return total_incidents, total_gas, total_electric, total_alerts.
    Loaded dynamically from database state.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS count FROM incidents;")
        total_incidents = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM incidents WHERE UPPER(utility_type) = 'GAS';")
        total_gas = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM incidents WHERE UPPER(utility_type) = 'ELECTRIC';")
        total_electric = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM alerts;")
        total_alerts = cursor.fetchone()["count"]

        return SummaryResponse(
            total_incidents=total_incidents,
            total_gas=total_gas,
            total_electric=total_electric,
            total_alerts=total_alerts
        )
    finally:
        conn.close()

@app.post("/api/import/seed", response_model=IngestResponse, tags=["Data Management"])
def import_seed_data():
    """Trigger ingestion of the seed_incidents.csv file."""
    if not config.SEED_CSV_PATH.is_file():
        raise HTTPException(status_code=404, detail="Seed CSV file not found on server")
    stats = ingest_csv(config.SEED_CSV_PATH)
    return IngestResponse(**stats)

@app.post("/api/import/replay", response_model=IngestResponse, tags=["Data Management"])
def import_replay_data():
    """Trigger ingestion of the replay_batch.csv file."""
    if not config.REPLAY_CSV_PATH.is_file():
        raise HTTPException(status_code=404, detail="Replay CSV file not found on server")
    stats = ingest_csv(config.REPLAY_CSV_PATH)
    return IngestResponse(**stats)

# Mount frontend dist static files if built
static_dist = Path(__file__).resolve().parent.parent / "static"
if static_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dist), html=True), name="static")
