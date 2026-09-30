"""Telemetry ingestion API router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from app.services.telemetry_service import ingest_telemetry

router = APIRouter(prefix="/ingest", tags=["Telemetry Ingestion"])

@router.post("/telemetry", response_model=TelemetryIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest(
    payload: TelemetryIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest IoT sensor telemetry payload."""
    return ingest_telemetry(db, payload)
