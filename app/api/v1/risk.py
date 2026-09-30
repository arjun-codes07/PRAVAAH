"""Risk predictions API router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.common import PaginatedResponse
from app.schemas.risk import RiskPredictionResponse, RiskPredictionDetailResponse
from app.services.risk_service import get_risk_predictions, get_risk_prediction_detail

router = APIRouter(prefix="/risk", tags=["Risk"])

@router.get("/predictions", response_model=PaginatedResponse[RiskPredictionResponse])
def list_risk_predictions(
    zone_id: Optional[int] = Query(default=None, description="Filter by zone ID"),
    status: str = Query(default="ACTIVE", description="Filter by prediction status"),
    min_level: Optional[str] = Query(default=None, description="Minimum overall risk level"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve paginated risk predictions."""
    return get_risk_predictions(
        db=db,
        authority_id=current_user.authority_id,
        zone_id=zone_id,
        status_filter=status,
        min_level=min_level,
        limit=limit,
        offset=offset,
    )

@router.get("/predictions/{id}", response_model=RiskPredictionDetailResponse)
def risk_prediction_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed risk prediction including risk explanations, related incidents, and alerts."""
    return get_risk_prediction_detail(
        db=db,
        authority_id=current_user.authority_id,
        prediction_id=id,
    )
