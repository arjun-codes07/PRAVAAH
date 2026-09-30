"""Observations API router."""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.zones import ObservationsListResponse

router = APIRouter(prefix="/observations", tags=["Observations"])

@router.get("", response_model=ObservationsListResponse)
def list_observations(
    zone_id: Optional[int] = Query(default=None),
    sensor_node_id: Optional[int] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    quality_status: Optional[str] = Query(default=None),
    data_origin: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve global / authority-scoped sensor observations."""
    limit = min(max(1, limit), 500)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if current_user.authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = current_user.authority_id
    if zone_id is not None:
        where_clauses.append("o.zone_id = :zone_id")
        params["zone_id"] = zone_id
    if sensor_node_id is not None:
        where_clauses.append("o.sensor_node_id = :sensor_node_id")
        params["sensor_node_id"] = sensor_node_id
    if start_time:
        where_clauses.append("o.observed_at >= :start_time")
        params["start_time"] = start_time
    if end_time:
        where_clauses.append("o.observed_at <= :end_time")
        params["end_time"] = end_time
    if quality_status:
        where_clauses.append("o.quality_status = :quality_status")
        params["quality_status"] = quality_status
    if data_origin:
        where_clauses.append("o.data_origin = :data_origin")
        params["data_origin"] = data_origin

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"""
        SELECT COUNT(*)
        FROM observations o
        JOIN zones z ON o.zone_id = z.id
        WHERE {where_sql}
    """)
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            o.id, o.sensor_node_id, o.data_source_id, o.zone_id, o.location_id,
            o.observed_at, o.ingested_at, o.rainfall_1h_mm, o.soil_moisture_pct,
            o.water_level_m, o.water_level_rate_m_per_h, o.slope_angle_deg,
            o.temperature_c, o.humidity_pct, o.quality_status, o.data_origin
        FROM observations o
        JOIN zones z ON o.zone_id = z.id
        WHERE {where_sql}
        ORDER BY o.observed_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, params).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        for k in ("rainfall_1h_mm", "soil_moisture_pct", "water_level_m", "water_level_rate_m_per_h", "slope_angle_deg", "temperature_c", "humidity_pct"):
            if d[k] is not None:
                d[k] = float(d[k])
        items.append(d)

    return {"items": items, "total": total, "limit": limit, "offset": offset}
