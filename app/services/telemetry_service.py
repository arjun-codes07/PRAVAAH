"""Telemetry ingestion service resolving sensor nodes, deriving rates, and updating last_seen_at in one transaction."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.models.tables import SensorNode, Observation
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse

logger = logging.getLogger("pravaah.telemetry")

def ingest_telemetry(db: Session, payload: TelemetryIngestRequest) -> TelemetryIngestResponse:
    """Ingest sensor telemetry payload, resolve node metadata, compute water_level_rate_m_per_h, insert observation, and update last_seen_at in one transaction."""
    # 1. Resolve sensor node by node_id
    sensor = db.query(SensorNode).filter(SensorNode.node_id == payload.node_id).first()
    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor node '{payload.node_id}' not found",
        )

    # 2. Check for duplicate (sensor_node_id, observed_at)
    dup_check = db.query(Observation).filter(
        Observation.sensor_node_id == sensor.id,
        Observation.observed_at == payload.timestamp,
    ).first()
    if dup_check:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Observation for sensor '{payload.node_id}' at timestamp {payload.timestamp.isoformat()} already exists",
        )

    # 3. Derive water_level_rate_m_per_h from previous observation
    water_rate = None
    if payload.water_level is not None:
        prev_obs = (
            db.query(Observation)
            .filter(
                Observation.sensor_node_id == sensor.id,
                Observation.observed_at < payload.timestamp,
                Observation.water_level_m.isnot(None),
            )
            .order_by(Observation.observed_at.desc())
            .first()
        )
        if prev_obs and prev_obs.water_level_m is not None:
            delta_hours = (payload.timestamp - prev_obs.observed_at).total_seconds() / 3600.0
            if delta_hours > 0:
                water_rate = (payload.water_level - float(prev_obs.water_level_m)) / delta_hours

    now_utc = datetime.now(timezone.utc)

    # 4. Insert observation & update sensor.last_seen_at in ONE transaction
    try:
        obs = Observation(
            sensor_node_id=sensor.id,
            data_source_id=sensor.data_source_id,
            zone_id=sensor.zone_id,
            location_id=sensor.location_id,
            observed_at=payload.timestamp,
            ingested_at=now_utc,
            rainfall_1h_mm=payload.rainfall_1h,
            soil_moisture_pct=payload.soil_moisture,
            water_level_m=payload.water_level,
            water_level_rate_m_per_h=water_rate,
            slope_angle_deg=payload.slope_angle,
            temperature_c=payload.temperature,
            humidity_pct=payload.humidity,
            quality_status="VALID",
            data_origin=payload.data_origin,
        )
        db.add(obs)

        # Update last_seen_at if payload timestamp is greater than current last_seen_at
        if sensor.last_seen_at is None or payload.timestamp > sensor.last_seen_at:
            sensor.last_seen_at = payload.timestamp

        db.commit()
        db.refresh(obs)

        # APPLIED DEFAULT trigger: recompute zone risk after successful ingest.
        # Best-effort: engine errors are logged but do NOT fail the ingestion response.
        try:
            from app.services.risk_engine import compute_zone_risk
            compute_zone_risk(db, sensor.zone_id)
        except Exception:
            logger.exception(f"Risk engine trigger failed for zone {sensor.zone_id} after ingest (best-effort)")

        return TelemetryIngestResponse(
            observation_id=obs.id,
            quality_status=obs.quality_status,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate observation or integrity conflict: {str(exc.orig)}",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}",
        )
