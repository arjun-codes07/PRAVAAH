"""
PRAVAAH seed script — SPEC §12 demo data.

Every row has data_origin='SIMULATED'. No REAL data.
Zone/location names prefixed "Demo".
Geometry is illustrative around Mandi, HP (~31.7°N, 76.9°E).
Passwords come from environment variables.
Idempotent: fails clearly if seed data already exists.

Usage:
    python -m scripts.seed
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://pravaah_app:changeme@localhost:5432/pravaah",
)

# Seed passwords from env
SEED_PW_OFFICER = os.environ.get("SEED_PASSWORD_OFFICER", "DemoOfficer123!")
SEED_PW_COMMANDER = os.environ.get("SEED_PASSWORD_COMMANDER", "DemoCommander123!")
SEED_PW_COORDINATOR = os.environ.get("SEED_PASSWORD_COORDINATOR", "DemoCoordinator123!")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main():
    engine = create_engine(DATABASE_URL, echo=False)
    with engine.begin() as conn:
        # --- Idempotency check ---
        existing = conn.execute(text("SELECT count(*) FROM roles")).scalar()
        if existing > 0:
            print("ERROR: Database already contains data (roles table is not empty).")
            print("To re-seed, run: python -m scripts.reset_db  or truncate all tables first.")
            sys.exit(1)

        now = datetime.now(timezone.utc)
        h24_ago = now - timedelta(hours=24)

        # ================================================================
        # ROLES (3)
        # ================================================================
        conn.execute(text("""
            INSERT INTO roles (name, description, permissions) VALUES
            ('AUTHORITY_OFFICER', 'District/authority-level officer with zone oversight',
             '{view_dashboard,view_zones,view_incidents,view_alerts,manage_alerts,view_sensors}'),
            ('INCIDENT_COMMANDER', 'Incident commander managing incidents and response',
             '{view_dashboard,view_zones,view_incidents,manage_incidents,view_alerts,manage_alerts,view_response,manage_response,view_sensors}'),
            ('RESOURCE_COORDINATOR', 'Coordinates rescue teams and resources',
             '{view_dashboard,view_zones,view_incidents,view_alerts,view_response,manage_response,manage_resources,view_sensors}')
        """))

        # ================================================================
        # AUTHORITIES (1)
        # ================================================================
        conn.execute(text("""
            INSERT INTO authorities (name, authority_type, region_scope, status) VALUES
            ('Demo District Authority - Mandi', 'DISTRICT_AUTHORITY', 'Mandi District, Himachal Pradesh', 'ACTIVE')
        """))

        # Get IDs
        auth_id = conn.execute(text("SELECT id FROM authorities WHERE name = 'Demo District Authority - Mandi'")).scalar()
        role_ids = {}
        for r in conn.execute(text("SELECT id, name FROM roles")).mappings():
            role_ids[r["name"]] = r["id"]

        # ================================================================
        # USERS (3)
        # ================================================================
        conn.execute(text("""
            INSERT INTO users (name, email, password_hash, role_id, authority_id, status) VALUES
            (:n1, :e1, :h1, :r1, :a, 'ACTIVE'),
            (:n2, :e2, :h2, :r2, :a, 'ACTIVE'),
            (:n3, :e3, :h3, :r3, :a, 'ACTIVE')
        """), {
            "n1": "Demo Officer", "e1": "officer@demo.pravaah.local",
            "h1": hash_password(SEED_PW_OFFICER), "r1": role_ids["AUTHORITY_OFFICER"],
            "n2": "Demo Commander", "e2": "commander@demo.pravaah.local",
            "h2": hash_password(SEED_PW_COMMANDER), "r2": role_ids["INCIDENT_COMMANDER"],
            "n3": "Demo Coordinator", "e3": "coordinator@demo.pravaah.local",
            "h3": hash_password(SEED_PW_COORDINATOR), "r3": role_ids["RESOURCE_COORDINATOR"],
            "a": auth_id,
        })

        user_commander = conn.execute(
            text("SELECT id FROM users WHERE email = 'commander@demo.pravaah.local'")
        ).scalar()
        user_coordinator = conn.execute(
            text("SELECT id FROM users WHERE email = 'coordinator@demo.pravaah.local'")
        ).scalar()

        # ================================================================
        # DATA_SOURCES (3)
        # ================================================================
        conn.execute(text("""
            INSERT INTO data_sources (name, source_type, provider, description, data_origin, status, stale_after_minutes, provenance_notes) VALUES
            ('Demo Telemetry Simulator', 'IOT_TELEMETRY', 'PRAVAAH Demo', 'Simulated IoT sensor telemetry feed', 'SIMULATED', 'ACTIVE', 30, NULL),
            ('Demo Replay Feed', 'IOT_TELEMETRY', 'PRAVAAH Demo', 'Replayed historical sensor data', 'SIMULATED', 'ACTIVE', 60, NULL),
            ('Demo Reference Data', 'HISTORICAL_RECORD', 'PRAVAAH Demo', 'Simulated terrain and historical event data', 'SIMULATED', 'ACTIVE', NULL, NULL)
        """))
        ds_sim = conn.execute(text("SELECT id FROM data_sources WHERE name = 'Demo Telemetry Simulator'")).scalar()
        ds_ref = conn.execute(text("SELECT id FROM data_sources WHERE name = 'Demo Reference Data'")).scalar()

        # ================================================================
        # ZONES (5) — illustrative polygons around Mandi, HP
        # Each zone is a small rectangle for demo purposes
        # ================================================================
        # Zone centers (lat, lon): roughly around Mandi district
        zone_specs = [
            ("Demo Zone - Mandi Town",       "URBAN",    "DEMO-Z01", 31.710, 76.930, 0.03),
            ("Demo Zone - Sundernagar",       "URBAN",    "DEMO-Z02", 31.530, 76.900, 0.04),
            ("Demo Zone - Jogindernagar",     "SEMI_URBAN","DEMO-Z03", 31.990, 76.780, 0.03),
            ("Demo Zone - Karsog Valley",     "RURAL",    "DEMO-Z04", 31.380, 77.200, 0.05),
            ("Demo Zone - Pandoh Dam Area",   "CRITICAL_INFRASTRUCTURE", "DEMO-Z05", 31.670, 77.050, 0.02),
        ]
        zone_ids = {}
        for zname, ztype, acode, lat, lon, sz in zone_specs:
            wkt = (
                f"MULTIPOLYGON((("
                f"{lon - sz} {lat - sz},"
                f"{lon + sz} {lat - sz},"
                f"{lon + sz} {lat + sz},"
                f"{lon - sz} {lat + sz},"
                f"{lon - sz} {lat - sz}"
                f")))"
            )
            conn.execute(text("""
                INSERT INTO zones (authority_id, name, zone_type, admin_code, geom, status)
                VALUES (:aid, :n, :zt, :ac, ST_GeomFromText(:wkt, 4326), 'ACTIVE')
            """), {"aid": auth_id, "n": zname, "zt": ztype, "ac": acode, "wkt": wkt})
            zid = conn.execute(text("SELECT id FROM zones WHERE name = :n"), {"n": zname}).scalar()
            zone_ids[zname] = zid

        # ================================================================
        # LOCATIONS (10) — 2 per zone
        # ================================================================
        location_specs = [
            ("Demo Location - Mandi Bus Stand",       "BUS_STATION",  zone_ids["Demo Zone - Mandi Town"],     31.712, 76.932),
            ("Demo Location - Mandi Hospital",        "HOSPITAL",     zone_ids["Demo Zone - Mandi Town"],     31.708, 76.928),
            ("Demo Location - Sundernagar Market",    "MARKET",       zone_ids["Demo Zone - Sundernagar"],     31.532, 76.902),
            ("Demo Location - Sundernagar School",    "SCHOOL",       zone_ids["Demo Zone - Sundernagar"],     31.528, 76.898),
            ("Demo Location - Joginder Nagar Center", "TOWN_CENTER",  zone_ids["Demo Zone - Jogindernagar"],  31.992, 76.782),
            ("Demo Location - Joginder Rail Station", "RAIL_STATION", zone_ids["Demo Zone - Jogindernagar"],  31.988, 76.778),
            ("Demo Location - Karsog Temple Area",    "RELIGIOUS",    zone_ids["Demo Zone - Karsog Valley"],   31.382, 77.202),
            ("Demo Location - Karsog Bridge",         "BRIDGE",       zone_ids["Demo Zone - Karsog Valley"],   31.378, 77.198),
            ("Demo Location - Pandoh Dam Viewpoint",  "DAM",          zone_ids["Demo Zone - Pandoh Dam Area"], 31.672, 77.052),
            ("Demo Location - Pandoh Colony",         "SETTLEMENT",   zone_ids["Demo Zone - Pandoh Dam Area"], 31.668, 77.048),
        ]
        loc_ids = {}
        for lname, ltype, zid, lat, lon in location_specs:
            conn.execute(text("""
                INSERT INTO locations (zone_id, name, location_type, geom)
                VALUES (:zid, :n, :lt, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            """), {"zid": zid, "n": lname, "lt": ltype, "lon": lon, "lat": lat})
            lid = conn.execute(text("SELECT id FROM locations WHERE name = :n"), {"n": lname}).scalar()
            loc_ids[lname] = lid

        # ================================================================
        # SENSOR_NODES (6) — HP-MANDI-001..006, one deliberately stale
        # All placed within their assigned zone geometry
        # ================================================================
        sensor_specs = [
            ("HP-MANDI-001", ds_sim, "Demo Zone - Mandi Town",     None, "MULTI_SENSOR", 31.711, 76.931, "ACTIVE",   now - timedelta(minutes=5)),
            ("HP-MANDI-002", ds_sim, "Demo Zone - Sundernagar",    None, "MULTI_SENSOR", 31.531, 76.901, "ACTIVE",   now - timedelta(minutes=10)),
            ("HP-MANDI-003", ds_sim, "Demo Zone - Jogindernagar",  None, "MULTI_SENSOR", 31.991, 76.781, "ACTIVE",   now - timedelta(minutes=8)),
            ("HP-MANDI-004", ds_sim, "Demo Zone - Karsog Valley",  None, "MULTI_SENSOR", 31.381, 77.201, "ACTIVE",   now - timedelta(minutes=3)),
            ("HP-MANDI-005", ds_sim, "Demo Zone - Pandoh Dam Area",None, "MULTI_SENSOR", 31.671, 77.051, "ACTIVE",   now - timedelta(minutes=15)),
            # HP-MANDI-006: deliberately stale — last_seen_at 2+ hours ago
            ("HP-MANDI-006", ds_sim, "Demo Zone - Mandi Town",     None, "MULTI_SENSOR", 31.709, 76.929, "ACTIVE",   now - timedelta(hours=2, minutes=30)),
        ]
        sensor_ids = {}
        for node_id, dsid, zname, loc_name, stype, lat, lon, status, last_seen in sensor_specs:
            zid = zone_ids[zname]
            lid = loc_ids[loc_name] if loc_name else None
            conn.execute(text("""
                INSERT INTO sensor_nodes (node_id, data_source_id, zone_id, location_id, sensor_type, geom, data_origin, status, last_seen_at)
                VALUES (:nid, :dsid, :zid, :lid, :stype, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 'SIMULATED', :status, :lsa)
            """), {"nid": node_id, "dsid": dsid, "zid": zid, "lid": lid, "stype": stype,
                   "lon": lon, "lat": lat, "status": status, "lsa": last_seen})
            sid = conn.execute(text("SELECT id FROM sensor_nodes WHERE node_id = :nid"), {"nid": node_id}).scalar()
            sensor_ids[node_id] = sid

        # ================================================================
        # OBSERVATIONS (~150) — 24h hourly per sensor (6 × 25 = 150)
        # HP-MANDI-001 zone shows a rising rainfall/soil-moisture/water-level trend
        # One SUSPECT reading on HP-MANDI-003
        # ================================================================
        import random
        random.seed(42)  # reproducible

        obs_count = 0
        for hour_offset in range(25):  # 0..24 => 25 readings per sensor
            obs_time = h24_ago + timedelta(hours=hour_offset)
            for node_id, sid in sensor_ids.items():
                sn = conn.execute(text("SELECT zone_id, data_source_id FROM sensor_nodes WHERE id = :id"), {"id": sid}).mappings().one()
                zid = sn["zone_id"]
                dsid_obs = sn["data_source_id"]

                quality = "VALID"

                if node_id == "HP-MANDI-001":
                    # Rising trend zone
                    base_rain = 2.0 + hour_offset * 1.5
                    base_soil = 30.0 + hour_offset * 1.2
                    base_water = 1.5 + hour_offset * 0.08
                    rainfall = round(base_rain + random.uniform(-0.5, 0.5), 2)
                    soil = min(round(base_soil + random.uniform(-1.0, 1.0), 2), 99.99)
                    water = round(base_water + random.uniform(-0.05, 0.05), 3)
                    rate = round(0.08 + random.uniform(-0.01, 0.01), 3) if hour_offset > 0 else None
                    slope = round(25.0 + random.uniform(-0.5, 0.5), 2)
                    temp = round(18.0 - hour_offset * 0.1 + random.uniform(-0.5, 0.5), 2)
                    humid = round(65.0 + hour_offset * 0.5 + random.uniform(-1.0, 1.0), 2)
                elif node_id == "HP-MANDI-003" and hour_offset == 12:
                    # SUSPECT reading
                    quality = "SUSPECT"
                    rainfall = round(random.uniform(0, 5), 2)
                    soil = round(random.uniform(30, 60), 2)
                    water = round(random.uniform(1, 3), 3)
                    rate = None
                    slope = round(random.uniform(15, 35), 2)
                    temp = round(random.uniform(10, 25), 2)
                    humid = round(random.uniform(50, 85), 2)
                else:
                    rainfall = round(random.uniform(0, 15), 2)
                    soil = round(random.uniform(25, 70), 2)
                    water = round(random.uniform(0.5, 4), 3)
                    rate = round(random.uniform(-0.05, 0.1), 3) if hour_offset > 0 else None
                    slope = round(random.uniform(10, 40), 2)
                    temp = round(random.uniform(10, 28), 2)
                    humid = round(random.uniform(40, 90), 2)

                conn.execute(text("""
                    INSERT INTO observations
                    (sensor_node_id, data_source_id, zone_id, observed_at,
                     rainfall_1h_mm, soil_moisture_pct, water_level_m,
                     water_level_rate_m_per_h, slope_angle_deg, temperature_c,
                     humidity_pct, quality_status, data_origin)
                    VALUES (:sid, :dsid, :zid, :oat,
                            :rain, :soil, :water, :rate, :slope, :temp, :humid,
                            :qs, 'SIMULATED')
                """), {
                    "sid": sid, "dsid": dsid_obs, "zid": zid, "oat": obs_time,
                    "rain": rainfall, "soil": soil, "water": water, "rate": rate,
                    "slope": slope, "temp": temp, "humid": humid, "qs": quality,
                })
                obs_count += 1

        print(f"  Observations inserted: {obs_count}")

        # ================================================================
        # TERRAIN_FEATURES (5) — one per zone
        # ================================================================
        tf_specs = [
            ("Demo Zone - Mandi Town",     None, 850.0, 25.5, 0.65),
            ("Demo Zone - Sundernagar",    None, 780.0, 18.0, 0.45),
            ("Demo Zone - Jogindernagar",  None, 1200.0, 30.0, 0.72),
            ("Demo Zone - Karsog Valley",  None, 1500.0, 35.0, 0.80),
            ("Demo Zone - Pandoh Dam Area",None, 900.0, 12.0, 0.35),
        ]
        for zname, loc_name, elev, slope, susc in tf_specs:
            zid = zone_ids[zname]
            lid = loc_ids[loc_name] if loc_name else None
            conn.execute(text("""
                INSERT INTO terrain_features (zone_id, location_id, elevation_m, slope_deg, susceptibility_score, data_source_id, data_origin)
                VALUES (:zid, :lid, :elev, :slope, :susc, :dsid, 'SIMULATED')
            """), {"zid": zid, "lid": lid, "elev": elev, "slope": slope, "susc": susc, "dsid": ds_ref})

        # ================================================================
        # HISTORICAL_EVENTS (4) — 2 FLOOD, 2 LANDSLIDE; one with affected_area
        # ================================================================
        conn.execute(text("""
            INSERT INTO historical_events (hazard_type, zone_id, event_time, severity, description, data_source_id, data_origin)
            VALUES
            ('FLOOD', :z1, '2024-07-15 08:00:00+05:30', 'HIGH',
             'Demo: Flash flood event in Mandi Town area during monsoon 2024', :ds, 'SIMULATED'),
            ('FLOOD', :z5, '2023-08-20 14:00:00+05:30', 'MODERATE',
             'Demo: Moderate flooding near Pandoh Dam due to heavy rainfall', :ds, 'SIMULATED'),
            ('LANDSLIDE', :z3, '2024-09-01 06:00:00+05:30', 'CRITICAL',
             'Demo: Major landslide blocking Jogindernagar road', :ds, 'SIMULATED')
        """), {"z1": zone_ids["Demo Zone - Mandi Town"],
               "z5": zone_ids["Demo Zone - Pandoh Dam Area"],
               "z3": zone_ids["Demo Zone - Jogindernagar"],
               "ds": ds_ref})

        # One with affected_area polygon
        z4 = zone_ids["Demo Zone - Karsog Valley"]
        conn.execute(text("""
            INSERT INTO historical_events (hazard_type, zone_id, event_time, severity, description, affected_area, data_source_id, data_origin)
            VALUES ('LANDSLIDE', :z4, '2023-06-10 16:00:00+05:30', 'HIGH',
                    'Demo: Landslide in Karsog Valley with mapped affected area',
                    ST_GeomFromText('MULTIPOLYGON(((77.195 31.375, 77.205 31.375, 77.205 31.385, 77.195 31.385, 77.195 31.375)))', 4326),
                    :ds, 'SIMULATED')
        """), {"z4": z4, "ds": ds_ref})

        # ================================================================
        # RISK_PREDICTIONS (5 ACTIVE + 1 SUPERSEDED)
        # Levels: LOW, MODERATE, HIGH across zones
        # The SUPERSEDED row shows a "recent change" for the HIGH zone
        # model: demo-rule-baseline v0.1-demo, confidence NULL
        # ================================================================
        pred_time = now - timedelta(minutes=30)
        pred_specs = [
            # (zone_name, overall, flood_level, ls_level, flood_prob, ls_prob, status, rec_action)
            ("Demo Zone - Mandi Town",     "HIGH",     "HIGH",     "MODERATE", 0.78, 0.55, "ACTIVE",
             "Evacuate low-lying areas. Monitor water levels continuously."),
            ("Demo Zone - Sundernagar",    "MODERATE", "MODERATE", "LOW",      0.45, 0.20, "ACTIVE",
             "Increase monitoring frequency. Alert response teams."),
            ("Demo Zone - Jogindernagar",  "MODERATE", "LOW",      "MODERATE", 0.25, 0.50, "ACTIVE",
             "Monitor slope stability sensors. Restrict traffic on vulnerable routes."),
            ("Demo Zone - Karsog Valley",  "LOW",      "LOW",      "LOW",      0.10, 0.15, "ACTIVE", None),
            ("Demo Zone - Pandoh Dam Area","LOW",      "LOW",      None,       0.12, None,  "ACTIVE", None),
        ]
        pred_ids = {}
        for zname, overall, fl, ll, fp, lp, status, rec in pred_specs:
            zid = zone_ids[zname]
            conn.execute(text("""
                INSERT INTO risk_predictions
                (zone_id, predicted_at, horizon_minutes,
                 flood_probability, landslide_probability,
                 flood_risk_level, landslide_risk_level, overall_risk_level,
                 confidence, model_name, model_version,
                 recommended_action, input_data_as_of, data_origin, status)
                VALUES (:zid, :pat, 360,
                        :fp, :lp, :fl, :ll, :overall,
                        NULL, 'demo-rule-baseline', '0.1-demo',
                        :rec, :ida, 'SIMULATED', :status)
            """), {"zid": zid, "pat": pred_time, "fp": fp, "lp": lp,
                   "fl": fl, "ll": ll, "overall": overall, "rec": rec,
                   "ida": pred_time - timedelta(minutes=5), "status": status})
            pid = conn.execute(text(
                "SELECT id FROM risk_predictions WHERE zone_id = :zid AND status = :s ORDER BY id DESC LIMIT 1"
            ), {"zid": zid, "s": status}).scalar()
            pred_ids[zname] = pid

        # SUPERSEDED prediction for Mandi Town (was MODERATE, now HIGH — shows "recent change")
        sup_time = pred_time - timedelta(hours=6)
        conn.execute(text("""
            INSERT INTO risk_predictions
            (zone_id, predicted_at, horizon_minutes,
             flood_probability, landslide_probability,
             flood_risk_level, landslide_risk_level, overall_risk_level,
             confidence, model_name, model_version,
             recommended_action, input_data_as_of, data_origin, status)
            VALUES (:zid, :pat, 360,
                    0.40, 0.30, 'MODERATE', 'LOW', 'MODERATE',
                    NULL, 'demo-rule-baseline', '0.1-demo',
                    'Continue routine monitoring.', :ida, 'SIMULATED', 'SUPERSEDED')
        """), {"zid": zone_ids["Demo Zone - Mandi Town"],
               "pat": sup_time,
               "ida": sup_time - timedelta(minutes=5)})

        # ================================================================
        # RISK_EXPLANATIONS (~12) — 3-4 factors per MODERATE+ prediction
        # ================================================================
        high_pred = pred_ids["Demo Zone - Mandi Town"]
        conn.execute(text("""
            INSERT INTO risk_explanations (risk_prediction_id, factor_name, factor_value, unit, contribution, explanation_text, display_order) VALUES
            (:pid, 'rainfall_1h',     38.50, 'mm',     0.85, 'Sustained heavy rainfall exceeding 35mm/h threshold', 1),
            (:pid, 'soil_moisture',    82.00, '%',      0.75, 'Soil saturation above 80% significantly increases flood and landslide risk', 2),
            (:pid, 'water_level',      3.50,  'm',      0.70, 'Water level approaching danger mark of 4.0m', 3),
            (:pid, 'slope_angle',      25.50, 'deg',    0.55, 'Moderate slope angle contributes to landslide susceptibility', 4)
        """), {"pid": high_pred})

        mod_pred_sun = pred_ids["Demo Zone - Sundernagar"]
        conn.execute(text("""
            INSERT INTO risk_explanations (risk_prediction_id, factor_name, factor_value, unit, contribution, explanation_text, display_order) VALUES
            (:pid, 'rainfall_1h',     18.00, 'mm',     0.55, 'Moderate rainfall, within normal monsoon range', 1),
            (:pid, 'soil_moisture',    55.00, '%',      0.40, 'Soil moisture elevated but below critical threshold', 2),
            (:pid, 'water_level',      2.20,  'm',      0.45, 'Water level rising but within safe limits', 3)
        """), {"pid": mod_pred_sun})

        mod_pred_jog = pred_ids["Demo Zone - Jogindernagar"]
        conn.execute(text("""
            INSERT INTO risk_explanations (risk_prediction_id, factor_name, factor_value, unit, contribution, explanation_text, display_order) VALUES
            (:pid, 'slope_angle',      30.00, 'deg',    0.70, 'Steep terrain increases landslide susceptibility', 1),
            (:pid, 'soil_moisture',    60.00, '%',      0.50, 'Moderate soil moisture in hilly terrain', 2),
            (:pid, 'rainfall_1h',      12.00, 'mm',     0.35, 'Light rainfall but cumulative effect on steep slopes', 3),
            (:pid, 'water_level',      1.80,  'm',      0.20, 'Low water level, minimal flood risk', 4)
        """), {"pid": mod_pred_jog})

        # One explanation for the LOW prediction in Karsog to reach ~12 total
        low_pred_kar = pred_ids["Demo Zone - Karsog Valley"]
        conn.execute(text("""
            INSERT INTO risk_explanations (risk_prediction_id, factor_name, factor_value, unit, contribution, explanation_text, display_order) VALUES
            (:pid, 'rainfall_1h', 5.00, 'mm', 0.15, 'Light rainfall well within safe limits', 1)
        """), {"pid": low_pred_kar})

        # ================================================================
        # INCIDENTS (2) — FLOOD/HIGH/IN_PROGRESS + LANDSLIDE/RESOLVED
        # Linked to the HIGH prediction
        # ================================================================
        inc_z1 = zone_ids["Demo Zone - Mandi Town"]
        conn.execute(text("""
            INSERT INTO incidents
            (zone_id, location_id, geom, incident_type, severity, status, description,
             source_prediction_id, started_at, resolved_at, created_by, data_origin)
            VALUES
            (:zid, :lid, ST_SetSRID(ST_MakePoint(76.932, 31.712), 4326),
             'FLOOD', 'HIGH', 'IN_PROGRESS',
             'Demo: Active flooding near Mandi Bus Stand. Water level rising rapidly.',
             :pid, :started, NULL, :cb, 'SIMULATED')
        """), {
            "zid": inc_z1,
            "lid": loc_ids["Demo Location - Mandi Bus Stand"],
            "pid": high_pred,
            "started": now - timedelta(hours=3),
            "cb": user_commander,
        })
        inc_flood_id = conn.execute(text(
            "SELECT id FROM incidents WHERE incident_type='FLOOD' AND status='IN_PROGRESS' ORDER BY id DESC LIMIT 1"
        )).scalar()

        inc_z3 = zone_ids["Demo Zone - Jogindernagar"]
        resolved_time = now - timedelta(hours=12)
        conn.execute(text("""
            INSERT INTO incidents
            (zone_id, geom, incident_type, severity, status, description,
             source_prediction_id, started_at, resolved_at, created_by, data_origin)
            VALUES
            (:zid, ST_SetSRID(ST_MakePoint(76.780, 31.989), 4326),
             'LANDSLIDE', 'MODERATE', 'RESOLVED',
             'Demo: Minor landslide on Jogindernagar approach road. Cleared.',
             NULL, :started, :resolved, :cb, 'SIMULATED')
        """), {
            "zid": inc_z3,
            "started": now - timedelta(hours=36),
            "resolved": resolved_time,
            "cb": user_commander,
        })
        inc_ls_id = conn.execute(text(
            "SELECT id FROM incidents WHERE incident_type='LANDSLIDE' ORDER BY id DESC LIMIT 1"
        )).scalar()

        # ================================================================
        # ALERTS (2) — one ACTIVE, one ACKNOWLEDGED
        # ================================================================
        conn.execute(text("""
            INSERT INTO alerts
            (zone_id, alert_type, severity, message, incident_id, source_prediction_id,
             status, issued_at, expires_at, issued_by, data_origin)
            VALUES
            (:zid, 'FLOOD', 'HIGH',
             'Demo: High flood risk alert for Mandi Town. Immediate action recommended.',
             :iid, :pid, 'ACTIVE', :issued, :expires, :ib, 'SIMULATED')
        """), {
            "zid": inc_z1, "iid": inc_flood_id, "pid": high_pred,
            "issued": now - timedelta(hours=2, minutes=45),
            "expires": now + timedelta(hours=6),
            "ib": user_commander,
        })

        conn.execute(text("""
            INSERT INTO alerts
            (zone_id, alert_type, severity, message, incident_id, source_prediction_id,
             status, issued_at, expires_at, issued_by, acknowledged_at, acknowledged_by, data_origin)
            VALUES
            (:zid, 'LANDSLIDE', 'MODERATE',
             'Demo: Moderate landslide risk in Jogindernagar area. Monitor conditions.',
             NULL, :pid, 'ACKNOWLEDGED', :issued, :expires, :ib, :ack_at, :ack_by, 'SIMULATED')
        """), {
            "zid": inc_z3, "pid": mod_pred_jog,
            "issued": now - timedelta(hours=18),
            "expires": now + timedelta(hours=2),
            "ib": user_commander,
            "ack_at": now - timedelta(hours=17),
            "ack_by": user_commander,
        })

        # ================================================================
        # RESCUE_TEAMS (2)
        # ================================================================
        conn.execute(text("""
            INSERT INTO rescue_teams (authority_id, name, team_type, status, geom) VALUES
            (:aid, 'Demo NDRF Alpha Team', 'NDRF', 'DEPLOYED',
             ST_SetSRID(ST_MakePoint(76.931, 31.711), 4326)),
            (:aid, 'Demo SDRF Bravo Team', 'SDRF', 'AVAILABLE',
             ST_SetSRID(ST_MakePoint(76.900, 31.530), 4326))
        """), {"aid": auth_id})
        team_alpha = conn.execute(text("SELECT id FROM rescue_teams WHERE name = 'Demo NDRF Alpha Team'")).scalar()
        team_bravo = conn.execute(text("SELECT id FROM rescue_teams WHERE name = 'Demo SDRF Bravo Team'")).scalar()

        # ================================================================
        # RESCUE_RESOURCES (4)
        # ================================================================
        conn.execute(text("""
            INSERT INTO rescue_resources (authority_id, team_id, resource_type, name, quantity, status, geom) VALUES
            (:aid, :t1, 'BOAT',       'Demo Rescue Boat RB-01',       2, 'DEPLOYED',
             ST_SetSRID(ST_MakePoint(76.932, 31.712), 4326)),
            (:aid, :t1, 'MEDICAL_KIT','Demo Medical Kit MK-01',       5, 'DEPLOYED',
             ST_SetSRID(ST_MakePoint(76.931, 31.711), 4326)),
            (:aid, :t2, 'EXCAVATOR',  'Demo Excavator EX-01',         1, 'AVAILABLE',
             ST_SetSRID(ST_MakePoint(76.900, 31.530), 4326)),
            (:aid, NULL,'GENERATOR',  'Demo Portable Generator GN-01',3, 'AVAILABLE',
             ST_SetSRID(ST_MakePoint(76.935, 31.715), 4326))
        """), {"aid": auth_id, "t1": team_alpha, "t2": team_bravo})
        res_boat = conn.execute(text("SELECT id FROM rescue_resources WHERE name = 'Demo Rescue Boat RB-01'")).scalar()
        res_excavator = conn.execute(text("SELECT id FROM rescue_resources WHERE name = 'Demo Excavator EX-01'")).scalar()

        # ================================================================
        # RESPONSE_ACTIONS (2) — one IN_PROGRESS, one PLANNED
        # ================================================================
        conn.execute(text("""
            INSERT INTO response_actions (incident_id, action_type, status, priority, started_at, notes, created_by) VALUES
            (:iid1, 'EVACUATION', 'IN_PROGRESS', 'HIGH', :started,
             'Demo: Evacuating residents from flood-affected areas near Mandi Bus Stand', :cb),
            (:iid1, 'SEARCH_AND_RESCUE', 'PLANNED', 'CRITICAL', NULL,
             'Demo: Planned search and rescue operation for stranded residents', :cb)
        """), {"iid1": inc_flood_id, "started": now - timedelta(hours=2, minutes=30), "cb": user_commander})
        ra_evac = conn.execute(text("SELECT id FROM response_actions WHERE action_type='EVACUATION' ORDER BY id DESC LIMIT 1")).scalar()
        ra_sar = conn.execute(text("SELECT id FROM response_actions WHERE action_type='SEARCH_AND_RESCUE' ORDER BY id DESC LIMIT 1")).scalar()

        # ================================================================
        # RESPONSE_ASSIGNMENTS (2)
        # One IN_PROGRESS with team DEPLOYED; one PLANNED with resource ASSIGNED
        # ================================================================
        conn.execute(text("""
            INSERT INTO response_assignments (response_action_id, team_id, status, assigned_by) VALUES
            (:raid, :tid, 'DEPLOYED', :ab)
        """), {"raid": ra_evac, "tid": team_alpha, "ab": user_coordinator})

        conn.execute(text("""
            INSERT INTO response_assignments (response_action_id, resource_id, status, assigned_by) VALUES
            (:raid, :rid, 'ASSIGNED', :ab)
        """), {"raid": ra_sar, "rid": res_excavator, "ab": user_coordinator})

        # ================================================================
        # AUDIT_LOGS (~4)
        # ================================================================
        conn.execute(text("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) VALUES
            (:u1, 'CREATE', 'incident', :inc1, '{"description":"Demo flood incident created"}'::jsonb),
            (:u1, 'CREATE', 'alert',    NULL,   '{"description":"Demo flood alert issued"}'::jsonb),
            (:u2, 'CREATE', 'response_assignment', NULL, '{"description":"Demo team assigned to evacuation"}'::jsonb),
            (:u1, 'UPDATE', 'incident', :inc2, '{"description":"Demo landslide incident resolved","old_status":"IN_PROGRESS","new_status":"RESOLVED"}'::jsonb)
        """), {"u1": user_commander, "u2": user_coordinator, "inc1": inc_flood_id, "inc2": inc_ls_id})

        print("Seed completed successfully!")
        # Print summary counts
        for tbl in [
            "roles", "authorities", "users", "data_sources", "zones", "locations",
            "sensor_nodes", "observations", "terrain_features", "historical_events",
            "risk_predictions", "risk_explanations", "incidents", "alerts",
            "rescue_teams", "rescue_resources", "response_actions", "response_assignments",
            "audit_logs",
        ]:
            cnt = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar()
            print(f"  {tbl}: {cnt}")


if __name__ == "__main__":
    main()
