"""Telemetry ingestion schemas."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

class TelemetryIngestRequest(BaseModel):
    node_id: str
    timestamp: datetime
    rainfall_1h: Optional[float] = Field(default=None, ge=0.0)
    soil_moisture: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    water_level: Optional[float] = Field(default=None, ge=0.0)
    slope_angle: Optional[float] = Field(default=None, ge=0.0, le=90.0)
    temperature: Optional[float] = None
    humidity: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    data_origin: Literal["REAL", "SIMULATED", "REPLAYED"]

class TelemetryIngestResponse(BaseModel):
    observation_id: int
    quality_status: str
