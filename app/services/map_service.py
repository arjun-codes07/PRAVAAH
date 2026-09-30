"""Map service serving valid GeoJSON FeatureCollection layers."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def get_map_features(
    db: Session,
    authority_id: Optional[int],
    layers_str: str = "zones,incidents,sensors,resources,teams,rescue_routes,evacuation_zones,evacuation_routes",
    bbox: Optional[str] = None,
    min_level: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate GeoJSON FeatureCollection containing selected spatial feature layers."""
    requested_layers = [l.strip().lower() for l in layers_str.split(",") if l.strip()]
    features: List[Dict[str, Any]] = []

    bbox_filter = ""
    bbox_params: Dict[str, Any] = {}
    if bbox:
        try:
            coords = [float(x.strip()) for x in bbox.split(",")]
            if len(coords) == 4:
                min_lon, min_lat, max_lon, max_lat = coords
                bbox_filter = "AND ST_Intersects(geom, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
                bbox_params = {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat}
        except ValueError:
            pass

    auth_filter_zone = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    auth_params = {"auth_id": authority_id} if authority_id is not None else {}
    base_params = {**auth_params, **bbox_params}

    # -------------------------------------------------------------------------
    # 1. ZONES layer
    # -------------------------------------------------------------------------
    if "zones" in requested_layers:
        risk_levels_order = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
        min_level_filter = ""
        if min_level and min_level.upper() in risk_levels_order:
            idx = risk_levels_order.index(min_level.upper())
            allowed = risk_levels_order[idx:]
            min_level_filter = "AND rp.overall_risk_level IN (" + ",".join(f"'{lvl}'" for lvl in allowed) + ")"

        zones_sql = text(f"""
            SELECT 
                z.id as zone_id, z.name, z.zone_type, z.admin_code,
                ST_AsGeoJSON(z.geom) as geojson,
                rp.overall_risk_level, rp.flood_risk_level, rp.landslide_risk_level,
                rp.flood_probability, rp.landslide_probability, rp.confidence,
                rp.recommended_action, rp.predicted_at, rp.horizon_minutes,
                z.status, 'SIMULATED' as data_origin
            FROM zones z
            LEFT JOIN risk_predictions rp ON z.id = rp.zone_id AND rp.status = 'ACTIVE'
            WHERE z.status = 'ACTIVE' {auth_filter_zone} {bbox_filter} {min_level_filter}
        """)
        rows = db.execute(zones_sql, base_params).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                overall_lvl = r["overall_risk_level"] or "LOW"

                # Continuous risk score approximation from level / probabilities
                score = 0.5
                if overall_lvl == "CRITICAL":
                    score = 3.8
                elif overall_lvl == "HIGH":
                    score = 2.6
                elif overall_lvl == "MODERATE":
                    score = 1.6
                if r["flood_probability"] is not None or r["landslide_probability"] is not None:
                    fp = float(r["flood_probability"] or 0)
                    lp = float(r["landslide_probability"] or 0)
                    prob_score = round(max(fp, lp) * 4.0, 2)
                    if prob_score > 0:
                        score = prob_score

                # Determine primary hazard
                primary_hazard = "General Flood & Landslide"
                if (r["flood_probability"] or 0) >= (r["landslide_probability"] or 0):
                    primary_hazard = "River Flash Flood"
                else:
                    primary_hazard = "Debris Flow Landslide"

                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "zones",
                        "zone_id": r["zone_id"],
                        "name": r["name"],
                        "zone_type": r["zone_type"],
                        "admin_code": r["admin_code"],
                        "overall_risk_level": overall_lvl,
                        "flood_risk_level": r["flood_risk_level"] or "LOW",
                        "landslide_risk_level": r["landslide_risk_level"] or "LOW",
                        "flood_probability": float(r["flood_probability"]) if r["flood_probability"] is not None else None,
                        "landslide_probability": float(r["landslide_probability"]) if r["landslide_probability"] is not None else None,
                        "risk_score": score,
                        "primary_hazard": primary_hazard,
                        "confidence": float(r["confidence"]) if r["confidence"] is not None else 0.85,
                        "recommended_action": r["recommended_action"],
                        "predicted_at": r["predicted_at"].isoformat() if r["predicted_at"] else None,
                        "horizon_minutes": r["horizon_minutes"] or 60,
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 2. INCIDENTS layer
    # -------------------------------------------------------------------------
    if "incidents" in requested_layers:
        inc_sql = text(f"""
            SELECT 
                i.id, i.incident_type as type, i.severity, i.status,
                i.description, i.started_at, z.id as zone_id, z.name as zone_name,
                ST_AsGeoJSON(i.geom) as geojson, i.data_origin
            FROM incidents i
            JOIN zones z ON i.zone_id = z.id
            WHERE 1=1 {auth_filter_zone} {bbox_filter}
        """)
        rows = db.execute(inc_sql, base_params).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "incidents",
                        "id": r["id"],
                        "type": r["type"],
                        "severity": r["severity"],
                        "status": r["status"],
                        "description": r["description"] or f"Active {r['type']} Incident reported in {r['zone_name']}",
                        "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                        "zone_id": r["zone_id"],
                        "zone_name": r["zone_name"],
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 3. SENSORS layer (with latest real observations)
    # -------------------------------------------------------------------------
    if "sensors" in requested_layers:
        now_utc = datetime.now(timezone.utc)
        sen_sql = text(f"""
            SELECT 
                sn.id, sn.node_id, sn.sensor_type, sn.status, sn.last_seen_at,
                ST_AsGeoJSON(sn.geom) as geojson, sn.data_origin,
                COALESCE(ds.stale_after_minutes, :default_stale) as stale_minutes,
                z.name as zone_name,
                latest_obs.rainfall_1h_mm,
                latest_obs.water_level_m,
                latest_obs.soil_moisture_pct,
                latest_obs.temperature_c,
                latest_obs.humidity_pct,
                latest_obs.observed_at as latest_observed_at
            FROM sensor_nodes sn
            JOIN data_sources ds ON sn.data_source_id = ds.id
            JOIN zones z ON sn.zone_id = z.id
            LEFT JOIN LATERAL (
                SELECT 
                    rainfall_1h_mm, water_level_m, soil_moisture_pct,
                    temperature_c, humidity_pct, observed_at
                FROM observations obs
                WHERE obs.sensor_node_id = sn.id AND obs.quality_status = 'VALID'
                ORDER BY obs.observed_at DESC
                LIMIT 1
            ) latest_obs ON TRUE
            WHERE 1=1 {auth_filter_zone} {bbox_filter}
        """)
        sen_params = {**base_params, "default_stale": settings.STALE_DEFAULT_MINUTES}
        rows = db.execute(sen_sql, sen_params).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                last_seen = r["last_seen_at"]
                stale_mins = r["stale_minutes"]
                is_stale = False
                if last_seen is None:
                    is_stale = True
                else:
                    diff_mins = (now_utc - last_seen).total_seconds() / 60.0
                    is_stale = diff_mins > stale_mins

                rf = float(r["rainfall_1h_mm"]) if r["rainfall_1h_mm"] is not None else None
                wl = float(r["water_level_m"]) if r["water_level_m"] is not None else None
                sm = float(r["soil_moisture_pct"]) if r["soil_moisture_pct"] is not None else None

                # Visual convention: Green Normal, Yellow Warning, Orange Elevated, Red Critical
                sensor_condition = "NORMAL"
                if (wl is not None and wl >= 5.0) or (rf is not None and rf >= 50.0):
                    sensor_condition = "CRITICAL"
                elif (wl is not None and wl >= 3.5) or (rf is not None and rf >= 30.0):
                    sensor_condition = "ELEVATED"
                elif is_stale or (wl is not None and wl >= 2.5):
                    sensor_condition = "WARNING"

                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "sensors",
                        "node_id": r["node_id"],
                        "sensor_type": r["sensor_type"],
                        "status": r["status"],
                        "sensor_condition": sensor_condition,
                        "is_stale": is_stale,
                        "last_seen_at": last_seen.isoformat() if last_seen else None,
                        "zone_name": r["zone_name"],
                        "rainfall_1h_mm": rf,
                        "water_level_m": wl,
                        "soil_moisture_pct": sm,
                        "temperature_c": float(r["temperature_c"]) if r["temperature_c"] is not None else None,
                        "humidity_pct": float(r["humidity_pct"]) if r["humidity_pct"] is not None else None,
                        "latest_observed_at": r["latest_observed_at"].isoformat() if r["latest_observed_at"] else None,
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 4. RESCUE TEAMS layer
    # -------------------------------------------------------------------------
    if "teams" in requested_layers or "resources" in requested_layers:
        teams_sql = text(f"""
            SELECT 
                rt.id, rt.name, rt.team_type, rt.status,
                ST_AsGeoJSON(rt.geom) as geojson, 'SIMULATED' as data_origin,
                ra.id as action_id, ra.action_type, ra.status as action_status,
                inc.id as incident_id, inc.incident_type, inc.severity as incident_severity,
                z.name as assigned_zone_name
            FROM rescue_teams rt
            LEFT JOIN response_assignments ras ON rt.id = ras.team_id AND ras.status <> 'RELEASED'
            LEFT JOIN response_actions ra ON ras.response_action_id = ra.id
            LEFT JOIN incidents inc ON ra.incident_id = inc.id
            LEFT JOIN zones z ON inc.zone_id = z.id
            WHERE rt.geom IS NOT NULL {bbox_filter}
        """)
        rows = db.execute(teams_sql, bbox_params).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "teams",
                        "id": r["id"],
                        "name": r["name"],
                        "team_type": r["team_type"],
                        "status": r["status"],
                        "assigned_incident_id": r["incident_id"],
                        "assigned_incident_type": r["incident_type"],
                        "assigned_incident_severity": r["incident_severity"],
                        "assigned_action_type": r["action_type"],
                        "assigned_action_status": r["action_status"],
                        "destination_name": r["assigned_zone_name"] or "Command Base",
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 5. RESOURCES layer (equipment / supplies)
    # -------------------------------------------------------------------------
    if "resources" in requested_layers:
        res_sql = text(f"""
            SELECT 
                rr.id, rr.name, rr.resource_type as type, rr.quantity, rr.status,
                ST_AsGeoJSON(rr.geom) as geojson, 'SIMULATED' as data_origin,
                rt.name as team_name
            FROM rescue_resources rr
            LEFT JOIN rescue_teams rt ON rr.team_id = rt.id
            WHERE rr.geom IS NOT NULL {bbox_filter}
        """)
        rows = db.execute(res_sql, bbox_params).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "resources",
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["type"],
                        "quantity": r["quantity"],
                        "status": r["status"],
                        "team_name": r["team_name"] or "Independent Unit",
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 6. RESCUE ROUTES layer (deployment vector between team & incident)
    # -------------------------------------------------------------------------
    if "rescue_routes" in requested_layers:
        routes_sql = text("""
            SELECT 
                rt.id as team_id, rt.name as team_name, rt.status as team_status,
                inc.id as incident_id, inc.incident_type, inc.severity,
                z.name as zone_name, ra.action_type,
                ST_AsGeoJSON(ST_MakeLine(rt.geom, inc.geom)) as geojson,
                'SIMULATED' as data_origin
            FROM rescue_teams rt
            JOIN response_assignments ras ON rt.id = ras.team_id AND ras.status <> 'RELEASED'
            JOIN response_actions ra ON ras.response_action_id = ra.id
            JOIN incidents inc ON ra.incident_id = inc.id
            JOIN zones z ON inc.zone_id = z.id
            WHERE rt.geom IS NOT NULL AND inc.geom IS NOT NULL
        """)
        rows = db.execute(routes_sql).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "rescue_routes",
                        "route_type": "RESCUE",
                        "team_id": r["team_id"],
                        "team_name": r["team_name"],
                        "team_status": r["team_status"],
                        "incident_id": r["incident_id"],
                        "incident_type": r["incident_type"],
                        "incident_severity": r["severity"],
                        "action_type": r["action_type"],
                        "destination": r["zone_name"],
                        "route_label": f"Rescue Route: {r['team_name']} -> Incident #{r['incident_id']} ({r['incident_type']})",
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 7. EVACUATION ZONES layer (civic safe shelters buffered around locations)
    # -------------------------------------------------------------------------
    if "evacuation_zones" in requested_layers:
        evac_sql = text("""
            SELECT 
                loc.id, loc.name, loc.location_type, z.id as zone_id, z.name as zone_name,
                ST_AsGeoJSON(ST_Buffer(CAST(loc.geom AS geography), 350)) as geojson,
                'SIMULATED' as data_origin
            FROM locations loc
            JOIN zones z ON loc.zone_id = z.id
            WHERE loc.location_type IN ('HOSPITAL', 'SCHOOL', 'TOWN_CENTER', 'BUS_STATION')
        """)
        rows = db.execute(evac_sql).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "evacuation_zones",
                        "zone_id": r["id"],
                        "evac_code": f"EV-{r['id']:02d}",
                        "name": r["name"],
                        "shelter_type": r["location_type"],
                        "capacity": "Designated Civic Shelter (Capacity not in DB schema)",
                        "status": "ACTIVE_SHELTER",
                        "related_zone_id": r["zone_id"],
                        "related_zone_name": r["zone_name"],
                        "data_origin": r["data_origin"],
                    }
                })

    # -------------------------------------------------------------------------
    # 8. EVACUATION ROUTES layer (corridor from active incident to nearest shelter)
    # -------------------------------------------------------------------------
    if "evacuation_routes" in requested_layers:
        evac_routes_sql = text("""
            SELECT 
                inc.id as incident_id, inc.incident_type, inc.severity,
                z.name as zone_name,
                nearest_loc.id as shelter_id, nearest_loc.name as shelter_name,
                nearest_loc.location_type as shelter_type,
                ST_AsGeoJSON(ST_MakeLine(inc.geom, nearest_loc.geom)) as geojson,
                'SIMULATED' as data_origin
            FROM incidents inc
            JOIN zones z ON inc.zone_id = z.id
            CROSS JOIN LATERAL (
                SELECT loc.id, loc.name, loc.location_type, loc.geom
                FROM locations loc
                WHERE loc.location_type IN ('HOSPITAL', 'SCHOOL', 'TOWN_CENTER', 'BUS_STATION')
                ORDER BY inc.geom <-> loc.geom
                LIMIT 1
            ) nearest_loc
            WHERE inc.geom IS NOT NULL AND inc.status IN ('OPEN', 'IN_PROGRESS')
        """)
        rows = db.execute(evac_routes_sql).mappings().all()
        for r in rows:
            if r["geojson"]:
                geom = json.loads(r["geojson"])
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "evacuation_routes",
                        "route_type": "EVACUATION",
                        "incident_id": r["incident_id"],
                        "incident_type": r["incident_type"],
                        "incident_severity": r["severity"],
                        "shelter_id": r["shelter_id"],
                        "shelter_name": r["shelter_name"],
                        "shelter_type": r["shelter_type"],
                        "zone_name": r["zone_name"],
                        "status": "OPEN_CORRIDOR",
                        "route_label": f"Public Evacuation: {r['incident_type']} -> {r['shelter_name']}",
                        "data_origin": r["data_origin"],
                    }
                })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
