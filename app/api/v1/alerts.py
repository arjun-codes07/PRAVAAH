"""Alerts API router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user, check_alert_permission
from app.models.tables import User
from app.schemas.common import PaginatedResponse
from app.schemas.alerts import AlertCreateRequest, AlertResponse
from app.services.alerts_service import get_alerts, get_alert_detail, create_alert, acknowledge_alert

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("", response_model=PaginatedResponse[AlertResponse])
def list_alerts(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    zone_id: Optional[int] = Query(default=None, description="Filter by zone ID"),
    active_only: bool = Query(default=False, description="Filter for unexpired active/acknowledged alerts"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve paginated alerts with computed effective_status."""
    return get_alerts(
        db=db,
        authority_id=current_user.authority_id,
        status_filter=status,
        severity=severity,
        zone_id=zone_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

@router.get("/{id}", response_model=AlertResponse)
def alert_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve alert detail by ID."""
    return get_alert_detail(
        db=db,
        authority_id=current_user.authority_id,
        alert_id=id,
    )

@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def issue_alert(
    payload: AlertCreateRequest,
    current_user: User = Depends(check_alert_permission),
    db: Session = Depends(get_db),
):
    """Issue a new alert and record audit log entry."""
    return create_alert(db, current_user, payload)

@router.post("/{id}/acknowledge", response_model=AlertResponse)
def ack_alert(
    id: int,
    current_user: User = Depends(check_alert_permission),
    db: Session = Depends(get_db),
):
    """Acknowledge an active alert and record audit log entry."""
    return acknowledge_alert(db, current_user, id)
