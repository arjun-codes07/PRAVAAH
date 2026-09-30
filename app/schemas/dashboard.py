"""Dashboard summary schemas."""

from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class HighRiskZoneSummary(BaseModel):
    zone_id: int
    zone_name: str
    risk_level: str
    predicted_at: datetime
    data_origin: str

class RecentRiskChange(BaseModel):
    zone_id: int
    zone_name: str
    previous_level: str
    current_level: str
    changed_at: datetime
    data_origin: str

class ActiveIncidentSummary(BaseModel):
    id: int
    incident_type: str
    severity: str
    status: str
    zone_id: int
    created_at: datetime
    data_origin: str

class ActiveIncidentsOverview(BaseModel):
    count: int
    by_severity: Dict[str, int]
    latest: List[ActiveIncidentSummary]

class ActiveAlertsOverview(BaseModel):
    count: int
    by_severity: Dict[str, int]
    latest: List[Any]

class SensorHealthOverview(BaseModel):
    active: int
    stale: int
    inactive: int

class EnvironmentalIndicators(BaseModel):
    as_of: datetime
    avg_rainfall_1h_mm: Optional[float] = None
    avg_soil_moisture_pct: Optional[float] = None
    avg_water_level_m: Optional[float] = None
    avg_temperature_c: Optional[float] = None
    avg_humidity_pct: Optional[float] = None

class ResourceStatusSummary(BaseModel):
    available: int
    deployed: int
    maintenance: int

class DashboardSummaryResponse(BaseModel):
    risk_counts_by_level: Dict[str, int]
    high_risk_zones: List[HighRiskZoneSummary]
    recent_changes: List[RecentRiskChange]
    active_incidents: ActiveIncidentsOverview
    active_alerts: ActiveAlertsOverview
    sensor_health: SensorHealthOverview
    environmental_indicators: EnvironmentalIndicators
    resource_status: ResourceStatusSummary
    data_origins_present: List[str]
