from typing import Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "GridSignal Mini"
    database: str = "connected"

class Incident(BaseModel):
    incident_id: str
    utility_type: str
    reported_at: str
    x_ft: Optional[float] = None
    y_ft: Optional[float] = None
    severity: str
    status: str
    area: Optional[str] = None

class Alert(BaseModel):
    gas_incident_id: str
    electric_incident_id: str
    distance_ft: float
    time_gap_minutes: float
    gas_reported_at: Optional[str] = None
    electric_reported_at: Optional[str] = None
    gas_severity: Optional[str] = None
    electric_severity: Optional[str] = None
    gas_status: Optional[str] = None
    electric_status: Optional[str] = None

class SummaryResponse(BaseModel):
    total_incidents: int
    total_gas: int
    total_electric: int
    total_alerts: int

class IngestResponse(BaseModel):
    status: str = "success"
    file_processed: str
    total_rows: int
    inserted_new: int
    updated_conflicting: int
    skipped_identical: int
    skipped_malformed: int
    alerts_count: int
