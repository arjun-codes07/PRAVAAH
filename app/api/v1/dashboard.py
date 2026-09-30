"""Dashboard API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve high-level dashboard summary filtered by user authority_id."""
    return get_dashboard_summary(db, current_user.authority_id)
