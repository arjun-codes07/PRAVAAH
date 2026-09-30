"""Risk prediction schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class RiskExplanationResponse(BaseModel):
    id: int
    factor_name: str
    contribution: float
    factor_value: Optional[float] = None
    unit: Optional[str] = None
    explanation_text: Optional[str] = None
    display_order: int

class RiskPredictionResponse(BaseModel):
    id: int
    zone_id: int
    location_id: Optional[int] = None
    model_name: str
    overall_risk_level: str
    flood_risk_level: Optional[str] = None
    landslide_risk_level: Optional[str] = None
    confidence: Optional[float] = None
    flood_probability: Optional[float] = None
    landslide_probability: Optional[float] = None
    predicted_at: datetime
    horizon_minutes: int
    valid_until: datetime
    recommended_action: Optional[str] = None
    status: str
    data_origin: str
    input_data_as_of: Optional[datetime] = None
    input_is_stale: Optional[bool] = None

class RiskPredictionDetailResponse(RiskPredictionResponse):
    explanations: List[RiskExplanationResponse] = []
    related_incidents: List[Dict[str, Any]] = []
    related_alerts: List[Dict[str, Any]] = []
