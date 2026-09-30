"""
PRAVAAH Risk Engine — Rule-based baseline risk assessment.

This is a transparent, rule-based engine (NO ML training).
It reads the latest VALID observations, terrain features, and historical events
to produce per-zone risk predictions written to risk_predictions + risk_explanations.

Per SPEC section 9:
- Insert new ACTIVE prediction and SUPERSEDE previous in ONE transaction.
- model_name = 'demo-rule-baseline', model_version from config.
- confidence and probabilities stay NULL (no unvalidated accuracy claims).
- data_origin = least-trusted origin among inputs (SIMULATED > REPLAYED > REAL).

APPLIED DEFAULTS (NOT SPECIFIED in source documents):
- Aggregation: max for rainfall, water_level, rate; mean for soil_moisture.
- Trigger: after POST /ingest/telemetry (best-effort; errors logged, don't fail ingestion).
- Stale-input handling: if a zone has no non-stale VALID input, do NOT write a new prediction.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.risk_config import (
    MODEL_NAME,
    MODEL_VERSION,
    HORIZON_MINUTES,
    FLOOD_THRESHOLDS,
    LANDSLIDE_THRESHOLDS,
    SUSCEPTIBILITY_WEIGHT,
    HISTORICAL_RECENT_YEARS,
    HISTORICAL_WEIGHT,
    LEVEL_ORDER,
    score_to_level,
    metric_to_score,
    RECOMMENDED_ACTION_TEMPLATES,
    EXPLANATION_TEMPLATES,
    CONTEXT_PHRASES,
)
from app.core.config import settings

logger = logging.getLogger("pravaah.risk_engine")

# Origin trust ordering: SIMULATED is least trusted
ORIGIN_TRUST = {"REAL": 0, "REPLAYED": 1, "SIMULATED": 2}


def _worst_origin(*origins: str) -> str:
    """Return the least-trusted data_origin from inputs."""
    worst = "REAL"
    for o in origins:
        if ORIGIN_TRUST.get(o, 2) > ORIGIN_TRUST.get(worst, 0):
            worst = o
    return worst


def _to_float(val) -> Optional[float]:
    """Convert Decimal or other numeric to float, or None."""
    if val is None:
        return None
    return float(val)


def compute_zone_risk(db: Session, zone_id: int) -> Optional[int]:
    """Compute and write a risk prediction for a single zone.
    
    Returns the new prediction ID, or None if skipped (stale/no data).
    """
    now = datetime.now(timezone.utc)
    stale_minutes = settings.STALE_DEFAULT_MINUTES

    # -----------------------------------------------------------------------
    # 1. Gather latest VALID observations from ACTIVE, non-stale sensors
    # -----------------------------------------------------------------------
    obs_sql = text("""
        SELECT 
            o.rainfall_1h_mm, o.soil_moisture_pct, o.water_level_m,
            o.water_level_rate_m_per_h, o.data_origin,
            sn.data_origin AS sensor_origin,
            ds.data_origin AS ds_origin,
            ds.stale_after_minutes
        FROM sensor_nodes sn
        JOIN data_sources ds ON sn.data_source_id = ds.id
        CROSS JOIN LATERAL (
            SELECT * FROM observations
            WHERE sensor_node_id = sn.id
              AND quality_status = 'VALID'
            ORDER BY observed_at DESC
            LIMIT 1
        ) o
        WHERE sn.zone_id = :zone_id
          AND sn.status = 'ACTIVE'
          AND sn.last_seen_at IS NOT NULL
          AND sn.last_seen_at > :stale_cutoff
    """)
    
    # Use per-source stale threshold or global default
    stale_cutoff = now - timedelta(minutes=stale_minutes)
    rows = db.execute(obs_sql, {"zone_id": zone_id, "stale_cutoff": stale_cutoff}).mappings().all()

    if not rows:
        # No non-stale VALID input — do NOT write a fresh-looking prediction
        logger.info(f"Zone {zone_id}: no non-stale VALID observations, skipping prediction")
        return None

    # -----------------------------------------------------------------------
    # 2. Aggregate observations (APPLIED DEFAULT aggregation)
    # -----------------------------------------------------------------------
    rainfall_values = [_to_float(r["rainfall_1h_mm"]) for r in rows if r["rainfall_1h_mm"] is not None]
    water_level_values = [_to_float(r["water_level_m"]) for r in rows if r["water_level_m"] is not None]
    water_rate_values = [_to_float(r["water_level_rate_m_per_h"]) for r in rows if r["water_level_rate_m_per_h"] is not None]
    soil_moisture_values = [_to_float(r["soil_moisture_pct"]) for r in rows if r["soil_moisture_pct"] is not None]

    # Aggregation: max for flood metrics, mean for soil moisture
    max_rainfall = max(rainfall_values) if rainfall_values else None
    max_water_level = max(water_level_values) if water_level_values else None
    max_water_rate = max(water_rate_values) if water_rate_values else None
    mean_soil_moisture = (sum(soil_moisture_values) / len(soil_moisture_values)) if soil_moisture_values else None

    # Determine data_origin = least trusted across all input rows
    all_origins = []
    for r in rows:
        all_origins.append(r["data_origin"])
        all_origins.append(r["sensor_origin"])
        all_origins.append(r["ds_origin"])

    # -----------------------------------------------------------------------
    # 3. Terrain features for this zone
    # -----------------------------------------------------------------------
    terrain_sql = text("""
        SELECT slope_deg, susceptibility_score, data_origin
        FROM terrain_features
        WHERE zone_id = :zone_id AND location_id IS NULL
        LIMIT 1
    """)
    terrain = db.execute(terrain_sql, {"zone_id": zone_id}).mappings().first()
    
    slope_deg = _to_float(terrain["slope_deg"]) if terrain else None
    susceptibility = _to_float(terrain["susceptibility_score"]) if terrain else None
    if terrain:
        all_origins.append(terrain["data_origin"])

    # -----------------------------------------------------------------------
    # 4. Historical events context
    # -----------------------------------------------------------------------
    hist_sql = text("""
        SELECT hazard_type, COUNT(*) AS cnt, data_origin
        FROM historical_events
        WHERE zone_id = :zone_id
          AND event_time > :cutoff
        GROUP BY hazard_type, data_origin
    """)
    hist_cutoff = now - timedelta(days=HISTORICAL_RECENT_YEARS * 365)
    hist_rows = db.execute(hist_sql, {"zone_id": zone_id, "cutoff": hist_cutoff}).mappings().all()
    
    flood_hist_count = 0
    landslide_hist_count = 0
    for hr in hist_rows:
        all_origins.append(hr["data_origin"])
        if hr["hazard_type"] == "FLOOD":
            flood_hist_count += int(hr["cnt"])
        elif hr["hazard_type"] == "LANDSLIDE":
            landslide_hist_count += int(hr["cnt"])

    data_origin = _worst_origin(*all_origins) if all_origins else "SIMULATED"

    # -----------------------------------------------------------------------
    # 5. Compute flood risk score
    # -----------------------------------------------------------------------
    flood_scores = []
    explanations = []
    display_order = 1

    if max_rainfall is not None:
        score = metric_to_score(max_rainfall, FLOOD_THRESHOLDS["rainfall_1h_mm"])
        flood_scores.append(score)
        level = score_to_level(score)
        context = CONTEXT_PHRASES[level]
        explanations.append({
            "factor_name": "rainfall_1h",
            "factor_value": round(max_rainfall, 4),
            "unit": "mm/h",
            "contribution": round(min(score / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["rainfall_1h"].format(
                value=max_rainfall, level=level, context=context
            ),
            "display_order": display_order,
        })
        display_order += 1

    if max_water_level is not None:
        score = metric_to_score(max_water_level, FLOOD_THRESHOLDS["water_level_m"])
        flood_scores.append(score)
        level = score_to_level(score)
        context = CONTEXT_PHRASES[level]
        explanations.append({
            "factor_name": "water_level",
            "factor_value": round(max_water_level, 4),
            "unit": "m",
            "contribution": round(min(score / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["water_level"].format(
                value=max_water_level, level=level, context=context
            ),
            "display_order": display_order,
        })
        display_order += 1

    if max_water_rate is not None:
        score = metric_to_score(max_water_rate, FLOOD_THRESHOLDS["water_level_rate_m_per_h"])
        flood_scores.append(score)
        level = score_to_level(score)
        context = CONTEXT_PHRASES[level]
        explanations.append({
            "factor_name": "water_level_rate",
            "factor_value": round(max_water_rate, 4),
            "unit": "m/h",
            "contribution": round(min(score / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["water_level_rate"].format(
                value=max_water_rate, level=level, context=context
            ),
            "display_order": display_order,
        })
        display_order += 1

    # Historical flood modifier
    if flood_hist_count > 0:
        hist_modifier = min(flood_hist_count * HISTORICAL_WEIGHT, 0.5)
        if flood_scores:
            flood_scores[-1] += hist_modifier  # Apply to last score
        explanations.append({
            "factor_name": "historical_flood_events",
            "factor_value": Decimal(str(flood_hist_count)),
            "unit": "events",
            "contribution": round(hist_modifier / 3.0, 4),
            "explanation_text": EXPLANATION_TEMPLATES["historical_events"].format(
                count=flood_hist_count, hazard_type="flood",
                years=HISTORICAL_RECENT_YEARS,
                context=f"Historical precedent increases assessed risk by {hist_modifier:.2f} points."
            ),
            "display_order": display_order,
        })
        display_order += 1

    flood_score = max(flood_scores) if flood_scores else 0.0
    flood_risk_level = score_to_level(flood_score) if flood_scores else None

    # -----------------------------------------------------------------------
    # 6. Compute landslide risk score
    # -----------------------------------------------------------------------
    ls_scores = []

    if mean_soil_moisture is not None:
        score = metric_to_score(mean_soil_moisture, LANDSLIDE_THRESHOLDS["soil_moisture_pct"])
        ls_scores.append(score)
        level = score_to_level(score)
        context = CONTEXT_PHRASES[level]
        explanations.append({
            "factor_name": "soil_moisture",
            "factor_value": round(mean_soil_moisture, 4),
            "unit": "%",
            "contribution": round(min(score / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["soil_moisture"].format(
                value=mean_soil_moisture, level=level, context=context
            ),
            "display_order": display_order,
        })
        display_order += 1

    if slope_deg is not None:
        score = metric_to_score(slope_deg, LANDSLIDE_THRESHOLDS["slope_deg"])
        ls_scores.append(score)
        level = score_to_level(score)
        context = CONTEXT_PHRASES[level]
        explanations.append({
            "factor_name": "slope_angle",
            "factor_value": round(slope_deg, 4),
            "unit": "degrees",
            "contribution": round(min(score / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["slope_angle"].format(
                value=slope_deg, level=level, context=context
            ),
            "display_order": display_order,
        })
        display_order += 1

    if max_rainfall is not None:
        score = metric_to_score(max_rainfall, LANDSLIDE_THRESHOLDS["rainfall_1h_mm"])
        ls_scores.append(score)
        # Already have a rainfall explanation for flood; don't duplicate

    # Susceptibility modifier
    if susceptibility is not None and susceptibility > 0:
        susc_modifier = susceptibility * SUSCEPTIBILITY_WEIGHT * 3.0  # Scale to 0-3
        if ls_scores:
            ls_scores[-1] += susc_modifier
        explanations.append({
            "factor_name": "susceptibility",
            "factor_value": round(susceptibility, 4),
            "unit": "score",
            "contribution": round(min(susc_modifier / 3.0, 1.0), 4),
            "explanation_text": EXPLANATION_TEMPLATES["susceptibility"].format(
                value=susceptibility, level=score_to_level(susc_modifier),
                context=f"Terrain susceptibility contributes {susc_modifier:.2f} to landslide risk score."
            ),
            "display_order": display_order,
        })
        display_order += 1

    # Historical landslide modifier
    if landslide_hist_count > 0:
        hist_modifier = min(landslide_hist_count * HISTORICAL_WEIGHT, 0.5)
        if ls_scores:
            ls_scores[-1] += hist_modifier
        explanations.append({
            "factor_name": "historical_landslide_events",
            "factor_value": Decimal(str(landslide_hist_count)),
            "unit": "events",
            "contribution": round(hist_modifier / 3.0, 4),
            "explanation_text": EXPLANATION_TEMPLATES["historical_events"].format(
                count=landslide_hist_count, hazard_type="landslide",
                years=HISTORICAL_RECENT_YEARS,
                context=f"Historical precedent increases assessed risk by {hist_modifier:.2f} points."
            ),
            "display_order": display_order,
        })
        display_order += 1

    ls_score = max(ls_scores) if ls_scores else 0.0
    landslide_risk_level = score_to_level(ls_score) if ls_scores else None

    # -----------------------------------------------------------------------
    # 7. Overall risk = max of flood and landslide
    # -----------------------------------------------------------------------
    overall_score = max(flood_score, ls_score)
    overall_risk_level = score_to_level(overall_score)

    # Recommended action text
    recommended_action = RECOMMENDED_ACTION_TEMPLATES.get(overall_risk_level, "")

    # input_data_as_of: the earliest observed_at among the inputs used
    input_as_of_sql = text("""
        SELECT MIN(o.observed_at) AS min_obs
        FROM sensor_nodes sn
        CROSS JOIN LATERAL (
            SELECT observed_at FROM observations
            WHERE sensor_node_id = sn.id AND quality_status = 'VALID'
            ORDER BY observed_at DESC LIMIT 1
        ) o
        WHERE sn.zone_id = :zone_id AND sn.status = 'ACTIVE'
          AND sn.last_seen_at IS NOT NULL
          AND sn.last_seen_at > :stale_cutoff
    """)
    input_data_as_of_row = db.execute(input_as_of_sql, {"zone_id": zone_id, "stale_cutoff": stale_cutoff}).first()
    input_data_as_of = input_data_as_of_row[0] if input_data_as_of_row else now

    # -----------------------------------------------------------------------
    # 8. Write prediction + supersede previous (ONE transaction per SPEC §9)
    # -----------------------------------------------------------------------
    try:
        # Supersede existing ACTIVE prediction for this zone
        supersede_sql = text("""
            UPDATE risk_predictions
            SET status = 'SUPERSEDED'
            WHERE zone_id = :zone_id
              AND location_id IS NULL
              AND status = 'ACTIVE'
            RETURNING id
        """)
        superseded = db.execute(supersede_sql, {"zone_id": zone_id}).fetchall()
        if superseded:
            logger.info(f"Zone {zone_id}: superseded prediction(s) {[r[0] for r in superseded]}")

        # Insert new ACTIVE prediction
        insert_sql = text("""
            INSERT INTO risk_predictions (
                zone_id, location_id, predicted_at, horizon_minutes,
                flood_probability, landslide_probability,
                flood_risk_level, landslide_risk_level, overall_risk_level,
                confidence, model_name, model_version,
                recommended_action, input_data_as_of, data_origin, status
            ) VALUES (
                :zone_id, NULL, :predicted_at, :horizon_minutes,
                NULL, NULL,
                :flood_risk_level, :landslide_risk_level, :overall_risk_level,
                NULL, :model_name, :model_version,
                :recommended_action, :input_data_as_of, :data_origin, 'ACTIVE'
            )
            RETURNING id
        """)
        result = db.execute(insert_sql, {
            "zone_id": zone_id,
            "predicted_at": now,
            "horizon_minutes": HORIZON_MINUTES,
            "flood_risk_level": flood_risk_level,
            "landslide_risk_level": landslide_risk_level,
            "overall_risk_level": overall_risk_level,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "recommended_action": recommended_action,
            "input_data_as_of": input_data_as_of,
            "data_origin": data_origin,
        })
        new_pred_id = result.scalar_one()

        # Insert risk explanations
        for expl in explanations:
            expl_sql = text("""
                INSERT INTO risk_explanations (
                    risk_prediction_id, factor_name, factor_value, unit,
                    contribution, explanation_text, display_order
                ) VALUES (
                    :pred_id, :factor_name, :factor_value, :unit,
                    :contribution, :explanation_text, :display_order
                )
            """)
            db.execute(expl_sql, {
                "pred_id": new_pred_id,
                "factor_name": expl["factor_name"],
                "factor_value": expl["factor_value"],
                "unit": expl["unit"],
                "contribution": expl["contribution"],
                "explanation_text": expl["explanation_text"],
                "display_order": expl["display_order"],
            })

        db.commit()
        logger.info(
            f"Zone {zone_id}: new prediction #{new_pred_id} "
            f"overall={overall_risk_level} flood={flood_risk_level} landslide={landslide_risk_level} "
            f"origin={data_origin}"
        )
        return new_pred_id

    except Exception:
        db.rollback()
        logger.exception(f"Zone {zone_id}: failed to write prediction")
        raise


def run_all_zones(db: Session) -> dict:
    """Run the risk engine for all ACTIVE zones. Returns summary."""
    zones = db.execute(text("SELECT id, name FROM zones WHERE status = 'ACTIVE'")).mappings().all()
    
    results = {"computed": 0, "skipped": 0, "errors": 0, "details": []}
    for zone in zones:
        try:
            pred_id = compute_zone_risk(db, zone["id"])
            if pred_id:
                results["computed"] += 1
                results["details"].append({"zone_id": zone["id"], "zone_name": zone["name"], "prediction_id": pred_id})
            else:
                results["skipped"] += 1
                results["details"].append({"zone_id": zone["id"], "zone_name": zone["name"], "skipped": True})
        except Exception as e:
            results["errors"] += 1
            results["details"].append({"zone_id": zone["id"], "zone_name": zone["name"], "error": str(e)})
            logger.exception(f"Zone {zone['id']} ({zone['name']}): engine error")
    
    return results
