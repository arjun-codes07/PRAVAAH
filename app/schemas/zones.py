"""Zone schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.schemas.sensors import SensorNodeResponse
from app.schemas.risk import RiskExplanationResponse

class ZoneSummaryResponse(BaseModel):
    id: int
    name: str
    zone_type: str
    admin_code: Optional[str] = None
    authority_id: Optional[int] = None
    status: str
    current_risk_level: Optional[str] = None
    flood_risk_level: Optional[str] = None
    landslide_risk_level: Optional[str] = None
    sensor_count: int = 0
    active_incident_count: int = 0
    active_alert_count: int = 0
    created_at: datetime
    updated_at: datetime

class ZoneListResponse(BaseModel):
    items: List[ZoneSummaryResponse]
    total: int
    limit: int
    offset: int

class ZoneDetailResponse(BaseModel):
    zone_id: int
    name: str
    zone_type: str
    admin_code: Optional[str] = None
    authority_id: Optional[int] = None
    status: str
    geometry: Optional[Dict[str, Any]] = None
    current_risk: Optional[Dict[str, Any]] = None
    top_factors: List[RiskExplanationResponse] = []
    terrain: List[Dict[str, Any]] = []
    latest_observation: Optional[Dict[str, Any]] = None
    sensors: List[SensorNodeResponse] = []
    active_incidents: List[Dict[str, Any]] = []
    active_alerts: List[Dict[str, Any]] = []
    nearby_resources: Optional[List[Dict[str, Any]]] = None
    data_origin: str

class ObservationItemResponse(BaseModel):
    id: int
    sensor_node_id: Optional[int] = None
    data_source_id: int
    zone_id: int
    location_id: Optional[int] = None
    observed_at: datetime
    ingested_at: Optional[datetime] = None
    rainfall_1h_mm: Optional[float] = None
    soil_moisture_pct: Optional[float] = None
    water_level_m: Optional[float] = None
    water_level_rate_m_per_h: Optional[float] = None
    slope_angle_deg: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    quality_status: str
    data_origin: str

class ObservationsListResponse(BaseModel):
    items: List[ObservationItemResponse]
    total: int
    limit: int
    offset: int

class ZoneRiskHistoryItem(BaseModel):
    id: int
    zone_id: int
    predicted_at: datetime
    horizon_minutes: int
    model_name: str
    model_version: str
    overall_risk_level: str
    flood_risk_level: Optional[str] = None
    landslide_risk_level: Optional[str] = None
    confidence: Optional[float] = None
    flood_probability: Optional[float] = None
    landslide_probability: Optional[float] = None
    recommended_action: Optional[str] = None
    status: str
    data_origin: str

class ZoneRiskHistoryResponse(BaseModel):
    items: List[ZoneRiskHistoryItem]
    total: int
    limit: int
    offset: int
