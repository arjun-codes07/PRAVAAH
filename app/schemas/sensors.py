"""Sensor node schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

class SensorNodeResponse(BaseModel):
    id: int
    node_id: str
    name: Optional[str] = None
    sensor_type: str
    zone_id: int
    location_id: Optional[int] = None
    status: str
    is_stale: bool
    last_seen_at: Optional[datetime] = None
    data_origin: str
    latest_reading: Optional[Dict[str, Any]] = None
