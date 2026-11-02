from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import DB_PATH, SEED_CSV_PATH, REPLAY_CSV_PATH, STATIC_DIR
from .database import get_connection, init_db
from .schemas import (
    HealthResponse,
    IncidentCreate,
    IncidentResponse,
    AlertResponse,
    SummaryResponse,
    IngestResponse,
)
from .ingest import ingest_csv, upsert_single_incident
from .correlate import run_correlation

# Initialize SQLite database schema and seed on startup
init_db()
_init_conn = get_connection()
try:
    _cur = _init_conn.cursor()
    _cur.execute("SELECT COUNT(*) FROM incidents;")
    if _cur.fetchone()[0] == 0 and SEED_CSV_PATH.is_file():
        ingest_csv(SEED_CSV_PATH, _init_conn)
finally:
    _init_conn.close()

app = FastAPI(
    title="GridSignal Mini API",
    description="Utility Incident Analytics & Cross-Type Pair Hazard Correlation Platform",
    version="1.0.0",
)

# CORS Middleware allowing cross-origin requests from any frontend/port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    """Serve the single-page application dashboard directly at root /."""
    html_path = STATIC_DIR / "index.html"
    if html_path.is_file():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>GridSignal Mini API is running. Dashboard HTML not found.</h1>")

@app.get("/health", response_model=HealthResponse, tags=["Health"])
def get_health(conn=Depends(get_db)):
    """Simple healthy/ready response indicating service status and DB connectivity."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="ok",
        service="GridSignal Mini",
        database=db_status
    )

@app.get("/incidents", response_model=List[IncidentResponse], tags=["Incidents"])
def get_incidents(
    utility_type: Optional[str] = Query(None, description="Filter by utility type: GAS or ELECTRIC"),
    conn=Depends(get_db)
):
    """
    Return valid imported incidents, including those with missing coordinates.
    Optional filter: ?utility_type=GAS or ?utility_type=ELECTRIC
    """
    cursor = conn.cursor()
    if utility_type:
        cursor.execute("""
            SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
            FROM incidents
            WHERE UPPER(utility_type) = UPPER(?)
            ORDER BY reported_at ASC
        """, (utility_type.strip(),))
    else:
        cursor.execute("""
            SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
            FROM incidents
            ORDER BY reported_at ASC
        """)

    rows = cursor.fetchall()
    return [IncidentResponse(**dict(r)) for r in rows]

@app.post("/incidents", response_model=IncidentResponse, status_code=201, tags=["Incidents"])
def create_incident(incident: IncidentCreate, conn=Depends(get_db)):
    """
    Ingest a single incident via REST API JSON payload (e.g. from IoT sensors, SCADA webhooks, or mobile crews).
    Applies the Last-Write-Wins (LWW) deduplication policy and re-runs the cross-utility correlation engine.
    """
    res = upsert_single_incident(incident.model_dump(), conn)
    if res == "skipped_malformed":
        raise HTTPException(status_code=400, detail="Invalid incident data or malformed ISO-8601 timestamp")

    conn.commit()
    # Re-run correlation engine so alerts are instantly updated
    run_correlation(conn)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT incident_id, utility_type, reported_at, x_ft, y_ft, severity, status, area
        FROM incidents WHERE incident_id = ?
    """, (incident.incident_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to retrieve saved incident")
    return IncidentResponse(**dict(row))

@app.get("/alerts", response_model=List[AlertResponse], tags=["Alerts"])
def get_alerts(conn=Depends(get_db)):
    """
    Return list of unique GAS/ELECTRIC matched pairs.
    Includes gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes, created_at
        FROM alerts
        ORDER BY distance_ft ASC, time_gap_minutes ASC
    """)
    rows = cursor.fetchall()
    return [AlertResponse(**dict(r)) for r in rows]

@app.get("/summary", response_model=SummaryResponse, tags=["Summary"])
def get_summary(conn=Depends(get_db)):
    """Return total_incidents, total_gas, total_electric, and total_alerts counts."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM incidents;")
    total_incidents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM incidents WHERE utility_type = 'GAS';")
    total_gas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM incidents WHERE utility_type = 'ELECTRIC';")
    total_electric = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts;")
    total_alerts = cursor.fetchone()[0]

    return SummaryResponse(
        total_incidents=total_incidents,
        total_gas=total_gas,
        total_electric=total_electric,
        total_alerts=total_alerts
    )

@app.post("/api/import/seed", response_model=IngestResponse, tags=["Ingestion"])
def import_seed(conn=Depends(get_db)):
    """Trigger ingestion of seed_incidents.csv."""
    if not SEED_CSV_PATH.is_file():
        raise HTTPException(status_code=404, detail="Seed CSV file not found")
    stats = ingest_csv(SEED_CSV_PATH, conn)
    return IngestResponse(**stats)

@app.post("/api/import/replay", response_model=IngestResponse, tags=["Ingestion"])
def import_replay(conn=Depends(get_db)):
    """Trigger ingestion of replay_batch.csv."""
    if not REPLAY_CSV_PATH.is_file():
        raise HTTPException(status_code=404, detail="Replay CSV file not found")
    stats = ingest_csv(REPLAY_CSV_PATH, conn)
    return IngestResponse(**stats)
