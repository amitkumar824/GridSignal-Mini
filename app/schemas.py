from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class HealthResponse(BaseModel):
    status: str
    service: str
    database: str

class IncidentResponse(BaseModel):
    incident_id: str
    utility_type: str
    reported_at: str
    x_ft: Optional[float] = None
    y_ft: Optional[float] = None
    severity: str
    status: str
    area: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AlertResponse(BaseModel):
    id: int
    gas_incident_id: str
    electric_incident_id: str
    distance_ft: float
    time_gap_minutes: float
    created_at: str

    model_config = ConfigDict(from_attributes=True)

class SummaryResponse(BaseModel):
    total_incidents: int
    total_gas: int
    total_electric: int
    total_alerts: int

class IngestResponse(BaseModel):
    status: str
    file_processed: str
    total_rows: int
    inserted_new: int
    updated_conflicting: int
    skipped_identical: int
    skipped_malformed: int
    alerts_count: int

