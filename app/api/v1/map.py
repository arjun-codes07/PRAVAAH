"""Map API router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.services.map_service import get_map_features

router = APIRouter(prefix="/map", tags=["Map"])

@router.get("/features")
def map_features(
    layers: str = Query(default="zones,incidents,sensors,resources,teams,rescue_routes,evacuation_zones,evacuation_routes", description="Comma-separated layers"),
    bbox: Optional[str] = Query(default=None, description="Bounding box min_lon,min_lat,max_lon,max_lat"),
    min_level: Optional[str] = Query(default=None, description="Minimum risk level filter (LOW, MODERATE, HIGH, CRITICAL)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve GeoJSON FeatureCollection containing requested spatial feature layers."""
    return get_map_features(
        db=db,
        authority_id=current_user.authority_id,
        layers_str=layers,
        bbox=bbox,
        min_level=min_level,
    )
