"""Alert Pydantic schemas."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel

class AlertCreateRequest(BaseModel):
    zone_id: int
    location_id: Optional[int] = None
    alert_type: str
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    message: str
    incident_id: Optional[int] = None
    source_prediction_id: Optional[int] = None
    expires_at: Optional[datetime] = None

class AlertResponse(BaseModel):
    id: int
    zone_id: int
    location_id: Optional[int] = None
    incident_id: Optional[int] = None
    source_prediction_id: Optional[int] = None
    alert_type: str
    severity: str
    status: str
    effective_status: str
    message: str
    issued_at: datetime
    expires_at: Optional[datetime] = None
    issued_by: int
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    data_origin: str
