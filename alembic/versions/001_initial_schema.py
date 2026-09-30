"""001 — PostGIS extension, all 19 tables, constraints, indexes, triggers.

Implements SPEC sections 1-7 exactly.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ====================================================================
    # STAGE 1: PostGIS extension  (SPEC §1)
    # ====================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ====================================================================
    # UPDATED_AT TRIGGER FUNCTION
    # Choice: trigger (documented in DATABASE_SETUP.md)
    # ====================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # ====================================================================
    # STAGE 3: TABLES + PKs + FKs  (SPEC §2, §3, §4)
    # Table order per SPEC §15.4
    # ====================================================================

    # --- 1. roles ---
    op.execute("""
        CREATE TABLE roles (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name        varchar(50)  NOT NULL,
            description text,
            permissions text[]       NOT NULL DEFAULT '{}',
            created_at  timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 2. authorities ---
    op.execute("""
        CREATE TABLE authorities (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name            varchar(150) NOT NULL,
            authority_type  varchar(50)  NOT NULL,
            region_scope    text,
            status          varchar(20)  NOT NULL DEFAULT 'ACTIVE',
            created_at      timestamptz  NOT NULL DEFAULT now(),
            updated_at      timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 3. users ---
    op.execute("""
        CREATE TABLE users (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name          varchar(120) NOT NULL,
            email         varchar(255) NOT NULL,
            password_hash text         NOT NULL,
            role_id       bigint       NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            authority_id  bigint       REFERENCES authorities(id) ON DELETE RESTRICT,
            status        varchar(20)  NOT NULL DEFAULT 'ACTIVE',
            created_at    timestamptz  NOT NULL DEFAULT now(),
            updated_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 4. zones ---
    op.execute("""
        CREATE TABLE zones (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            authority_id  bigint       REFERENCES authorities(id) ON DELETE RESTRICT,
            name          varchar(150) NOT NULL,
            zone_type     varchar(50)  NOT NULL,
            admin_code    varchar(50),
            geom          geometry(MultiPolygon, 4326) NOT NULL,
            status        varchar(20)  NOT NULL DEFAULT 'ACTIVE',
            created_at    timestamptz  NOT NULL DEFAULT now(),
            updated_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 5. locations ---
    op.execute("""
        CREATE TABLE locations (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            zone_id       bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            name          varchar(150) NOT NULL,
            location_type varchar(50)  NOT NULL,
            admin_code    varchar(50),
            geom          geometry(Point, 4326) NOT NULL,
            created_at    timestamptz  NOT NULL DEFAULT now(),
            updated_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 6. data_sources ---
    op.execute("""
        CREATE TABLE data_sources (
            id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name                varchar(150) NOT NULL,
            source_type         varchar(30)  NOT NULL,
            provider            varchar(150),
            description         text,
            data_origin         varchar(10)  NOT NULL,
            status              varchar(20)  NOT NULL DEFAULT 'ACTIVE',
            stale_after_minutes integer,
            provenance_notes    text,
            created_at          timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 7. sensor_nodes ---
    op.execute("""
        CREATE TABLE sensor_nodes (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            node_id         varchar(64)  NOT NULL,
            data_source_id  bigint       NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
            zone_id         bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id     bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            sensor_type     varchar(50)  NOT NULL,
            geom            geometry(Point, 4326) NOT NULL,
            data_origin     varchar(10)  NOT NULL,
            status          varchar(20)  NOT NULL DEFAULT 'ACTIVE',
            last_seen_at    timestamptz,
            created_at      timestamptz  NOT NULL DEFAULT now(),
            updated_at      timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 8. observations (no created_at — uses ingested_at) ---
    op.execute("""
        CREATE TABLE observations (
            id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sensor_node_id           bigint       REFERENCES sensor_nodes(id) ON DELETE RESTRICT,
            data_source_id           bigint       NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
            zone_id                  bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id              bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            observed_at              timestamptz  NOT NULL,
            ingested_at              timestamptz  NOT NULL DEFAULT now(),
            rainfall_1h_mm           numeric(7,2),
            soil_moisture_pct        numeric(5,2),
            water_level_m            numeric(7,3),
            water_level_rate_m_per_h numeric(7,3),
            slope_angle_deg          numeric(5,2),
            temperature_c            numeric(5,2),
            humidity_pct             numeric(5,2),
            quality_status           varchar(10)  NOT NULL DEFAULT 'VALID',
            data_origin              varchar(10)  NOT NULL
        )
    """)

    # --- 9. terrain_features ---
    op.execute("""
        CREATE TABLE terrain_features (
            id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            zone_id               bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id           bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            elevation_m           numeric(7,2),
            slope_deg             numeric(5,2),
            susceptibility_score  numeric(4,3),
            data_source_id        bigint       NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
            data_origin           varchar(10)  NOT NULL,
            created_at            timestamptz  NOT NULL DEFAULT now(),
            updated_at            timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 10. historical_events ---
    op.execute("""
        CREATE TABLE historical_events (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            hazard_type     varchar(10)  NOT NULL,
            zone_id         bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id     bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            event_time      timestamptz  NOT NULL,
            severity        varchar(10),
            description     text,
            affected_area   geometry(MultiPolygon, 4326),
            data_source_id  bigint       NOT NULL REFERENCES data_sources(id) ON DELETE RESTRICT,
            data_origin     varchar(10)  NOT NULL,
            created_at      timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 11. risk_predictions ---
    op.execute("""
        CREATE TABLE risk_predictions (
            id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            zone_id                 bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id             bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            predicted_at            timestamptz  NOT NULL,
            horizon_minutes         integer      NOT NULL,
            flood_probability       numeric(5,4),
            landslide_probability   numeric(5,4),
            flood_risk_level        varchar(10),
            landslide_risk_level    varchar(10),
            overall_risk_level      varchar(10)  NOT NULL,
            confidence              numeric(5,4),
            model_name              varchar(100) NOT NULL,
            model_version           varchar(50)  NOT NULL,
            recommended_action      text,
            input_data_as_of        timestamptz,
            data_origin             varchar(10)  NOT NULL,
            status                  varchar(12)  NOT NULL DEFAULT 'ACTIVE',
            created_at              timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 12. risk_explanations ---
    op.execute("""
        CREATE TABLE risk_explanations (
            id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            risk_prediction_id  bigint       NOT NULL REFERENCES risk_predictions(id) ON DELETE CASCADE,
            factor_name         varchar(100) NOT NULL,
            factor_value        numeric(12,4),
            unit                varchar(20),
            contribution        numeric(6,4),
            explanation_text    text         NOT NULL,
            display_order       smallint     NOT NULL DEFAULT 1,
            created_at          timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 13. incidents ---
    op.execute("""
        CREATE TABLE incidents (
            id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            zone_id               bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id           bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            geom                  geometry(Point, 4326),
            incident_type         varchar(10)  NOT NULL,
            severity              varchar(10)  NOT NULL,
            status                varchar(15)  NOT NULL DEFAULT 'OPEN',
            description           text,
            source_prediction_id  bigint       REFERENCES risk_predictions(id) ON DELETE SET NULL,
            started_at            timestamptz  NOT NULL,
            resolved_at           timestamptz,
            created_by            bigint       REFERENCES users(id) ON DELETE RESTRICT,
            data_origin           varchar(10)  NOT NULL,
            created_at            timestamptz  NOT NULL DEFAULT now(),
            updated_at            timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 14. alerts ---
    op.execute("""
        CREATE TABLE alerts (
            id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            zone_id               bigint       NOT NULL REFERENCES zones(id) ON DELETE RESTRICT,
            location_id           bigint       REFERENCES locations(id) ON DELETE RESTRICT,
            alert_type            varchar(10)  NOT NULL,
            severity              varchar(10)  NOT NULL,
            message               text         NOT NULL,
            incident_id           bigint       REFERENCES incidents(id) ON DELETE RESTRICT,
            source_prediction_id  bigint       REFERENCES risk_predictions(id) ON DELETE RESTRICT,
            status                varchar(15)  NOT NULL DEFAULT 'ACTIVE',
            issued_at             timestamptz  NOT NULL DEFAULT now(),
            expires_at            timestamptz,
            issued_by             bigint       REFERENCES users(id) ON DELETE RESTRICT,
            acknowledged_at       timestamptz,
            acknowledged_by       bigint       REFERENCES users(id) ON DELETE RESTRICT,
            data_origin           varchar(10)  NOT NULL,
            created_at            timestamptz  NOT NULL DEFAULT now(),
            updated_at            timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 15. rescue_teams ---
    op.execute("""
        CREATE TABLE rescue_teams (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            authority_id  bigint       NOT NULL REFERENCES authorities(id) ON DELETE RESTRICT,
            name          varchar(150) NOT NULL,
            team_type     varchar(50)  NOT NULL,
            status        varchar(15)  NOT NULL DEFAULT 'AVAILABLE',
            geom          geometry(Point, 4326),
            created_at    timestamptz  NOT NULL DEFAULT now(),
            updated_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 16. rescue_resources ---
    op.execute("""
        CREATE TABLE rescue_resources (
            id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            authority_id    bigint       NOT NULL REFERENCES authorities(id) ON DELETE RESTRICT,
            team_id         bigint       REFERENCES rescue_teams(id) ON DELETE RESTRICT,
            resource_type   varchar(50)  NOT NULL,
            name            varchar(150) NOT NULL,
            quantity        integer      NOT NULL DEFAULT 1,
            status          varchar(15)  NOT NULL DEFAULT 'AVAILABLE',
            geom            geometry(Point, 4326),
            created_at      timestamptz  NOT NULL DEFAULT now(),
            updated_at      timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 17. response_actions ---
    op.execute("""
        CREATE TABLE response_actions (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            incident_id   bigint       NOT NULL REFERENCES incidents(id) ON DELETE RESTRICT,
            action_type   varchar(50)  NOT NULL,
            status        varchar(15)  NOT NULL DEFAULT 'PLANNED',
            priority      varchar(10)  NOT NULL,
            started_at    timestamptz,
            completed_at  timestamptz,
            notes         text,
            created_by    bigint       REFERENCES users(id) ON DELETE RESTRICT,
            created_at    timestamptz  NOT NULL DEFAULT now(),
            updated_at    timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # --- 18. response_assignments (no created_at — uses assigned_at) ---
    op.execute("""
        CREATE TABLE response_assignments (
            id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            response_action_id  bigint       NOT NULL REFERENCES response_actions(id) ON DELETE CASCADE,
            team_id             bigint       REFERENCES rescue_teams(id) ON DELETE RESTRICT,
            resource_id         bigint       REFERENCES rescue_resources(id) ON DELETE RESTRICT,
            status              varchar(10)  NOT NULL DEFAULT 'ASSIGNED',
            assigned_at         timestamptz  NOT NULL DEFAULT now(),
            released_at         timestamptz,
            assigned_by         bigint       REFERENCES users(id) ON DELETE RESTRICT
        )
    """)

    # --- 19. audit_logs ---
    op.execute("""
        CREATE TABLE audit_logs (
            id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id     bigint       REFERENCES users(id) ON DELETE RESTRICT,
            action      varchar(50)  NOT NULL,
            entity_type varchar(50)  NOT NULL,
            entity_id   bigint,
            metadata    jsonb,
            created_at  timestamptz  NOT NULL DEFAULT now()
        )
    """)

    # ====================================================================
    # UPDATED_AT TRIGGERS — applied to all (u) tables per SPEC §3
    # ====================================================================
    _updated_at_tables = [
        "authorities", "users", "zones", "locations",
        "sensor_nodes", "terrain_features",
        "incidents", "alerts", "response_actions",
        "rescue_teams", "rescue_resources",
    ]
    for tbl in _updated_at_tables:
        op.execute(f"""
            CREATE TRIGGER trg_{tbl}_updated_at
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """)

    # ====================================================================
    # STAGE 4: CONSTRAINTS  (SPEC §5)
    # ====================================================================

    # --- Controlled-value CHECKs ---

    # data_origin on ALL tables that have it
    for tbl in [
        "data_sources", "sensor_nodes", "observations",
        "terrain_features", "historical_events", "risk_predictions",
        "incidents", "alerts",
    ]:
        op.execute(f"""
            ALTER TABLE {tbl} ADD CONSTRAINT chk_{tbl}_data_origin
            CHECK (data_origin IN ('REAL','SIMULATED','REPLAYED'))
        """)

    # Level checks: *_risk_level, severity, priority  → L = LOW, MODERATE, HIGH, CRITICAL
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_flood_risk_level
        CHECK (flood_risk_level IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_landslide_risk_level
        CHECK (landslide_risk_level IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_overall_risk_level
        CHECK (overall_risk_level IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE historical_events ADD CONSTRAINT chk_he_severity
        CHECK (severity IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE incidents ADD CONSTRAINT chk_inc_severity
        CHECK (severity IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE alerts ADD CONSTRAINT chk_alt_severity
        CHECK (severity IN ('LOW','MODERATE','HIGH','CRITICAL'))""")
    op.execute("""ALTER TABLE response_actions ADD CONSTRAINT chk_ra_priority
        CHECK (priority IN ('LOW','MODERATE','HIGH','CRITICAL'))""")

    # Status checks per table
    op.execute("""ALTER TABLE authorities ADD CONSTRAINT chk_auth_status
        CHECK (status IN ('ACTIVE','INACTIVE'))""")
    op.execute("""ALTER TABLE zones ADD CONSTRAINT chk_zones_status
        CHECK (status IN ('ACTIVE','INACTIVE'))""")
    op.execute("""ALTER TABLE data_sources ADD CONSTRAINT chk_ds_status
        CHECK (status IN ('ACTIVE','INACTIVE'))""")
    op.execute("""ALTER TABLE users ADD CONSTRAINT chk_users_status
        CHECK (status IN ('ACTIVE','DISABLED'))""")
    op.execute("""ALTER TABLE sensor_nodes ADD CONSTRAINT chk_sn_status
        CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE'))""")
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_quality_status
        CHECK (quality_status IN ('VALID','SUSPECT','INVALID'))""")
    op.execute("""ALTER TABLE historical_events ADD CONSTRAINT chk_he_hazard_type
        CHECK (hazard_type IN ('FLOOD','LANDSLIDE'))""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_status
        CHECK (status IN ('ACTIVE','SUPERSEDED'))""")
    op.execute("""ALTER TABLE incidents ADD CONSTRAINT chk_inc_incident_type
        CHECK (incident_type IN ('FLOOD','LANDSLIDE','OTHER'))""")
    op.execute("""ALTER TABLE incidents ADD CONSTRAINT chk_inc_status
        CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED'))""")
    op.execute("""ALTER TABLE alerts ADD CONSTRAINT chk_alt_alert_type
        CHECK (alert_type IN ('FLOOD','LANDSLIDE','OTHER'))""")
    op.execute("""ALTER TABLE alerts ADD CONSTRAINT chk_alt_status
        CHECK (status IN ('ACTIVE','ACKNOWLEDGED','CANCELLED'))""")
    op.execute("""ALTER TABLE response_actions ADD CONSTRAINT chk_ra_status
        CHECK (status IN ('PLANNED','IN_PROGRESS','COMPLETED','CANCELLED'))""")
    op.execute("""ALTER TABLE rescue_teams ADD CONSTRAINT chk_rt_status
        CHECK (status IN ('AVAILABLE','DEPLOYED','UNAVAILABLE'))""")
    op.execute("""ALTER TABLE rescue_resources ADD CONSTRAINT chk_rr_status
        CHECK (status IN ('AVAILABLE','DEPLOYED','UNAVAILABLE'))""")
    op.execute("""ALTER TABLE response_assignments ADD CONSTRAINT chk_rasgn_status
        CHECK (status IN ('ASSIGNED','DEPLOYED','RELEASED'))""")

    # Source type
    op.execute("""ALTER TABLE data_sources ADD CONSTRAINT chk_ds_source_type
        CHECK (source_type IN ('IOT_TELEMETRY','EXTERNAL_DATASET','HISTORICAL_RECORD'))""")

    # --- Uniqueness constraints ---
    op.execute("ALTER TABLE roles ADD CONSTRAINT uq_roles_name UNIQUE (name)")
    op.execute("ALTER TABLE authorities ADD CONSTRAINT uq_authorities_name UNIQUE (name)")
    op.execute("ALTER TABLE data_sources ADD CONSTRAINT uq_data_sources_name UNIQUE (name)")
    op.execute("ALTER TABLE sensor_nodes ADD CONSTRAINT uq_sensor_nodes_node_id UNIQUE (node_id)")
    op.execute("""ALTER TABLE risk_explanations ADD CONSTRAINT uq_re_prediction_factor
        UNIQUE (risk_prediction_id, factor_name)""")
    op.execute("""ALTER TABLE rescue_teams ADD CONSTRAINT uq_rt_authority_name
        UNIQUE (authority_id, name)""")
    op.execute("""ALTER TABLE rescue_resources ADD CONSTRAINT uq_rr_authority_name
        UNIQUE (authority_id, name)""")
    # users lower(email) — done as expression index below

    # --- Range checks ---
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_soil_moisture_range
        CHECK (soil_moisture_pct >= 0 AND soil_moisture_pct <= 100)""")
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_humidity_range
        CHECK (humidity_pct >= 0 AND humidity_pct <= 100)""")
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_rainfall_range
        CHECK (rainfall_1h_mm >= 0)""")
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_slope_angle_range
        CHECK (slope_angle_deg >= 0 AND slope_angle_deg <= 90)""")
    op.execute("""ALTER TABLE terrain_features ADD CONSTRAINT chk_tf_slope_deg_range
        CHECK (slope_deg >= 0 AND slope_deg <= 90)""")
    op.execute("""ALTER TABLE terrain_features ADD CONSTRAINT chk_tf_susceptibility_range
        CHECK (susceptibility_score >= 0 AND susceptibility_score <= 1)""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_flood_prob_range
        CHECK (flood_probability >= 0 AND flood_probability <= 1)""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_landslide_prob_range
        CHECK (landslide_probability >= 0 AND landslide_probability <= 1)""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1)""")
    op.execute("""ALTER TABLE risk_predictions ADD CONSTRAINT chk_rp_horizon_positive
        CHECK (horizon_minutes > 0)""")
    op.execute("""ALTER TABLE data_sources ADD CONSTRAINT chk_ds_stale_after_positive
        CHECK (stale_after_minutes > 0)""")
    op.execute("""ALTER TABLE rescue_resources ADD CONSTRAINT chk_rr_quantity_positive
        CHECK (quantity > 0)""")

    # --- Row-level rules ---

    # zones: ST_IsValid(geom)
    op.execute("""ALTER TABLE zones ADD CONSTRAINT chk_zones_geom_valid
        CHECK (ST_IsValid(geom))""")

    # data_sources: REAL requires provenance_notes
    op.execute("""ALTER TABLE data_sources ADD CONSTRAINT chk_ds_real_provenance
        CHECK (data_origin <> 'REAL' OR provenance_notes IS NOT NULL)""")

    # observations: at least one measurement
    op.execute("""ALTER TABLE observations ADD CONSTRAINT chk_obs_at_least_one_measurement
        CHECK (num_nonnulls(
            rainfall_1h_mm, soil_moisture_pct, water_level_m,
            water_level_rate_m_per_h, slope_angle_deg, temperature_c, humidity_pct
        ) >= 1)""")

    # incidents: resolved_at consistency
    op.execute("""ALTER TABLE incidents ADD CONSTRAINT chk_inc_resolved_consistency
        CHECK ((status = 'RESOLVED') = (resolved_at IS NOT NULL))""")
    op.execute("""ALTER TABLE incidents ADD CONSTRAINT chk_inc_resolved_after_started
        CHECK (resolved_at >= started_at)""")

    # alerts: expires_at > issued_at
    op.execute("""ALTER TABLE alerts ADD CONSTRAINT chk_alt_expires_after_issued
        CHECK (expires_at > issued_at)""")
    # alerts: acknowledged_at and acknowledged_by consistency
    op.execute("""ALTER TABLE alerts ADD CONSTRAINT chk_alt_ack_consistency
        CHECK ((acknowledged_at IS NULL) = (acknowledged_by IS NULL))""")

    # response_actions: completed_at >= started_at
    op.execute("""ALTER TABLE response_actions ADD CONSTRAINT chk_ra_completed_after_started
        CHECK (completed_at >= started_at)""")

    # response_assignments: exactly one of team_id or resource_id
    op.execute("""ALTER TABLE response_assignments ADD CONSTRAINT chk_rasgn_exactly_one
        CHECK (num_nonnulls(team_id, resource_id) = 1)""")

    # ====================================================================
    # STAGE 5: INDEXES  (SPEC §6)
    # ====================================================================

    # --- users ---
    op.execute("CREATE UNIQUE INDEX ix_users_lower_email ON users (lower(email))")
    op.execute("CREATE INDEX ix_users_authority_id ON users (authority_id)")

    # --- zones ---
    op.execute("CREATE INDEX ix_zones_geom ON zones USING GIST (geom)")
    op.execute("CREATE INDEX ix_zones_authority_id ON zones (authority_id)")
    op.execute("""CREATE UNIQUE INDEX ix_zones_admin_code
        ON zones (admin_code) WHERE admin_code IS NOT NULL""")

    # --- locations ---
    op.execute("CREATE INDEX ix_locations_geom ON locations USING GIST (geom)")
    op.execute("CREATE INDEX ix_locations_zone_id ON locations (zone_id)")

    # --- sensor_nodes ---
    op.execute("CREATE INDEX ix_sensor_nodes_geom ON sensor_nodes USING GIST (geom)")
    op.execute("CREATE INDEX ix_sensor_nodes_zone_id ON sensor_nodes (zone_id)")
    op.execute("CREATE INDEX ix_sensor_nodes_data_source_id ON sensor_nodes (data_source_id)")
    op.execute("CREATE INDEX ix_sensor_nodes_status ON sensor_nodes (status)")

    # --- observations ---
    op.execute("""CREATE UNIQUE INDEX ix_obs_sensor_observed
        ON observations (sensor_node_id, observed_at)
        WHERE sensor_node_id IS NOT NULL""")
    op.execute("""CREATE INDEX ix_obs_zone_observed
        ON observations (zone_id, observed_at DESC)""")
    op.execute("""CREATE INDEX ix_obs_source_observed
        ON observations (data_source_id, observed_at DESC)""")
    # BRIN index on observed_at — optional P2, creating (trivial)
    op.execute("""CREATE INDEX ix_obs_observed_at_brin
        ON observations USING BRIN (observed_at)""")

    # --- terrain_features ---
    op.execute("""CREATE UNIQUE INDEX ix_tf_zone_only
        ON terrain_features (zone_id) WHERE location_id IS NULL""")
    op.execute("""CREATE UNIQUE INDEX ix_tf_location_only
        ON terrain_features (location_id) WHERE location_id IS NOT NULL""")

    # --- historical_events ---
    op.execute("""CREATE INDEX ix_he_zone_hazard_time
        ON historical_events (zone_id, hazard_type, event_time DESC)""")
    op.execute("""CREATE INDEX ix_he_affected_area
        ON historical_events USING GIST (affected_area)
        WHERE affected_area IS NOT NULL""")

    # --- risk_predictions ---
    op.execute("""CREATE INDEX ix_rp_zone_predicted
        ON risk_predictions (zone_id, predicted_at DESC)""")
    op.execute("""CREATE UNIQUE INDEX ix_rp_active_per_zone_loc
        ON risk_predictions (zone_id, COALESCE(location_id, 0))
        WHERE status = 'ACTIVE'""")
    op.execute("""CREATE INDEX ix_rp_dashboard_high_risk
        ON risk_predictions (overall_risk_level, predicted_at DESC)
        WHERE status = 'ACTIVE'""")

    # --- risk_explanations ---
    op.execute("""CREATE INDEX ix_re_prediction_order
        ON risk_explanations (risk_prediction_id, display_order)""")

    # --- incidents ---
    op.execute("CREATE INDEX ix_inc_status_severity ON incidents (status, severity)")
    op.execute("""CREATE INDEX ix_inc_zone_started
        ON incidents (zone_id, started_at DESC)""")
    op.execute("""CREATE INDEX ix_inc_source_prediction
        ON incidents (source_prediction_id)""")
    op.execute("""CREATE INDEX ix_inc_geom
        ON incidents USING GIST (geom) WHERE geom IS NOT NULL""")

    # --- alerts ---
    op.execute("""CREATE INDEX ix_alt_status_severity_issued
        ON alerts (status, severity, issued_at DESC)""")
    op.execute("""CREATE INDEX ix_alt_zone_issued
        ON alerts (zone_id, issued_at DESC)""")
    op.execute("CREATE INDEX ix_alt_incident_id ON alerts (incident_id)")
    op.execute("CREATE INDEX ix_alt_source_prediction ON alerts (source_prediction_id)")

    # --- response_actions ---
    op.execute("CREATE INDEX ix_ra_incident_id ON response_actions (incident_id)")
    op.execute("CREATE INDEX ix_ra_status ON response_actions (status)")

    # --- rescue_teams ---
    op.execute("CREATE INDEX ix_rt_status ON rescue_teams (status)")
    op.execute("""CREATE INDEX ix_rt_geom
        ON rescue_teams USING GIST (geom) WHERE geom IS NOT NULL""")

    # --- rescue_resources ---
    op.execute("CREATE INDEX ix_rr_status ON rescue_resources (status)")
    op.execute("""CREATE INDEX ix_rr_geom
        ON rescue_resources USING GIST (geom) WHERE geom IS NOT NULL""")

    # --- response_assignments ---
    op.execute("""CREATE INDEX ix_rasgn_action_id
        ON response_assignments (response_action_id)""")
    op.execute("""CREATE UNIQUE INDEX ix_rasgn_resource_active
        ON response_assignments (resource_id)
        WHERE status <> 'RELEASED' AND resource_id IS NOT NULL""")
    op.execute("""CREATE UNIQUE INDEX ix_rasgn_team_active
        ON response_assignments (team_id)
        WHERE status <> 'RELEASED' AND team_id IS NOT NULL""")

    # --- audit_logs ---
    op.execute("""CREATE INDEX ix_al_entity
        ON audit_logs (entity_type, entity_id, created_at DESC)""")
    op.execute("""CREATE INDEX ix_al_user
        ON audit_logs (user_id, created_at DESC)""")


def downgrade() -> None:
    # Drop all tables in reverse dependency order
    _tables = [
        "audit_logs",
        "response_assignments",
        "rescue_resources",
        "rescue_teams",
        "response_actions",
        "alerts",
        "incidents",
        "risk_explanations",
        "risk_predictions",
        "historical_events",
        "terrain_features",
        "observations",
        "sensor_nodes",
        "data_sources",
        "locations",
        "zones",
        "users",
        "authorities",
        "roles",
    ]
    for tbl in _tables:
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")

    # Drop PostGIS extension
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
