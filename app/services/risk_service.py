"""Risk service for listing predictions and obtaining prediction detail with explanations."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def get_risk_predictions(
    db: Session,
    authority_id: Optional[int],
    zone_id: Optional[int] = None,
    status_filter: str = "ACTIVE",
    min_level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated risk predictions filtered by authority, zone, status, and min_level."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if zone_id is not None:
        where_clauses.append("rp.zone_id = :zone_id")
        params["zone_id"] = zone_id
    if status_filter:
        where_clauses.append("rp.status = :status_filter")
        params["status_filter"] = status_filter

    risk_levels = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    if min_level and min_level.upper() in risk_levels:
        idx = risk_levels.index(min_level.upper())
        allowed = risk_levels[idx:]
        where_clauses.append("rp.overall_risk_level IN (" + ",".join(f"'{lvl}'" for lvl in allowed) + ")")

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"""
        SELECT COUNT(*)
        FROM risk_predictions rp
        JOIN zones z ON rp.zone_id = z.id
        WHERE {where_sql}
    """)
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            rp.id, rp.zone_id, rp.location_id, rp.model_name, rp.overall_risk_level,
            rp.flood_risk_level, rp.landslide_risk_level, rp.confidence,
            rp.flood_probability, rp.landslide_probability, rp.predicted_at,
            rp.horizon_minutes, rp.recommended_action, rp.status, rp.data_origin,
            rp.input_data_as_of
        FROM risk_predictions rp
        JOIN zones z ON rp.zone_id = z.id
        WHERE {where_sql}
        ORDER BY rp.predicted_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, params).mappings().all()

    now = datetime.now(timezone.utc)
    stale_threshold = timedelta(minutes=settings.STALE_DEFAULT_MINUTES)

    items = []
    for r in rows:
        pred_at = r["predicted_at"]
        horizon = r["horizon_minutes"] or 60
        valid_until = pred_at + timedelta(minutes=horizon)
        # APPLIED DEFAULT: input_is_stale derived from input_data_as_of vs stale threshold
        input_data_as_of = r["input_data_as_of"]
        input_is_stale = (
            input_data_as_of is None
            or (now - input_data_as_of) > stale_threshold
        )
        
        items.append({
            "id": r["id"],
            "zone_id": r["zone_id"],
            "location_id": r["location_id"],
            "model_name": r["model_name"],
            "overall_risk_level": r["overall_risk_level"],
            "flood_risk_level": r["flood_risk_level"],
            "landslide_risk_level": r["landslide_risk_level"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "flood_probability": float(r["flood_probability"]) if r["flood_probability"] is not None else None,
            "landslide_probability": float(r["landslide_probability"]) if r["landslide_probability"] is not None else None,
            "predicted_at": pred_at,
            "horizon_minutes": horizon,
            "valid_until": valid_until,
            "recommended_action": r["recommended_action"],
            "status": r["status"],
            "data_origin": r["data_origin"],
            "input_data_as_of": input_data_as_of,
            "input_is_stale": input_is_stale,
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}

def get_risk_prediction_detail(db: Session, authority_id: Optional[int], prediction_id: int) -> Dict[str, Any]:
    """Retrieve full risk prediction detail including risk explanations, related incidents, and alerts."""
    auth_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    params: Dict[str, Any] = {"pid": prediction_id}
    if authority_id is not None:
        params["auth_id"] = authority_id

    sql = text(f"""
        SELECT 
            rp.id, rp.zone_id, rp.location_id, rp.model_name, rp.overall_risk_level,
            rp.flood_risk_level, rp.landslide_risk_level, rp.confidence,
            rp.flood_probability, rp.landslide_probability, rp.predicted_at,
            rp.horizon_minutes, rp.recommended_action, rp.status, rp.data_origin,
            rp.input_data_as_of
        FROM risk_predictions rp
        JOIN zones z ON rp.zone_id = z.id
        WHERE rp.id = :pid {auth_filter}
    """)
    rp = db.execute(sql, params).mappings().first()
    if not rp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prediction {prediction_id} not found or access denied")

    pred_at = rp["predicted_at"]
    horizon = rp["horizon_minutes"] or 60
    valid_until = pred_at + timedelta(minutes=horizon)

    # Explanations
    re_sql = text("SELECT id, factor_name, contribution, factor_value, unit, explanation_text, display_order FROM risk_explanations WHERE risk_prediction_id = :pid ORDER BY display_order ASC")
    re_rows = db.execute(re_sql, {"pid": prediction_id}).mappings().all()
    explanations = [
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

    # Related incidents
    inc_sql = text("SELECT id, incident_type, severity, status FROM incidents WHERE source_prediction_id = :pid")
    inc_rows = db.execute(inc_sql, {"pid": prediction_id}).mappings().all()

    # Related alerts
    alt_sql = text("SELECT id, alert_type, severity, status, message FROM alerts WHERE source_prediction_id = :pid")
    alt_rows = db.execute(alt_sql, {"pid": prediction_id}).mappings().all()

    input_data_as_of = rp["input_data_as_of"]
    now = datetime.now(timezone.utc)
    stale_threshold = timedelta(minutes=settings.STALE_DEFAULT_MINUTES)
    input_is_stale = (
        input_data_as_of is None
        or (now - input_data_as_of) > stale_threshold
    )

    return {
        "id": rp["id"],
        "zone_id": rp["zone_id"],
        "location_id": rp["location_id"],
        "model_name": rp["model_name"],
        "overall_risk_level": rp["overall_risk_level"],
        "flood_risk_level": rp["flood_risk_level"],
        "landslide_risk_level": rp["landslide_risk_level"],
        "confidence": float(rp["confidence"]) if rp["confidence"] is not None else None,
        "flood_probability": float(rp["flood_probability"]) if rp["flood_probability"] is not None else None,
        "landslide_probability": float(rp["landslide_probability"]) if rp["landslide_probability"] is not None else None,
        "predicted_at": pred_at,
        "horizon_minutes": horizon,
        "valid_until": valid_until,
        "recommended_action": rp["recommended_action"],
        "status": rp["status"],
        "data_origin": rp["data_origin"],
        "input_data_as_of": input_data_as_of,
        "input_is_stale": input_is_stale,
        "explanations": explanations,
        "related_incidents": [dict(r) for r in inc_rows],
        "related_alerts": [dict(r) for r in alt_rows],
    }
