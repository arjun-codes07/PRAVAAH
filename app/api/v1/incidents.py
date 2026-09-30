"""Incidents API router."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.common import PaginatedResponse
from app.schemas.incidents import (
    IncidentListResponse,
    IncidentDetailResponse,
    IncidentCreateRequest,
    IncidentUpdateRequest,
    ResponseActionCreateRequest,
    ResponseActionResponse,
)
from app.services.incidents_service import (
    get_incidents,
    get_incident_detail,
    create_incident as create_incident_service,
    update_incident as update_incident_service,
    create_response_action as create_response_action_service,
)

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("", response_model=PaginatedResponse[IncidentListResponse])
def list_incidents(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    incident_type: Optional[str] = Query(default=None, description="Filter by incident type"),
    zone_id: Optional[int] = Query(default=None, description="Filter by zone ID"),
    from_date: Optional[datetime] = Query(default=None, alias="from", description="Filter from reported timestamp"),
    to_date: Optional[datetime] = Query(default=None, alias="to", description="Filter to reported timestamp"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve paginated incidents."""
    return get_incidents(
        db=db,
        authority_id=current_user.authority_id,
        status_filter=status,
        severity=severity,
        incident_type=incident_type,
        zone_id=zone_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )

@router.post("", response_model=IncidentDetailResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new incident and record an audit log."""
    return create_incident_service(db, current_user, payload)

@router.get("/{id}", response_model=IncidentDetailResponse)
def incident_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve complete incident details including response actions and assignments."""
    return get_incident_detail(
        db=db,
        authority_id=current_user.authority_id,
        incident_id=id,
    )

@router.patch("/{id}", response_model=IncidentDetailResponse)
def update_incident(
    id: int,
    payload: IncidentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update incident status, severity, description, or resolved_at."""
    return update_incident_service(db, current_user, id, payload)

@router.post("/{id}/response-actions", response_model=ResponseActionResponse, status_code=status.HTTP_201_CREATED)
def create_response_action(
    id: int,
    payload: ResponseActionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a response action for an incident."""
    return create_response_action_service(db, current_user, id, payload)
