"""Incident and response action schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class IncidentListResponse(BaseModel):
    id: int
    incident_type: str
    severity: str
    status: str
    zone_id: int
    location_id: Optional[int] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    data_origin: str

class IncidentDetailResponse(IncidentListResponse):
    description: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    zone: Dict[str, Any]
    location: Optional[Dict[str, Any]] = None
    source_prediction: Optional[Dict[str, Any]] = None
    alerts: List[Dict[str, Any]] = []
    response_actions: List[Dict[str, Any]] = []

class IncidentCreateRequest(BaseModel):
    zone_id: int
    incident_type: Literal["FLOOD", "LANDSLIDE", "OTHER"]
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    description: Optional[str] = None
    location_id: Optional[int] = None
    source_prediction_id: Optional[int] = None
    started_at: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    data_origin: Literal["REAL", "SIMULATED", "REPLAYED"] = "SIMULATED"

class IncidentUpdateRequest(BaseModel):
    status: Optional[Literal["OPEN", "IN_PROGRESS", "RESOLVED"]] = None
    severity: Optional[Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]] = None
    description: Optional[str] = None
    resolved_at: Optional[datetime] = None

class ResponseActionCreateRequest(BaseModel):
    action_type: str
    priority: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"] = "MEDIUM"
    notes: Optional[str] = None

class ResponseActionUpdateRequest(BaseModel):
    status: Optional[Literal["PLANNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]] = None
    priority: Optional[Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ResponseActionResponse(BaseModel):
    id: int
    incident_id: int
    action_type: str
    status: str
    priority: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    assignments: List[Dict[str, Any]] = []
