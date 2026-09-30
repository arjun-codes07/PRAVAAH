"""Unit and integration tests for PRAVAAH Risk Engine."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import SessionLocal
from app.services.risk_config import (
    score_to_level,
    metric_to_score,
    FLOOD_THRESHOLDS,
    LANDSLIDE_THRESHOLDS,
)
from app.services.risk_engine import (
    _worst_origin,
    compute_zone_risk,
    run_all_zones,
)
from app.models.tables import RiskPrediction, RiskExplanation, Observation, SensorNode, Zone


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_score_to_level():
    """Verify numeric risk score (0-3 scale) correctly maps to categorical risk levels."""
    assert score_to_level(0.0) == "LOW"
    assert score_to_level(0.85) == "LOW"
    assert score_to_level(1.0) == "MODERATE"
    assert score_to_level(1.75) == "MODERATE"
    assert score_to_level(2.0) == "HIGH"
    assert score_to_level(2.65) == "HIGH"
    assert score_to_level(3.0) == "CRITICAL"
    assert score_to_level(3.5) == "CRITICAL"


def test_metric_to_score_rainfall():
    """Verify rainfall metric maps to normalized score based on thresholds."""
    # Thresholds: MODERATE=15.0, HIGH=35.0, CRITICAL=65.0
    assert metric_to_score(0.0, FLOOD_THRESHOLDS["rainfall_1h_mm"]) == 0.0
    score_low = metric_to_score(5.0, FLOOD_THRESHOLDS["rainfall_1h_mm"])
    assert score_to_level(score_low) == "LOW"
    score_mod = metric_to_score(20.0, FLOOD_THRESHOLDS["rainfall_1h_mm"])
    assert score_to_level(score_mod) == "MODERATE"
    score_high = metric_to_score(40.0, FLOOD_THRESHOLDS["rainfall_1h_mm"])
    assert score_to_level(score_high) == "HIGH"
    score_crit = metric_to_score(70.0, FLOOD_THRESHOLDS["rainfall_1h_mm"])
    assert score_to_level(score_crit) == "CRITICAL"


def test_worst_origin():
    """Verify data origin priority: SIMULATED is least trusted, REAL is most trusted."""
    assert _worst_origin("REAL", "REAL") == "REAL"
    assert _worst_origin("REAL", "REPLAYED") == "REPLAYED"
    assert _worst_origin("REAL", "SIMULATED") == "SIMULATED"
    assert _worst_origin("REPLAYED", "SIMULATED") == "SIMULATED"
    assert _worst_origin("SIMULATED", "SIMULATED") == "SIMULATED"


def test_compute_zone_risk_supersede_and_origin(db: Session):
    """Verify compute_zone_risk creates an ACTIVE prediction, supersedes the previous,

    and populates risk explanations.
    """
    # Zone 1 is Mandi Town Core
    zone = db.query(Zone).filter(Zone.id == 1).first()
    assert zone is not None

    # Find previous active prediction count
    prev_active = db.query(RiskPrediction).filter(
        RiskPrediction.zone_id == 1,
        RiskPrediction.status == "ACTIVE"
    ).first()

    # Ensure sensor HP-MANDI-001 has recent last_seen_at so it's not skipped as stale
    sensor = db.query(SensorNode).filter(SensorNode.zone_id == 1).first()
    assert sensor is not None
    now_utc = datetime.now(timezone.utc)
    sensor.last_seen_at = now_utc
    db.commit()

    # Insert a valid recent observation
    obs = Observation(
        sensor_node_id=sensor.id,
        data_source_id=sensor.data_source_id,
        zone_id=1,
        location_id=sensor.location_id,
        observed_at=now_utc - timedelta(minutes=2),
        ingested_at=now_utc - timedelta(minutes=2),
        rainfall_1h_mm=Decimal("15.5"),
        soil_moisture_pct=Decimal("45.0"),
        water_level_m=Decimal("2.1"),
        water_level_rate_m_per_h=Decimal("0.1"),
        slope_angle_deg=Decimal("12.0"),
        temperature_c=Decimal("22.0"),
        humidity_pct=Decimal("80.0"),
        quality_status="VALID",
        data_origin="SIMULATED",
    )
    db.add(obs)
    db.commit()

    # Run risk engine for Zone 1
    new_pred_id = compute_zone_risk(db, 1)
    assert new_pred_id is not None

    # Verify new prediction is ACTIVE
    new_pred = db.query(RiskPrediction).filter(RiskPrediction.id == new_pred_id).first()
    assert new_pred is not None
    assert new_pred.status == "ACTIVE"
    assert new_pred.model_name == "demo-rule-baseline"
    assert new_pred.data_origin == "SIMULATED"

    # Verify previous active prediction is now SUPERSEDED
    if prev_active and prev_active.id != new_pred_id:
        db.refresh(prev_active)
        assert prev_active.status == "SUPERSEDED"

    # Verify risk explanations were created and ordered by display_order
    exps = db.query(RiskExplanation).filter(
        RiskExplanation.risk_prediction_id == new_pred_id
    ).order_by(RiskExplanation.display_order.asc()).all()

    assert len(exps) >= 3
    # Check explanations have required text and valid factor contributions
    for exp in exps:
        assert exp.factor_name is not None
        assert exp.contribution is not None
        assert exp.explanation_text is not None


def test_escalation_changes_prediction(db: Session):
    """Verify that severe rainfall values escalate risk level to HIGH or CRITICAL."""
    sensor = db.query(SensorNode).filter(SensorNode.zone_id == 1).first()
    now_utc = datetime.now(timezone.utc)
    sensor.last_seen_at = now_utc
    db.commit()

    # Extreme rainfall observation
    obs = Observation(
        sensor_node_id=sensor.id,
        data_source_id=sensor.data_source_id,
        zone_id=1,
        location_id=sensor.location_id,
        observed_at=now_utc - timedelta(minutes=1),
        ingested_at=now_utc - timedelta(minutes=1),
        rainfall_1h_mm=Decimal("75.0"),  # > 50mm extreme threshold
        soil_moisture_pct=Decimal("88.0"),
        water_level_m=Decimal("5.5"),
        water_level_rate_m_per_h=Decimal("1.2"),
        slope_angle_deg=Decimal("12.0"),
        temperature_c=Decimal("19.0"),
        humidity_pct=Decimal("95.0"),
        quality_status="VALID",
        data_origin="SIMULATED",
    )
    db.add(obs)
    db.commit()

    pred_id = compute_zone_risk(db, 1)
    assert pred_id is not None
    pred = db.query(RiskPrediction).filter(RiskPrediction.id == pred_id).first()
    assert pred.overall_risk_level in ("HIGH", "CRITICAL")
