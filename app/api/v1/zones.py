"""Zones API router."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.zones import (
    ZoneDetailResponse,
    ZoneListResponse,
    ObservationsListResponse,
    ZoneRiskHistoryResponse,
)
from app.services.zones_service import (
    get_zone_detail,
    get_zones,
    get_zone_observations,
    get_zone_risk_history,
)

router = APIRouter(prefix="/zones", tags=["Zones"])

@router.get("", response_model=ZoneListResponse)
def list_zones(
    status: Optional[str] = Query(default=None, description="Filter by status (ACTIVE/INACTIVE)"),
    zone_type: Optional[str] = Query(default=None, description="Filter by zone type"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve list of zones with active risk summary and counts."""
    return get_zones(
        db=db,
        authority_id=current_user.authority_id,
        status_filter=status,
        zone_type=zone_type,
        limit=limit,
        offset=offset,
    )

@router.get("/{id}", response_model=ZoneDetailResponse)
def zone_detail(
    id: int,
    include_geometry: bool = Query(default=False, description="Include GeoJSON geometry"),
    nearby_radius_m: Optional[float] = Query(default=None, description="Nearby resource search radius in meters"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve zone details, current risk, top factors, sensors, incidents, alerts, and optional nearby resources."""
    return get_zone_detail(
        db=db,
        zone_id=id,
        authority_id=current_user.authority_id,
        include_geometry=include_geometry,
        nearby_radius_m=nearby_radius_m,
    )

@router.get("/{id}/observations", response_model=ObservationsListResponse)
def zone_observations(
    id: int,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    quality_status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve time-series observations for a specific zone."""
    return get_zone_observations(
        db=db,
        zone_id=id,
        authority_id=current_user.authority_id,
        start_time=start_time,
        end_time=end_time,
        quality_status=quality_status,
        limit=limit,
        offset=offset,
    )

@router.get("/{id}/risk-history", response_model=ZoneRiskHistoryResponse)
def zone_risk_history(
    id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve prediction history for a zone."""
    return get_zone_risk_history(
        db=db,
        zone_id=id,
        authority_id=current_user.authority_id,
        limit=limit,
        offset=offset,
    )
