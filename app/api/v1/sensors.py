"""Sensors API router."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.common import PaginatedResponse
from app.schemas.sensors import SensorNodeResponse
from app.services.sensors_service import get_sensors

router = APIRouter(prefix="/sensors", tags=["Sensors"])

@router.get("", response_model=PaginatedResponse[SensorNodeResponse])
def list_sensors(
    zone_id: Optional[int] = Query(default=None, description="Filter by zone ID"),
    status: Optional[str] = Query(default=None, description="Filter by status (e.g. ACTIVE)"),
    stale: Optional[bool] = Query(default=None, description="Filter by staleness"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve paginated sensor nodes with computed staleness and latest reading (via lateral join)."""
    return get_sensors(
        db=db,
        authority_id=current_user.authority_id,
        zone_id=zone_id,
        status_filter=status,
        stale_filter=stale,
        limit=limit,
        offset=offset,
    )

@router.get("/{node_id}/readings")
def sensor_readings(
    node_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve time-series readings for a specific sensor node."""
    from app.services.sensors_service import get_sensor_readings
    return get_sensor_readings(
        db=db,
        node_id=node_id,
        authority_id=current_user.authority_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
