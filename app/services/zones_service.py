"""Zone service for detailed zone information, risk, sensors, incidents, and spatial nearby resource search."""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def get_zone_detail(
    db: Session,
    zone_id: int,
    authority_id: Optional[int],
    include_geometry: bool = False,
    nearby_radius_m: Optional[float] = None,
) -> Dict[str, Any]:
    """Retrieve full zone detail including current risk, top factors, terrain, sensors, active incidents/alerts, and optional nearby resources."""
    auth_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    params: Dict[str, Any] = {"zid": zone_id}
    if authority_id is not None:
        params["auth_id"] = authority_id

    # 1. Zone
    zone_sql = text(f"""
        SELECT id as zone_id, name, zone_type, admin_code, authority_id, status, ST_AsGeoJSON(geom) as geojson
        FROM zones z
        WHERE z.id = :zid {auth_filter}
    """)
    zone_row = db.execute(zone_sql, params).mappings().first()
    if not zone_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found or access denied",
        )

    geometry = json.loads(zone_row["geojson"]) if (include_geometry and zone_row["geojson"]) else None

    # 2. Current ACTIVE Risk Prediction
    rp_sql = text("""
        SELECT id, model_name, overall_risk_level, flood_risk_level, landslide_risk_level,
               confidence, flood_probability, landslide_probability, predicted_at, horizon_minutes,
               recommended_action, status, data_origin
        FROM risk_predictions
        WHERE zone_id = :zid AND status = 'ACTIVE'
        ORDER BY predicted_at DESC LIMIT 1
    """)
    rp_row = db.execute(rp_sql, {"zid": zone_id}).mappings().first()
    
    current_risk = None
    top_factors = []
    if rp_row:
        pred_at = rp_row["predicted_at"]
        horizon = rp_row["horizon_minutes"] or 60
        valid_until = pred_at + timedelta(minutes=horizon)
        
        current_risk = {
            "id": rp_row["id"],
            "model_name": rp_row["model_name"],
            "overall_risk_level": rp_row["overall_risk_level"],
            "flood_risk_level": rp_row["flood_risk_level"],
            "landslide_risk_level": rp_row["landslide_risk_level"],
            "confidence": float(rp_row["confidence"]) if rp_row["confidence"] is not None else None,
            "flood_probability": float(rp_row["flood_probability"]) if rp_row["flood_probability"] is not None else None,
            "landslide_probability": float(rp_row["landslide_probability"]) if rp_row["landslide_probability"] is not None else None,
            "predicted_at": pred_at,
            "horizon_minutes": horizon,
            "valid_until": valid_until,
            "recommended_action": rp_row["recommended_action"],
            "status": rp_row["status"],
            "data_origin": rp_row["data_origin"],
        }
        
        # Top factors from risk_explanations
        re_sql = text("""
            SELECT id, factor_name, contribution, factor_value, unit, explanation_text, display_order
            FROM risk_explanations
            WHERE risk_prediction_id = :rpid
            ORDER BY display_order ASC
        """)
        re_rows = db.execute(re_sql, {"rpid": rp_row["id"]}).mappings().all()
        top_factors = [
            {
                "id": r["id"],
                "factor_name": r["factor_name"],
                "contribution": float(r["contribution"]),
                "factor_value": float(r["factor_value"]) if r["factor_value"] is not None else None,
                "unit": r["unit"],
                "explanation_text": r["explanation_text"],
                "display_order": r["display_order"],
            }
            for r in re_rows
        ]

    # 3. Terrain features
    tf_sql = text("""
        SELECT id, elevation_m, slope_deg, susceptibility_score, data_source_id, data_origin
        FROM terrain_features
        WHERE zone_id = :zid
    """)
    tf_rows = db.execute(tf_sql, {"zid": zone_id}).mappings().all()
    terrain = [dict(r) for r in tf_rows]

    # 4. Latest observation in zone
    obs_sql = text("""
        SELECT id, sensor_node_id, observed_at, rainfall_1h_mm, soil_moisture_pct, water_level_m,
               temperature_c, humidity_pct, quality_status, data_origin
        FROM observations
        WHERE zone_id = :zid
        ORDER BY observed_at DESC LIMIT 1
    """)
    obs_row = db.execute(obs_sql, {"zid": zone_id}).mappings().first()
    latest_obs = dict(obs_row) if obs_row else None

    # 5. Sensors in zone
    now_utc = datetime.now(timezone.utc)
    sn_sql = text("""
        SELECT sn.id, sn.node_id, NULL as name, sn.sensor_type, sn.zone_id, sn.location_id,
               sn.status, sn.last_seen_at, sn.data_origin,
               COALESCE(ds.stale_after_minutes, :default_stale) as stale_minutes
        FROM sensor_nodes sn
        JOIN data_sources ds ON sn.data_source_id = ds.id
        WHERE sn.zone_id = :zid
    """)
    sn_rows = db.execute(sn_sql, {"zid": zone_id, "default_stale": settings.STALE_DEFAULT_MINUTES}).mappings().all()
    sensors = []
    for r in sn_rows:
        last_seen = r["last_seen_at"]
        stale_mins = r["stale_minutes"]
        is_stale = False
        if last_seen is None:
            is_stale = True
        else:
            diff_mins = (now_utc - last_seen).total_seconds() / 60.0
            is_stale = diff_mins > stale_mins
            
        sensors.append({
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
        })

    # 6. Active incidents
    inc_sql = text("""
        SELECT id, incident_type, severity, status, created_at, data_origin
        FROM incidents
        WHERE zone_id = :zid AND status IN ('REPORTED', 'VERIFIED', 'IN_PROGRESS')
        ORDER BY created_at DESC
    """)
    inc_rows = db.execute(inc_sql, {"zid": zone_id}).mappings().all()
    active_incidents = [dict(r) for r in inc_rows]

    # 7. Active alerts
    alt_sql = text("""
        SELECT id, alert_type, severity, status, message, issued_at, expires_at, data_origin
        FROM alerts
        WHERE zone_id = :zid AND status IN ('ACTIVE', 'ACKNOWLEDGED')
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY issued_at DESC
    """)
    alt_rows = db.execute(alt_sql, {"zid": zone_id}).mappings().all()
    active_alerts = [dict(r) for r in alt_rows]

    # 8. Nearby resources (if requested via nearby_radius_m)
    nearby_resources = None
    if nearby_radius_m is not None and nearby_radius_m > 0:
        res_sql = text("""
            SELECT rr.id, rr.name, rr.resource_type, rr.status, 'SIMULATED' as data_origin,
                   ST_Distance(rr.geom::geography, z.geom::geography) as distance_m
            FROM rescue_resources rr, zones z
            WHERE z.id = :zid
              AND ST_DWithin(rr.geom::geography, z.geom::geography, :radius)
            ORDER BY distance_m ASC
        """)
        res_rows = db.execute(res_sql, {"zid": zone_id, "radius": nearby_radius_m}).mappings().all()
        nearby_resources = [
            {
                "id": r["id"],
                "name": r["name"],
                "resource_type": r["resource_type"],
                "status": r["status"],
                "distance_m": round(float(r["distance_m"]), 2),
                "data_origin": r["data_origin"],
            }
            for r in res_rows
        ]

    return {
        "zone_id": zone_row["zone_id"],
        "name": zone_row["name"],
        "zone_type": zone_row["zone_type"],
        "admin_code": zone_row["admin_code"],
        "authority_id": zone_row["authority_id"],
        "status": zone_row["status"],
        "geometry": geometry,
        "current_risk": current_risk,
        "top_factors": top_factors,
        "terrain": terrain,
        "latest_observation": latest_obs,
        "sensors": sensors,
        "active_incidents": active_incidents,
        "active_alerts": active_alerts,
        "nearby_resources": nearby_resources,
        "data_origin": "SIMULATED",
    }


def get_zones(
    db: Session,
    authority_id: Optional[int],
    status_filter: Optional[str] = None,
    zone_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve list of zones with active risk summary, sensor counts, and incident/alert counts."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if status_filter:
        where_clauses.append("z.status = :status_filter")
        params["status_filter"] = status_filter
    if zone_type:
        where_clauses.append("z.zone_type = :zone_type")
        params["zone_type"] = zone_type

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"SELECT COUNT(*) FROM zones z WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            z.id, z.name, z.zone_type, z.admin_code, z.authority_id, z.status,
            z.created_at, z.updated_at,
            rp.overall_risk_level as current_risk_level,
            rp.flood_risk_level,
            rp.landslide_risk_level,
            COALESCE(sc.sensor_count, 0) as sensor_count,
            COALESCE(ic.active_incident_count, 0) as active_incident_count,
            COALESCE(ac.active_alert_count, 0) as active_alert_count
        FROM zones z
        LEFT JOIN LATERAL (
            SELECT overall_risk_level, flood_risk_level, landslide_risk_level
            FROM risk_predictions
            WHERE zone_id = z.id AND status = 'ACTIVE'
            ORDER BY predicted_at DESC LIMIT 1
        ) rp ON true
        LEFT JOIN (
            SELECT zone_id, COUNT(*) as sensor_count
            FROM sensor_nodes
            GROUP BY zone_id
        ) sc ON sc.zone_id = z.id
        LEFT JOIN (
            SELECT zone_id, COUNT(*) as active_incident_count
            FROM incidents
            WHERE status IN ('OPEN', 'IN_PROGRESS')
            GROUP BY zone_id
        ) ic ON ic.zone_id = z.id
        LEFT JOIN (
            SELECT zone_id, COUNT(*) as active_alert_count
            FROM alerts
            WHERE status IN ('ACTIVE', 'ACKNOWLEDGED')
              AND (expires_at IS NULL OR expires_at > now())
            GROUP BY zone_id
        ) ac ON ac.zone_id = z.id
        WHERE {where_sql}
        ORDER BY z.id ASC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, params).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_zone_observations(
    db: Session,
    zone_id: int,
    authority_id: Optional[int],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    quality_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve time-series observations for a specific zone."""
    limit = min(max(1, limit), 500)
    offset = max(0, offset)

    # Authority check
    if authority_id is not None:
        z = db.execute(text("SELECT authority_id FROM zones WHERE id = :zid"), {"zid": zone_id}).mappings().first()
        if not z or z["authority_id"] != authority_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone {zone_id} not found or access denied")

    where_clauses = ["zone_id = :zid"]
    params: Dict[str, Any] = {"zid": zone_id, "limit": limit, "offset": offset}

    if start_time:
        where_clauses.append("observed_at >= :start_time")
        params["start_time"] = start_time
    if end_time:
        where_clauses.append("observed_at <= :end_time")
        params["end_time"] = end_time
    if quality_status:
        where_clauses.append("quality_status = :quality_status")
        params["quality_status"] = quality_status

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


def get_zone_risk_history(
    db: Session,
    zone_id: int,
    authority_id: Optional[int],
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve historical risk predictions for a zone."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    if authority_id is not None:
        z = db.execute(text("SELECT authority_id FROM zones WHERE id = :zid"), {"zid": zone_id}).mappings().first()
        if not z or z["authority_id"] != authority_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone {zone_id} not found or access denied")

    count_sql = text("SELECT COUNT(*) FROM risk_predictions WHERE zone_id = :zid")
    total = db.execute(count_sql, {"zid": zone_id}).scalar() or 0

    query_sql = text("""
        SELECT 
            id, zone_id, predicted_at, horizon_minutes, model_name, model_version,
            overall_risk_level, flood_risk_level, landslide_risk_level,
            confidence, flood_probability, landslide_probability,
            recommended_action, status, data_origin
        FROM risk_predictions
        WHERE zone_id = :zid
        ORDER BY predicted_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, {"zid": zone_id, "limit": limit, "offset": offset}).mappings().all()

    items = []
    for r in rows:
        d = dict(r)
        for k in ("confidence", "flood_probability", "landslide_probability"):
            if d[k] is not None:
                d[k] = float(d[k])
        items.append(d)

    return {"items": items, "total": total, "limit": limit, "offset": offset}
