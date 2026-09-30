"""
PRAVAAH — All 19 approved table models.

Matches DATABASE_SPEC_FOR_ANTIGRAVITY.md sections 2–7 exactly.
Models are defined for Alembic autogenerate reference only.
All schema DDL is in the hand-written migrations.
"""

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.models.base import Base

# ---------------------------------------------------------------------------
# Shorthand
# ---------------------------------------------------------------------------
TS = TIMESTAMP(timezone=True)


def _id_col():
    """bigint PK GENERATED ALWAYS AS IDENTITY."""
    return Column(
        "id",
        BigInteger,
        primary_key=True,
        server_default=text("generated always as identity"),
        autoincrement=True,
    )


# ============================= IDENTITY =====================================

class Role(Base):
    __tablename__ = "roles"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(ARRAY(Text), nullable=False, server_default="{}")
    created_at = Column(TS, nullable=False, server_default=func.now())


class Authority(Base):
    __tablename__ = "authorities"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    authority_type = Column(String(50), nullable=False)
    region_scope = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(Text, nullable=False)
    role_id = Column(BigInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    authority_id = Column(BigInteger, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=True)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


# ============================= GEOGRAPHY ====================================

class Zone(Base):
    __tablename__ = "zones"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    authority_id = Column(BigInteger, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=True)
    name = Column(String(150), nullable=False)
    zone_type = Column(String(50), nullable=False)
    admin_code = Column(String(50), nullable=True)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class Location(Base):
    __tablename__ = "locations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(150), nullable=False)
    location_type = Column(String(50), nullable=False)
    admin_code = Column(String(50), nullable=True)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


# ============================= SENSING ======================================

class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    source_type = Column(String(30), nullable=False)
    provider = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    data_origin = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    stale_after_minutes = Column(Integer, nullable=True)
    provenance_notes = Column(Text, nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())


class SensorNode(Base):
    __tablename__ = "sensor_nodes"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_id = Column(String(64), nullable=False)
    data_source_id = Column(BigInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    sensor_type = Column(String(50), nullable=False)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    data_origin = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    last_seen_at = Column(TS, nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


# ============================= TIME-SERIES ==================================

class Observation(Base):
    __tablename__ = "observations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sensor_node_id = Column(BigInteger, ForeignKey("sensor_nodes.id", ondelete="RESTRICT"), nullable=True)
    data_source_id = Column(BigInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    observed_at = Column(TS, nullable=False)
    ingested_at = Column(TS, nullable=False, server_default=func.now())
    rainfall_1h_mm = Column(Numeric(7, 2), nullable=True)
    soil_moisture_pct = Column(Numeric(5, 2), nullable=True)
    water_level_m = Column(Numeric(7, 3), nullable=True)
    water_level_rate_m_per_h = Column(Numeric(7, 3), nullable=True)
    slope_angle_deg = Column(Numeric(5, 2), nullable=True)
    temperature_c = Column(Numeric(5, 2), nullable=True)
    humidity_pct = Column(Numeric(5, 2), nullable=True)
    quality_status = Column(String(10), nullable=False, server_default="VALID")
    data_origin = Column(String(10), nullable=False)
    # No created_at — uses ingested_at per SPEC


# ============================= TERRAIN ======================================

class TerrainFeature(Base):
    __tablename__ = "terrain_features"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    elevation_m = Column(Numeric(7, 2), nullable=True)
    slope_deg = Column(Numeric(5, 2), nullable=True)
    susceptibility_score = Column(Numeric(4, 3), nullable=True)
    data_source_id = Column(BigInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    data_origin = Column(String(10), nullable=False)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


# ============================= HISTORY ======================================

class HistoricalEvent(Base):
    __tablename__ = "historical_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    hazard_type = Column(String(10), nullable=False)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    event_time = Column(TS, nullable=False)
    severity = Column(String(10), nullable=True)
    description = Column(Text, nullable=True)
    affected_area = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    data_source_id = Column(BigInteger, ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False)
    data_origin = Column(String(10), nullable=False)
    created_at = Column(TS, nullable=False, server_default=func.now())


# ============================= RISK =========================================

class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    predicted_at = Column(TS, nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    flood_probability = Column(Numeric(5, 4), nullable=True)
    landslide_probability = Column(Numeric(5, 4), nullable=True)
    flood_risk_level = Column(String(10), nullable=True)
    landslide_risk_level = Column(String(10), nullable=True)
    overall_risk_level = Column(String(10), nullable=False)
    confidence = Column(Numeric(5, 4), nullable=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    recommended_action = Column(Text, nullable=True)
    input_data_as_of = Column(TS, nullable=True)
    data_origin = Column(String(10), nullable=False)
    status = Column(String(12), nullable=False, server_default="ACTIVE")
    created_at = Column(TS, nullable=False, server_default=func.now())


class RiskExplanation(Base):
    __tablename__ = "risk_explanations"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    risk_prediction_id = Column(BigInteger, ForeignKey("risk_predictions.id", ondelete="CASCADE"), nullable=False)
    factor_name = Column(String(100), nullable=False)
    factor_value = Column(Numeric(12, 4), nullable=True)
    unit = Column(String(20), nullable=True)
    contribution = Column(Numeric(6, 4), nullable=True)
    explanation_text = Column(Text, nullable=False)
    display_order = Column(SmallInteger, nullable=False, server_default="1")
    created_at = Column(TS, nullable=False, server_default=func.now())


# ============================= OPERATIONS ===================================

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    incident_type = Column(String(10), nullable=False)
    severity = Column(String(10), nullable=False)
    status = Column(String(15), nullable=False, server_default="OPEN")
    description = Column(Text, nullable=True)
    source_prediction_id = Column(BigInteger, ForeignKey("risk_predictions.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(TS, nullable=False)
    resolved_at = Column(TS, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    data_origin = Column(String(10), nullable=False)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(BigInteger, ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True)
    alert_type = Column(String(10), nullable=False)
    severity = Column(String(10), nullable=False)
    message = Column(Text, nullable=False)
    incident_id = Column(BigInteger, ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=True)
    source_prediction_id = Column(BigInteger, ForeignKey("risk_predictions.id", ondelete="RESTRICT"), nullable=True)
    status = Column(String(15), nullable=False, server_default="ACTIVE")
    issued_at = Column(TS, nullable=False, server_default=func.now())
    expires_at = Column(TS, nullable=True)
    issued_by = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    acknowledged_at = Column(TS, nullable=True)
    acknowledged_by = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    data_origin = Column(String(10), nullable=False)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class ResponseAction(Base):
    __tablename__ = "response_actions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    incident_id = Column(BigInteger, ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False)
    action_type = Column(String(50), nullable=False)
    status = Column(String(15), nullable=False, server_default="PLANNED")
    priority = Column(String(10), nullable=False)
    started_at = Column(TS, nullable=True)
    completed_at = Column(TS, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


# ============================= RESCUE =======================================

class RescueTeam(Base):
    __tablename__ = "rescue_teams"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    authority_id = Column(BigInteger, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(150), nullable=False)
    team_type = Column(String(50), nullable=False)
    status = Column(String(15), nullable=False, server_default="AVAILABLE")
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class RescueResource(Base):
    __tablename__ = "rescue_resources"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    authority_id = Column(BigInteger, ForeignKey("authorities.id", ondelete="RESTRICT"), nullable=False)
    team_id = Column(BigInteger, ForeignKey("rescue_teams.id", ondelete="RESTRICT"), nullable=True)
    resource_type = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    quantity = Column(Integer, nullable=False, server_default="1")
    status = Column(String(15), nullable=False, server_default="AVAILABLE")
    geom = Column(Geometry("POINT", srid=4326), nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())
    updated_at = Column(TS, nullable=False, server_default=func.now())


class ResponseAssignment(Base):
    __tablename__ = "response_assignments"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    response_action_id = Column(BigInteger, ForeignKey("response_actions.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(BigInteger, ForeignKey("rescue_teams.id", ondelete="RESTRICT"), nullable=True)
    resource_id = Column(BigInteger, ForeignKey("rescue_resources.id", ondelete="RESTRICT"), nullable=True)
    status = Column(String(10), nullable=False, server_default="ASSIGNED")
    assigned_at = Column(TS, nullable=False, server_default=func.now())
    released_at = Column(TS, nullable=True)
    assigned_by = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    # No created_at — uses assigned_at per SPEC


# ============================= AUDIT ========================================

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    action = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(BigInteger, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(TS, nullable=False, server_default=func.now())
