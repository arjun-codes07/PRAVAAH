"""Sensor node service with lateral join for latest reading and dynamic staleness computation."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def get_sensors(
    db: Session,
    authority_id: Optional[int],
    zone_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    stale_filter: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve list of sensor nodes with latest reading (via lateral join) and computed staleness."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "default_stale": settings.STALE_DEFAULT_MINUTES,
    }

    if authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if zone_id is not None:
        where_clauses.append("sn.zone_id = :zone_id")
        params["zone_id"] = zone_id
    if status_filter:
        where_clauses.append("sn.status = :status_filter")
        params["status_filter"] = status_filter

    where_sql = " AND ".join(where_clauses)

    query_sql = text(f"""
        SELECT 
            sn.id, sn.node_id, NULL as name, sn.sensor_type, sn.zone_id, sn.location_id,
            sn.status, sn.last_seen_at, sn.data_origin,
            COALESCE(ds.stale_after_minutes, :default_stale) as stale_minutes,
            obs.id as obs_id, obs.observed_at, obs.rainfall_1h_mm, obs.soil_moisture_pct,
            obs.water_level_m, obs.water_level_rate_m_per_h, obs.slope_angle_deg,
            obs.temperature_c, obs.humidity_pct, obs.quality_status, obs.data_origin as obs_origin
        FROM sensor_nodes sn
        JOIN data_sources ds ON sn.data_source_id = ds.id
        JOIN zones z ON sn.zone_id = z.id
        LEFT JOIN LATERAL (
            SELECT * FROM observations o
            WHERE o.sensor_node_id = sn.id
            ORDER BY o.sensor_node_id DESC, o.observed_at DESC
            LIMIT 1
        ) obs ON TRUE
        WHERE {where_sql}
        ORDER BY sn.id ASC
    """)
    
    rows = db.execute(query_sql, params).mappings().all()

    now_utc = datetime.now(timezone.utc)
    items = []

    for r in rows:
        last_seen = r["last_seen_at"]
        stale_mins = r["stale_minutes"]
        is_stale = False
        if last_seen is None:
            is_stale = True
        else:
            diff_mins = (now_utc - last_seen).total_seconds() / 60.0
            is_stale = diff_mins > stale_mins

        if stale_filter is not None and is_stale != stale_filter:
            continue

        latest_reading = None
        if r["obs_id"] is not None:
            latest_reading = {
                "id": r["obs_id"],
                "observed_at": r["observed_at"],
                "rainfall_1h_mm": float(r["rainfall_1h_mm"]) if r["rainfall_1h_mm"] is not None else None,
                "soil_moisture_pct": float(r["soil_moisture_pct"]) if r["soil_moisture_pct"] is not None else None,
                "water_level_m": float(r["water_level_m"]) if r["water_level_m"] is not None else None,
                "water_level_rate_m_per_h": float(r["water_level_rate_m_per_h"]) if r["water_level_rate_m_per_h"] is not None else None,
                "slope_angle_deg": float(r["slope_angle_deg"]) if r["slope_angle_deg"] is not None else None,
                "temperature_c": float(r["temperature_c"]) if r["temperature_c"] is not None else None,
                "humidity_pct": float(r["humidity_pct"]) if r["humidity_pct"] is not None else None,
                "quality_status": r["quality_status"],
                "data_origin": r["obs_origin"],
            }

        items.append({
            "id": r["id"],
            "node_id": r["node_id"],
            "name": r["name"],
            "sensor_type": r["sensor_type"],
            "zone_id": r["zone_id"],
            "location_id": r["location_id"],
            "status": r["status"],
            "is_stale": is_stale,
            "last_seen_at": last_seen,
            "data_origin": r["data_origin"],
            "latest_reading": latest_reading,
        })

    total = len(items)
    paginated_items = items[offset : offset + limit]

    return {"items": paginated_items, "total": total, "limit": limit, "offset": offset}


def get_sensor_readings(
    db: Session,
    node_id: str,
    authority_id: Optional[int],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve time-series readings for a specific sensor node."""
    limit = min(max(1, limit), 500)
    offset = max(0, offset)

    # Resolve sensor and check authority
    s_sql = text("""
        SELECT sn.id, sn.zone_id, z.authority_id
        FROM sensor_nodes sn
        JOIN zones z ON sn.zone_id = z.id
        WHERE sn.node_id = :node_id
    """)
    sensor = db.execute(s_sql, {"node_id": node_id}).mappings().first()
    if not sensor:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sensor '{node_id}' not found")

    if authority_id is not None and sensor["authority_id"] != authority_id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sensor '{node_id}' access denied")

    where_clauses = ["sensor_node_id = :sid"]
    params: Dict[str, Any] = {"sid": sensor["id"], "limit": limit, "offset": offset}

    if start_time:
        where_clauses.append("observed_at >= :start_time")
        params["start_time"] = start_time
    if end_time:
        where_clauses.append("observed_at <= :end_time")
        params["end_time"] = end_time

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"SELECT COUNT(*) FROM observations WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            id, sensor_node_id, data_source_id, zone_id, location_id,
            observed_at, ingested_at, rainfall_1h_mm, soil_moisture_pct,
            water_level_m, water_level_rate_m_per_h, slope_angle_deg,
            temperature_c, humidity_pct, quality_status, data_origin
        FROM observations
        WHERE {where_sql}
        ORDER BY observed_at DESC
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
