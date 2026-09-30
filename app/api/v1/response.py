"""Response management, teams, resources, and assignments API router."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.response import (
    RescueTeamResponse,
    RescueResourceResponse,
    ResponseAssignmentCreateRequest,
    ResponseAssignmentUpdateRequest,
    ResponseAssignmentResponse,
)
from app.schemas.incidents import ResponseActionUpdateRequest, ResponseActionResponse
from app.services.response_service import (
    get_rescue_teams,
    get_rescue_resources,
    create_assignment as create_assignment_service,
    update_assignment as update_assignment_service,
)
from app.services.incidents_service import update_response_action as update_response_action_service

router = APIRouter(tags=["Response Coordination"])

@router.get("/response/teams", response_model=List[RescueTeamResponse])
def list_teams(
    status: Optional[str] = Query(default=None, description="Filter by status (AVAILABLE, DEPLOYED, UNAVAILABLE)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve list of rescue teams with active assignment counts."""
    return get_rescue_teams(
        db=db,
        authority_id=current_user.authority_id,
        status_filter=status,
    )

@router.get("/response/resources", response_model=List[RescueResourceResponse])
def list_resources(
    status: Optional[str] = Query(default=None, description="Filter by status (AVAILABLE, DEPLOYED, UNAVAILABLE)"),
    resource_type: Optional[str] = Query(default=None, description="Filter by resource type"),
    near_lat: Optional[float] = Query(default=None, description="Proximity search latitude"),
    near_lon: Optional[float] = Query(default=None, description="Proximity search longitude"),
    radius_m: Optional[float] = Query(default=None, description="Proximity search radius in meters"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve list of rescue resources with optional proximity distance calculation."""
    return get_rescue_resources(
        db=db,
        authority_id=current_user.authority_id,
        status_filter=status,
        resource_type=resource_type,
        near_lat=near_lat,
        near_lon=near_lon,
        radius_m=radius_m,
    )

@router.patch("/response-actions/{id}", response_model=ResponseActionResponse)
def update_response_action(
    id: int,
    payload: ResponseActionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update status, priority, or notes of a response action."""
    return update_response_action_service(db, current_user, id, payload)

@router.post("/response-actions/{id}/assignments", response_model=ResponseAssignmentResponse, status_code=status.HTTP_201_CREATED)
def create_assignment(
    id: int,
    payload: ResponseAssignmentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign team or resource to response action, preventing duplicate active assignments."""
    return create_assignment_service(db, current_user, id, payload)

@router.patch("/assignments/{id}", response_model=ResponseAssignmentResponse)
def update_assignment(
    id: int,
    payload: ResponseAssignmentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update response assignment status (ASSIGNED, DEPLOYED, RELEASED)."""
    return update_assignment_service(db, current_user, id, payload)
