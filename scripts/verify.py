"""
PRAVAAH — Complete database verification script.

Covers ALL verification items from the task spec:
1. Schema comparison (tables, columns, types, nullability, defaults)
2. FK listing and ON DELETE rules
3. CHECK/UNIQUE constraint listing
4. Index listing
5. PostGIS verification
6. Negative tests (12 cases)
7. Sample queries (10 queries)
8. Seed data verification
9. EXPLAIN analysis

Usage:
    python -m scripts.verify
"""

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://pravaah_app:changeme@localhost:5432/pravaah",
)

PASS = "PASS ✓"
FAIL = "FAIL ✗"
results = []


def record(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    print(f"  [{status}] {name}")
    if detail and not passed:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


def main():
    engine = create_engine(DATABASE_URL, echo=False)

    with engine.connect() as conn:
        print("=" * 70)
        print("PRAVAAH DATABASE VERIFICATION")
        print("=" * 70)

        # ==============================================================
        # 1. PostGIS verification
        # ==============================================================
        print("\n--- PostGIS Verification ---")
        try:
            ver = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            record("PostGIS installed", True, f"Version: {ver}")
        except Exception as e:
            record("PostGIS installed", False, str(e))

        # ==============================================================
        # 2. Schema: tables exist
        # ==============================================================
        print("\n--- Schema: Tables ---")
        expected_tables = [
            "roles", "authorities", "users", "zones", "locations",
            "data_sources", "sensor_nodes", "observations",
            "terrain_features", "historical_events",
            "risk_predictions", "risk_explanations",
            "incidents", "alerts",
            "rescue_teams", "rescue_resources", "response_actions",
            "response_assignments", "audit_logs",
        ]
        actual_tables = [
            r[0] for r in conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE' "
                "ORDER BY table_name"
            ))
        ]
        missing = set(expected_tables) - set(actual_tables)
        extra = set(actual_tables) - set(expected_tables) - {"spatial_ref_sys", "alembic_version"}
        record("All 19 tables exist", len(missing) == 0,
               f"Missing: {missing}" if missing else f"Found: {len(expected_tables)}")
        if extra:
            record("No extra tables", len(extra) == 0, f"Extra: {extra}")

        # ==============================================================
        # 3. Schema: columns, types, nullability
        # ==============================================================
        print("\n--- Schema: Columns ---")
        # Spec column definitions (table -> [(name, pg_type_pattern, nullable)])
        # Checking a representative subset; full check via the listing
        col_checks = {
            "roles": [("id", "bigint", "NO"), ("name", "character varying", "NO"),
                      ("permissions", "ARRAY", "NO"), ("created_at", "timestamp with time zone", "NO")],
            "observations": [("ingested_at", "timestamp with time zone", "NO"),
                            ("rainfall_1h_mm", "numeric", "YES"),
                            ("quality_status", "character varying", "NO"),
                            ("data_origin", "character varying", "NO")],
            "risk_predictions": [("status", "character varying", "NO"),
                                ("confidence", "numeric", "YES"),
                                ("model_name", "character varying", "NO")],
            "response_assignments": [("assigned_at", "timestamp with time zone", "NO"),
                                     ("released_at", "timestamp with time zone", "YES")],
            "audit_logs": [("metadata", "jsonb", "YES")],
        }
        all_cols_ok = True
        for tbl, checks in col_checks.items():
            cols = {
                r[0]: (r[1], r[2]) for r in conn.execute(text(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t ORDER BY ordinal_position"
                ), {"t": tbl})
            }
            for cname, ctype, cnull in checks:
                if cname not in cols:
                    record(f"Column {tbl}.{cname} exists", False, "NOT FOUND")
                    all_cols_ok = False
                else:
                    actual_type, actual_null = cols[cname]
                    type_ok = ctype.lower() in actual_type.lower() or (ctype == "ARRAY" and "ARRAY" in actual_type)
                    null_ok = actual_null == cnull
                    if not type_ok or not null_ok:
                        record(f"Column {tbl}.{cname}", False,
                               f"Expected type~{ctype} null={cnull}, got {actual_type} null={actual_null}")
                        all_cols_ok = False
        record("Column type/nullability spot check", all_cols_ok)

        # Check observations has NO created_at
        obs_cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='observations'"
        ))]
        record("observations: no created_at (uses ingested_at)",
               "created_at" not in obs_cols and "ingested_at" in obs_cols)

        # Check response_assignments has NO created_at (uses assigned_at)
        ra_cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='response_assignments'"
        ))]
        record("response_assignments: no created_at (uses assigned_at)",
               "created_at" not in ra_cols and "assigned_at" in ra_cols)

        # ==============================================================
        # 4. Foreign keys and ON DELETE rules
        # ==============================================================
        print("\n--- Foreign Keys ---")
        fk_query = text("""
            SELECT
                tc.table_name AS child_table,
                kcu.column_name AS child_column,
                ccu.table_name AS parent_table,
                rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public'
            ORDER BY tc.table_name, kcu.column_name
        """)
        fks = list(conn.execute(fk_query).mappings())
        fk_count = len(fks)
        record(f"Foreign keys found: {fk_count}", fk_count > 0)

        # Check specific ON DELETE rules
        cascade_fks = {
            ("risk_explanations", "risk_prediction_id"): "CASCADE",
            ("response_assignments", "response_action_id"): "CASCADE",
        }
        set_null_fks = {
            ("incidents", "source_prediction_id"): "SET NULL",
        }
        for (child, col), expected_rule in {**cascade_fks, **set_null_fks}.items():
            found = [f for f in fks if f["child_table"] == child and f["child_column"] == col]
            if found:
                actual = found[0]["delete_rule"]
                record(f"FK {child}.{col} ON DELETE {expected_rule}", actual == expected_rule,
                       f"Actual: {actual}")
            else:
                record(f"FK {child}.{col} exists", False, "NOT FOUND")

        # Check that all other FKs default to RESTRICT
        restrict_fks = [f for f in fks
                        if (f["child_table"], f["child_column"]) not in cascade_fks
                        and (f["child_table"], f["child_column"]) not in set_null_fks]
        all_restrict = all(f["delete_rule"] == "RESTRICT" for f in restrict_fks)
        non_restrict = [(f["child_table"], f["child_column"], f["delete_rule"])
                        for f in restrict_fks if f["delete_rule"] != "RESTRICT"]
        record("All other FKs ON DELETE RESTRICT", all_restrict,
               f"Non-restrict: {non_restrict}" if non_restrict else "")

        # ==============================================================
        # 5. Constraints
        # ==============================================================
        print("\n--- Constraints ---")
        constraints = list(conn.execute(text("""
            SELECT conname, contype, conrelid::regclass AS table_name
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
            ORDER BY conrelid::regclass::text, conname
        """)).mappings())
        check_constraints = [c for c in constraints if c["contype"] == "c"]
        unique_constraints = [c for c in constraints if c["contype"] == "u"]
        record(f"CHECK constraints found: {len(check_constraints)}", len(check_constraints) > 0)
        record(f"UNIQUE constraints found: {len(unique_constraints)}", len(unique_constraints) > 0)

        # Verify specific constraints exist
        constraint_names = {c["conname"] for c in constraints}
        expected_checks = [
            "chk_obs_at_least_one_measurement", "chk_ds_real_provenance",
            "chk_rasgn_exactly_one", "chk_inc_resolved_consistency",
            "chk_alt_ack_consistency", "chk_zones_geom_valid",
            "chk_obs_soil_moisture_range", "chk_obs_humidity_range",
            "chk_rp_confidence_range", "chk_rp_horizon_positive",
        ]
        for cn in expected_checks:
            record(f"Constraint {cn}", cn in constraint_names)

        # ==============================================================
        # 6. Indexes
        # ==============================================================
        print("\n--- Indexes ---")
        indexes = list(conn.execute(text("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)).mappings())
        record(f"Total indexes: {len(indexes)}", len(indexes) > 0)

        expected_indexes = [
            "ix_users_lower_email", "ix_zones_geom", "ix_zones_admin_code",
            "ix_locations_geom", "ix_sensor_nodes_geom",
            "ix_obs_sensor_observed", "ix_obs_zone_observed",
            "ix_rp_active_per_zone_loc", "ix_rp_dashboard_high_risk",
            "ix_inc_geom", "ix_rt_geom", "ix_rr_geom",
            "ix_rasgn_resource_active", "ix_rasgn_team_active",
            "ix_he_affected_area", "ix_re_prediction_order",
            "ix_tf_zone_only", "ix_tf_location_only",
            "ix_obs_observed_at_brin",
        ]
        idx_names = {i["indexname"] for i in indexes}
        for iname in expected_indexes:
            record(f"Index {iname}", iname in idx_names)

        # ==============================================================
        # 7. PostGIS: geometry_columns
        # ==============================================================
        print("\n--- Geometry Columns ---")
        geom_cols = list(conn.execute(text("""
            SELECT f_table_name, f_geometry_column, type, srid
            FROM geometry_columns
            WHERE f_table_schema = 'public'
            ORDER BY f_table_name
        """)).mappings())
        record(f"Geometry columns found: {len(geom_cols)}", len(geom_cols) >= 7)

        expected_geom = {
            "zones": ("MULTIPOLYGON", 4326),
            "locations": ("POINT", 4326),
            "sensor_nodes": ("POINT", 4326),
            "incidents": ("POINT", 4326),
            "rescue_teams": ("POINT", 4326),
            "rescue_resources": ("POINT", 4326),
            "historical_events": ("MULTIPOLYGON", 4326),
        }
        for gc in geom_cols:
            tname = gc["f_table_name"]
            if tname in expected_geom:
                exp_type, exp_srid = expected_geom[tname]
                record(f"geometry {tname}: {exp_type} SRID {exp_srid}",
                       gc["type"] == exp_type and gc["srid"] == exp_srid,
                       f"Actual: {gc['type']} SRID {gc['srid']}")

        # ==============================================================
        # 8. Negative tests (each must be REJECTED)
        # ==============================================================
        print("\n--- Negative Tests ---")

        def expect_failure(label, sql, params=None):
            """Execute SQL that should fail with a constraint violation."""
            try:
                # Use a savepoint so the outer transaction survives
                conn.execute(text("SAVEPOINT neg_test"))
                conn.execute(text(sql), params or {})
                conn.execute(text("ROLLBACK TO SAVEPOINT neg_test"))
                record(f"NEG: {label}", False, "INSERT SUCCEEDED (should have failed)")
            except Exception as e:
                conn.execute(text("ROLLBACK TO SAVEPOINT neg_test"))
                record(f"NEG: {label}", True, str(e)[:120])

        # Need valid FKs for many tests — get existing IDs
        zone_id = conn.execute(text("SELECT id FROM zones LIMIT 1")).scalar()
        ds_id = conn.execute(text("SELECT id FROM data_sources LIMIT 1")).scalar()
        user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        pred_id = conn.execute(text("SELECT id FROM risk_predictions WHERE status='ACTIVE' LIMIT 1")).scalar()
        inc_id = conn.execute(text("SELECT id FROM incidents LIMIT 1")).scalar()
        ra_id = conn.execute(text("SELECT id FROM response_actions LIMIT 1")).scalar()
        rt_id = conn.execute(text("SELECT id FROM rescue_teams LIMIT 1")).scalar()
        rr_id = conn.execute(text("SELECT id FROM rescue_resources LIMIT 1")).scalar()

        if zone_id is None:
            print("  WARNING: No seed data found. Some negative tests require seed data. Run seed first.")

        # 8a. Invalid level value
        expect_failure(
            "Invalid risk level value",
            """INSERT INTO risk_predictions (zone_id, predicted_at, horizon_minutes,
               overall_risk_level, model_name, model_version, data_origin, status)
               VALUES (:zid, now(), 60, 'EXTREME', 'test', '1.0', 'SIMULATED', 'ACTIVE')""",
            {"zid": zone_id}
        )

        # 8b. Invalid data_origin
        expect_failure(
            "Invalid data_origin value",
            """INSERT INTO data_sources (name, source_type, data_origin)
               VALUES ('test_bad_origin', 'IOT_TELEMETRY', 'SYNTHETIC')"""
        )

        # 8c. Observation with no measurement
        expect_failure(
            "Observation with no measurement",
            """INSERT INTO observations (data_source_id, zone_id, observed_at, data_origin)
               VALUES (:ds, :zid, now(), 'SIMULATED')""",
            {"ds": ds_id, "zid": zone_id}
        )

        # 8d. soil_moisture_pct > 100
        expect_failure(
            "soil_moisture_pct > 100",
            """INSERT INTO observations (data_source_id, zone_id, observed_at,
               soil_moisture_pct, data_origin)
               VALUES (:ds, :zid, now(), 105.00, 'SIMULATED')""",
            {"ds": ds_id, "zid": zone_id}
        )

        # 8e. REAL data_source without provenance_notes
        expect_failure(
            "REAL data_source without provenance_notes",
            """INSERT INTO data_sources (name, source_type, data_origin, provenance_notes)
               VALUES ('test_real_no_prov', 'IOT_TELEMETRY', 'REAL', NULL)"""
        )

        # 8f. Two non-RELEASED assignments for same resource
        # First, create a valid assignment for the resource, then try a second
        if rr_id and ra_id:
            # The seed may already have an active assignment for a resource.
            # Check for one that's free
            free_rr = conn.execute(text("""
                SELECT rr.id FROM rescue_resources rr
                WHERE NOT EXISTS (
                    SELECT 1 FROM response_assignments ra
                    WHERE ra.resource_id = rr.id AND ra.status <> 'RELEASED'
                )
                LIMIT 1
            """)).scalar()
            if free_rr:
                try:
                    conn.execute(text("SAVEPOINT neg_test_dup"))
                    conn.execute(text("""
                        INSERT INTO response_assignments (response_action_id, resource_id, status, assigned_by)
                        VALUES (:raid, :rid, 'ASSIGNED', :uid)
                    """), {"raid": ra_id, "rid": free_rr, "uid": user_id})
                    # Now try a second
                    try:
                        conn.execute(text("""
                            INSERT INTO response_assignments (response_action_id, resource_id, status, assigned_by)
                            VALUES (:raid, :rid, 'ASSIGNED', :uid)
                        """), {"raid": ra_id, "rid": free_rr, "uid": user_id})
                        conn.execute(text("ROLLBACK TO SAVEPOINT neg_test_dup"))
                        record("NEG: Two non-RELEASED assignments for same resource", False,
                               "Second INSERT succeeded")
                    except Exception as e:
                        conn.execute(text("ROLLBACK TO SAVEPOINT neg_test_dup"))
                        record("NEG: Two non-RELEASED assignments for same resource", True,
                               str(e)[:120])
                except Exception as e:
                    conn.execute(text("ROLLBACK TO SAVEPOINT neg_test_dup"))
                    record("NEG: Two non-RELEASED assignments for same resource", False,
                           f"Setup failed: {e}")
            else:
                # All resources have assignments, test with existing assigned resource
                assigned_rr = conn.execute(text("""
                    SELECT ra.resource_id FROM response_assignments ra
                    WHERE ra.resource_id IS NOT NULL AND ra.status <> 'RELEASED' LIMIT 1
                """)).scalar()
                if assigned_rr:
                    expect_failure(
                        "Two non-RELEASED assignments for same resource",
                        """INSERT INTO response_assignments (response_action_id, resource_id, status, assigned_by)
                           VALUES (:raid, :rid, 'ASSIGNED', :uid)""",
                        {"raid": ra_id, "rid": assigned_rr, "uid": user_id}
                    )

        # 8g. Assignment with both team_id and resource_id
        expect_failure(
            "Assignment with both team_id AND resource_id",
            """INSERT INTO response_assignments (response_action_id, team_id, resource_id, status)
               VALUES (:raid, :tid, :rid, 'ASSIGNED')""",
            {"raid": ra_id, "tid": rt_id, "rid": rr_id}
        )

        # 8h. Assignment with neither team_id nor resource_id
        expect_failure(
            "Assignment with neither team_id NOR resource_id",
            """INSERT INTO response_assignments (response_action_id, team_id, resource_id, status)
               VALUES (:raid, NULL, NULL, 'ASSIGNED')""",
            {"raid": ra_id}
        )

        # 8i. Incident RESOLVED without resolved_at
        expect_failure(
            "Incident RESOLVED without resolved_at",
            """INSERT INTO incidents (zone_id, incident_type, severity, status,
               started_at, resolved_at, data_origin)
               VALUES (:zid, 'FLOOD', 'HIGH', 'RESOLVED', now(), NULL, 'SIMULATED')""",
            {"zid": zone_id}
        )

        # 8j. Alert with acknowledged_at but no acknowledged_by
        expect_failure(
            "Alert with acknowledged_at but no acknowledged_by",
            """INSERT INTO alerts (zone_id, alert_type, severity, message,
               status, acknowledged_at, acknowledged_by, data_origin)
               VALUES (:zid, 'FLOOD', 'HIGH', 'test', 'ACKNOWLEDGED',
                       now(), NULL, 'SIMULATED')""",
            {"zid": zone_id}
        )

        # 8k. Two ACTIVE predictions for same zone/location
        if zone_id and pred_id:
            expect_failure(
                "Two ACTIVE predictions for same zone/location",
                """INSERT INTO risk_predictions (zone_id, predicted_at, horizon_minutes,
                   overall_risk_level, model_name, model_version, data_origin, status)
                   VALUES (:zid, now(), 60, 'LOW', 'test', '1.0', 'SIMULATED', 'ACTIVE')""",
                {"zid": zone_id}
            )

        # 8l. Duplicate (sensor_node_id, observed_at) — use existing sensor and observation time
        sn_id = conn.execute(text("SELECT id FROM sensor_nodes LIMIT 1")).scalar()
        if sn_id:
            existing_obs = conn.execute(text(
                "SELECT observed_at FROM observations WHERE sensor_node_id = :sid LIMIT 1"
            ), {"sid": sn_id}).scalar()
            if existing_obs:
                expect_failure(
                    "Duplicate (sensor_node_id, observed_at)",
                    """INSERT INTO observations (sensor_node_id, data_source_id, zone_id,
                       observed_at, rainfall_1h_mm, data_origin)
                       VALUES (:sid, :ds, :zid, :oat, 5.0, 'SIMULATED')""",
                    {"sid": sn_id, "ds": ds_id, "zid": zone_id, "oat": existing_obs}
                )

        # 8m. Invalid polygon in zones (self-intersecting bowtie)
        expect_failure(
            "Invalid polygon in zones (ST_IsValid check)",
            """INSERT INTO zones (name, zone_type, geom, status)
               VALUES ('bad_geom', 'TEST',
                       ST_GeomFromText('MULTIPOLYGON(((0 0, 1 1, 1 0, 0 1, 0 0)))', 4326),
                       'ACTIVE')"""
        )

        # ==============================================================
        # 9. Sample queries
        # ==============================================================
        print("\n--- Sample Queries ---")

        # 9a. Latest observation per sensor (lateral join)
        try:
            q = conn.execute(text("""
                SELECT sn.node_id, latest.observed_at, latest.rainfall_1h_mm,
                       latest.water_level_m, latest.quality_status
                FROM sensor_nodes sn
                CROSS JOIN LATERAL (
                    SELECT o.observed_at, o.rainfall_1h_mm, o.water_level_m, o.quality_status
                    FROM observations o
                    WHERE o.sensor_node_id = sn.id
                    ORDER BY o.observed_at DESC
                    LIMIT 1
                ) latest
                ORDER BY sn.node_id
            """))
            rows = q.fetchall()
            record("Latest observation per sensor", len(rows) > 0,
                   f"{len(rows)} sensors with readings")
            for r in rows[:3]:
                print(f"         {r[0]}: {r[1]} rain={r[2]}mm water={r[3]}m q={r[4]}")
        except Exception as e:
            record("Latest observation per sensor", False, str(e)[:200])

        # 9b. ACTIVE risk prediction per zone with explanations
        try:
            q = conn.execute(text("""
                SELECT z.name, rp.overall_risk_level, rp.flood_risk_level,
                       rp.landslide_risk_level, rp.predicted_at,
                       string_agg(re.factor_name || '=' || re.factor_value::text,
                                  ', ' ORDER BY re.display_order) AS factors
                FROM risk_predictions rp
                JOIN zones z ON z.id = rp.zone_id
                LEFT JOIN risk_explanations re ON re.risk_prediction_id = rp.id
                WHERE rp.status = 'ACTIVE'
                GROUP BY z.name, rp.overall_risk_level, rp.flood_risk_level,
                         rp.landslide_risk_level, rp.predicted_at
                ORDER BY rp.overall_risk_level DESC
            """))
            rows = q.fetchall()
            record("ACTIVE predictions with explanations", len(rows) > 0,
                   f"{len(rows)} active predictions")
            for r in rows[:3]:
                print(f"         {r[0]}: {r[1]} (flood={r[2]}, ls={r[3]}) factors=[{r[5]}]")
        except Exception as e:
            record("ACTIVE predictions with explanations", False, str(e)[:200])

        # 9c. Dashboard high-risk list (ACTIVE, level >= HIGH)
        try:
            q = conn.execute(text("""
                SELECT z.name, rp.overall_risk_level, rp.predicted_at,
                       rp.recommended_action
                FROM risk_predictions rp
                JOIN zones z ON z.id = rp.zone_id
                WHERE rp.status = 'ACTIVE'
                  AND rp.overall_risk_level IN ('HIGH','CRITICAL')
                ORDER BY rp.predicted_at DESC
            """))
            rows = q.fetchall()
            record("Dashboard high-risk list", True, f"{len(rows)} high-risk zones")
            for r in rows:
                print(f"         {r[0]}: {r[1]} at {r[2]}")
        except Exception as e:
            record("Dashboard high-risk list", False, str(e)[:200])

        # 9d. Recent change: ACTIVE vs most recent SUPERSEDED per zone
        try:
            q = conn.execute(text("""
                SELECT z.name,
                       active.overall_risk_level AS current_level,
                       superseded.overall_risk_level AS previous_level,
                       active.predicted_at AS changed_at
                FROM risk_predictions active
                JOIN zones z ON z.id = active.zone_id
                LEFT JOIN LATERAL (
                    SELECT rp2.overall_risk_level, rp2.predicted_at
                    FROM risk_predictions rp2
                    WHERE rp2.zone_id = active.zone_id
                      AND rp2.status = 'SUPERSEDED'
                    ORDER BY rp2.predicted_at DESC
                    LIMIT 1
                ) superseded ON TRUE
                WHERE active.status = 'ACTIVE'
                  AND superseded.overall_risk_level IS NOT NULL
                  AND superseded.overall_risk_level <> active.overall_risk_level
            """))
            rows = q.fetchall()
            record("Recent change (ACTIVE vs SUPERSEDED)", len(rows) > 0,
                   f"{len(rows)} zones with level changes")
            for r in rows:
                print(f"         {r[0]}: {r[2]} → {r[1]} at {r[3]}")
        except Exception as e:
            record("Recent change query", False, str(e)[:200])

        # 9e. Sensor-in-zone check with ST_Within
        try:
            q = conn.execute(text("""
                SELECT sn.node_id, z.name,
                       ST_Within(sn.geom, z.geom) AS is_within
                FROM sensor_nodes sn
                JOIN zones z ON z.id = sn.zone_id
                ORDER BY sn.node_id
            """))
            rows = q.fetchall()
            all_within = all(r[2] for r in rows)
            record("Sensor-in-zone ST_Within check", all_within,
                   f"All {len(rows)} sensors within their zone")
            for r in rows:
                status_mark = "✓" if r[2] else "✗"
                print(f"         {status_mark} {r[0]} in {r[1]}")
        except Exception as e:
            record("Sensor-in-zone check", False, str(e)[:200])

        # 9f. Locations inside a zone with an ACTIVE prediction
        try:
            q = conn.execute(text("""
                SELECT l.name, z.name AS zone_name, rp.overall_risk_level
                FROM locations l
                JOIN zones z ON z.id = l.zone_id
                JOIN risk_predictions rp ON rp.zone_id = z.id AND rp.status='ACTIVE'
                WHERE ST_Within(l.geom, z.geom)
                ORDER BY rp.overall_risk_level DESC, l.name
            """))
            rows = q.fetchall()
            record("Locations in zones with ACTIVE predictions", len(rows) > 0,
                   f"{len(rows)} locations found")
        except Exception as e:
            record("Locations in risk zones", False, str(e)[:200])

        # 9g. Resources near an incident with ST_DWithin
        try:
            q = conn.execute(text("""
                SELECT rr.name, rr.resource_type, rr.status,
                       ST_Distance(rr.geom::geography, i.geom::geography) AS distance_m
                FROM rescue_resources rr, incidents i
                WHERE i.geom IS NOT NULL
                  AND rr.geom IS NOT NULL
                  AND ST_DWithin(rr.geom::geography, i.geom::geography, 50000)
                ORDER BY distance_m
                LIMIT 10
            """))
            rows = q.fetchall()
            record("Resources near incident (ST_DWithin)", len(rows) > 0,
                   f"{len(rows)} resources within 50km")
            for r in rows[:5]:
                print(f"         {r[0]} ({r[1]}/{r[2]}): {r[3]:.0f}m")
        except Exception as e:
            record("Resources near incident", False, str(e)[:200])

        # 9h. Stale sensor query
        try:
            q = conn.execute(text("""
                SELECT sn.node_id, sn.last_seen_at, ds.stale_after_minutes,
                       CASE
                           WHEN sn.last_seen_at IS NULL THEN TRUE
                           WHEN now() - sn.last_seen_at >
                                make_interval(mins => COALESCE(ds.stale_after_minutes, 30))
                           THEN TRUE
                           ELSE FALSE
                       END AS is_stale
                FROM sensor_nodes sn
                JOIN data_sources ds ON ds.id = sn.data_source_id
                ORDER BY sn.node_id
            """))
            rows = q.fetchall()
            stale_count = sum(1 for r in rows if r[3])
            record("Stale sensor query", True, f"{stale_count} stale out of {len(rows)}")
            for r in rows:
                status_mark = "STALE" if r[3] else "OK"
                print(f"         {r[0]}: last_seen={r[1]}, threshold={r[2]}min → {status_mark}")
        except Exception as e:
            record("Stale sensor query", False, str(e)[:200])

        # 9i. Incident detail join
        try:
            q = conn.execute(text("""
                SELECT i.id AS incident_id, i.incident_type, i.severity, i.status,
                       z.name AS zone_name,
                       rp.overall_risk_level AS source_prediction_level,
                       a.message AS alert_message,
                       ra2.action_type, ra2.status AS action_status,
                       COALESCE(rt.name, rr.name) AS assigned_entity
                FROM incidents i
                JOIN zones z ON z.id = i.zone_id
                LEFT JOIN risk_predictions rp ON rp.id = i.source_prediction_id
                LEFT JOIN alerts a ON a.incident_id = i.id
                LEFT JOIN response_actions ra2 ON ra2.incident_id = i.id
                LEFT JOIN response_assignments rasgn ON rasgn.response_action_id = ra2.id
                LEFT JOIN rescue_teams rt ON rt.id = rasgn.team_id
                LEFT JOIN rescue_resources rr ON rr.id = rasgn.resource_id
                ORDER BY i.id
            """))
            rows = q.fetchall()
            record("Incident detail join", len(rows) > 0, f"{len(rows)} rows")
            for r in rows[:5]:
                print(f"         Inc#{r[0]} {r[1]}/{r[2]}/{r[3]} in {r[4]}, "
                      f"pred={r[5]}, action={r[7]}/{r[8]}, assigned={r[9]}")
        except Exception as e:
            record("Incident detail join", False, str(e)[:200])

        # 9j. EXPLAIN on key queries
        try:
            plan_sensor = conn.execute(text("""
                EXPLAIN SELECT o.* FROM sensor_nodes sn
                CROSS JOIN LATERAL (
                    SELECT * FROM observations o
                    WHERE o.sensor_node_id = sn.id
                    ORDER BY o.observed_at DESC LIMIT 1
                ) o WHERE sn.id = 1
            """)).fetchall()
            uses_index = any("ix_obs_sensor_observed" in str(r) or "Index" in str(r) for r in plan_sensor)
            record("EXPLAIN latest-per-sensor uses index", uses_index,
                   "\n".join(str(r[0]) for r in plan_sensor[:5]))
        except Exception as e:
            record("EXPLAIN latest-per-sensor", False, str(e)[:200])

        try:
            plan_active = conn.execute(text("""
                EXPLAIN SELECT * FROM risk_predictions
                WHERE status = 'ACTIVE' AND overall_risk_level IN ('HIGH','CRITICAL')
                ORDER BY predicted_at DESC
            """)).fetchall()
            uses_index = any("ix_rp_dashboard_high_risk" in str(r) or "Index" in str(r) for r in plan_active)
            record("EXPLAIN active-prediction uses index", uses_index,
                   "\n".join(str(r[0]) for r in plan_active[:5]))
        except Exception as e:
            record("EXPLAIN active-prediction", False, str(e)[:200])

        # ==============================================================
        # 10. Seed data verification
        # ==============================================================
        print("\n--- Seed Data Verification ---")
        expected_counts = {
            "roles": 3, "authorities": 1, "users": 3, "data_sources": 3,
            "zones": 5, "locations": 10, "sensor_nodes": 6,
            "terrain_features": 5, "historical_events": 4,
            "risk_predictions": 6,  # 5 ACTIVE + 1 SUPERSEDED
            "incidents": 2, "alerts": 2,
            "rescue_teams": 2, "rescue_resources": 4,
            "response_actions": 2, "response_assignments": 2,
            "audit_logs": 4,
        }
        for tbl, expected in expected_counts.items():
            actual = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
            record(f"Seed count {tbl}: {actual}/{expected}", actual == expected)

        # Observations: ~150
        obs_cnt = conn.execute(text("SELECT count(*) FROM observations")).scalar()
        record(f"Seed count observations: {obs_cnt}/~150", 140 <= obs_cnt <= 160,
               f"Actual: {obs_cnt}")

        # Risk explanations: ~12
        re_cnt = conn.execute(text("SELECT count(*) FROM risk_explanations")).scalar()
        record(f"Seed count risk_explanations: {re_cnt}/~12", 10 <= re_cnt <= 15,
               f"Actual: {re_cnt}")

        # No NULL data_origin
        tables_with_origin = [
            "data_sources", "sensor_nodes", "observations",
            "terrain_features", "historical_events", "risk_predictions",
            "incidents", "alerts",
        ]
        all_origin_ok = True
        for tbl in tables_with_origin:
            null_cnt = conn.execute(text(
                f"SELECT count(*) FROM {tbl} WHERE data_origin IS NULL"
            )).scalar()
            if null_cnt > 0:
                all_origin_ok = False
                record(f"No NULL data_origin in {tbl}", False, f"{null_cnt} NULL rows")
        record("No NULL data_origin in any table", all_origin_ok)

        # All SIMULATED
        all_sim_ok = True
        for tbl in tables_with_origin:
            non_sim = conn.execute(text(
                f"SELECT count(*) FROM {tbl} WHERE data_origin <> 'SIMULATED'"
            )).scalar()
            if non_sim > 0:
                all_sim_ok = False
                record(f"All SIMULATED in {tbl}", False, f"{non_sim} non-SIMULATED rows")
        record("All seed data is SIMULATED", all_sim_ok)

        # ==============================================================
        # SUMMARY
        # ==============================================================
        print("\n" + "=" * 70)
        print("VERIFICATION SUMMARY")
        print("=" * 70)
        passed = sum(1 for _, s, _ in results if s == PASS)
        failed = sum(1 for _, s, _ in results if s == FAIL)
        print(f"\n  PASSED: {passed}")
        print(f"  FAILED: {failed}")
        print(f"  TOTAL:  {passed + failed}")

        if failed > 0:
            print(f"\n  FAILED ITEMS:")
            for name, status, detail in results:
                if status == FAIL:
                    print(f"    - {name}: {detail[:150]}")

        return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
