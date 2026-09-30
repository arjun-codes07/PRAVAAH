"""Dashboard service aggregating high-level risk, incidents, alerts, sensor health, environmental indicators, and resources."""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings

def get_dashboard_summary(db: Session, authority_id: int | None) -> Dict[str, Any]:
    """Build dashboard summary filtered by user authority_id."""
    auth_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    params = {"auth_id": authority_id} if authority_id is not None else {}
    
    # 1. Risk counts by level (ACTIVE predictions)
    risk_sql = text(f"""
        SELECT rp.overall_risk_level, COUNT(*) as cnt
        FROM risk_predictions rp
        JOIN zones z ON rp.zone_id = z.id
        WHERE rp.status = 'ACTIVE' {auth_filter}
        GROUP BY rp.overall_risk_level
    """)
    risk_rows = db.execute(risk_sql, params).all()
    risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    for rlevel, cnt in risk_rows:
        if rlevel in risk_counts:
            risk_counts[rlevel] = cnt

    # 2. High risk zones (HIGH or CRITICAL ACTIVE predictions)
    hrz_sql = text(f"""
        SELECT rp.zone_id, z.name as zone_name, rp.overall_risk_level as risk_level, rp.predicted_at, rp.data_origin
        FROM risk_predictions rp
        JOIN zones z ON rp.zone_id = z.id
        WHERE rp.status = 'ACTIVE' AND rp.overall_risk_level IN ('HIGH', 'CRITICAL') {auth_filter}
        ORDER BY rp.predicted_at DESC
    """)
    hrz_rows = db.execute(hrz_sql, params).mappings().all()
    high_risk_zones = [dict(r) for r in hrz_rows]

    # 3. Recent changes (ACTIVE vs most recent SUPERSEDED prediction per zone)
    changes_sql = text(f"""
        WITH active_preds AS (
            SELECT rp.zone_id, z.name as zone_name, rp.overall_risk_level as current_level, rp.predicted_at, rp.data_origin
            FROM risk_predictions rp
            JOIN zones z ON rp.zone_id = z.id
            WHERE rp.status = 'ACTIVE' {auth_filter}
        ),
        latest_superseded AS (
            SELECT DISTINCT ON (rp.zone_id) rp.zone_id, rp.overall_risk_level as prev_level
            FROM risk_predictions rp
            JOIN zones z ON rp.zone_id = z.id
            WHERE rp.status = 'SUPERSEDED' {auth_filter}
            ORDER BY rp.zone_id, rp.predicted_at DESC
        )
        SELECT a.zone_id, a.zone_name, s.prev_level as previous_level, a.current_level, a.predicted_at as changed_at, a.data_origin
        FROM active_preds a
        JOIN latest_superseded s ON a.zone_id = s.zone_id
        WHERE a.current_level <> s.prev_level
    """)
    changes_rows = db.execute(changes_sql, params).mappings().all()
    recent_changes = [dict(r) for r in changes_rows]

    # 4. Active incidents (REPORTED, VERIFIED, IN_PROGRESS)
    inc_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    inc_sql = text(f"""
        SELECT i.id, i.incident_type, i.severity, i.status, i.zone_id, i.created_at, i.data_origin
        FROM incidents i
        JOIN zones z ON i.zone_id = z.id
        WHERE i.status IN ('REPORTED', 'VERIFIED', 'IN_PROGRESS') {inc_filter}
        ORDER BY i.created_at DESC
    """)
    inc_rows = db.execute(inc_sql, params).mappings().all()
    by_sev_inc = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    for r in inc_rows:
        sev = r["severity"]
        if sev in by_sev_inc:
            by_sev_inc[sev] += 1
    active_incidents = {
        "count": len(inc_rows),
        "by_severity": by_sev_inc,
        "latest": [dict(r) for r in inc_rows[:5]]
    }

    # 5. Active alerts (status ACTIVE or ACKNOWLEDGED, not expired and not CANCELLED)
    alt_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    alt_sql = text(f"""
        SELECT a.id, a.alert_type, a.severity, a.status, a.zone_id, a.issued_at, a.expires_at, a.data_origin
        FROM alerts a
        JOIN zones z ON a.zone_id = z.id
        WHERE a.status IN ('ACTIVE', 'ACKNOWLEDGED') 
          AND (a.expires_at IS NULL OR a.expires_at > NOW()) {alt_filter}
        ORDER BY a.issued_at DESC
    """)
    alt_rows = db.execute(alt_sql, params).mappings().all()
    by_sev_alt = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    for r in alt_rows:
        sev = r["severity"]
        if sev in by_sev_alt:
            by_sev_alt[sev] += 1
    active_alerts = {
        "count": len(alt_rows),
        "by_severity": by_sev_alt,
        "latest": [dict(r) for r in alt_rows[:5]]
    }

    # 6. Sensor health (active, stale, inactive)
    sn_filter = "WHERE z.authority_id = :auth_id" if authority_id is not None else ""
    sn_sql = text(f"""
        SELECT sn.id, sn.status, sn.last_seen_at, COALESCE(ds.stale_after_minutes, :default_stale) as stale_minutes
        FROM sensor_nodes sn
        JOIN data_sources ds ON sn.data_source_id = ds.id
        JOIN zones z ON sn.zone_id = z.id
        {sn_filter}
    """)
    sn_params = {**params, "default_stale": settings.STALE_DEFAULT_MINUTES}
    sn_rows = db.execute(sn_sql, sn_params).mappings().all()
    
    active_cnt = 0
    stale_cnt = 0
    inactive_cnt = 0
    now_utc = datetime.now(timezone.utc)

    for r in sn_rows:
        s_status = r["status"]
        last_seen = r["last_seen_at"]
        stale_mins = r["stale_minutes"]
        
        if s_status != "ACTIVE":
            inactive_cnt += 1
        elif last_seen is None:
            stale_cnt += 1
        else:
            diff_mins = (now_utc - last_seen).total_seconds() / 60.0
            if diff_mins > stale_mins:
                stale_cnt += 1
            else:
                active_cnt += 1
                
    sensor_health = {
        "active": active_cnt,
        "stale": stale_cnt,
        "inactive": inactive_cnt,
    }

    # 7. Environmental indicators (Aggregated latest VALID reading per active sensor node)
    env_filter = "WHERE z.authority_id = :auth_id" if authority_id is not None else ""
    env_sql = text(f"""
        WITH latest_obs AS (
            SELECT DISTINCT ON (o.sensor_node_id) o.*
            FROM observations o
            JOIN sensor_nodes sn ON o.sensor_node_id = sn.id
            JOIN zones z ON o.zone_id = z.id
            {env_filter} AND sn.status = 'ACTIVE' AND o.quality_status = 'VALID'
            ORDER BY o.sensor_node_id, o.observed_at DESC
        )
        SELECT 
            AVG(rainfall_1h_mm) as avg_rain,
            AVG(soil_moisture_pct) as avg_soil,
            AVG(water_level_m) as avg_water,
            AVG(temperature_c) as avg_temp,
            AVG(humidity_pct) as avg_hum,
            MAX(observed_at) as max_as_of
        FROM latest_obs
    """)
    env_row = db.execute(env_sql, params).mappings().first()
    
    environmental_indicators = {
        "as_of": env_row["max_as_of"] or now_utc,
        "avg_rainfall_1h_mm": round(float(env_row["avg_rain"]), 2) if env_row["avg_rain"] is not None else None,
        "avg_soil_moisture_pct": round(float(env_row["avg_soil"]), 2) if env_row["avg_soil"] is not None else None,
        "avg_water_level_m": round(float(env_row["avg_water"]), 2) if env_row["avg_water"] is not None else None,
        "avg_temperature_c": round(float(env_row["avg_temp"]), 2) if env_row["avg_temp"] is not None else None,
        "avg_humidity_pct": round(float(env_row["avg_hum"]), 2) if env_row["avg_hum"] is not None else None,
    }

    # 8. Resource status summary (rescue_resources + rescue_teams)
    res_sql = text("""
        SELECT status, count(*) as cnt FROM (
            SELECT status FROM rescue_resources
            UNION ALL
            SELECT status FROM rescue_teams
        ) combined
        GROUP BY status
    """)
    res_rows = db.execute(res_sql).all()
    resource_status = {"available": 0, "deployed": 0, "maintenance": 0}
    for rstat, cnt in res_rows:
        if rstat == "AVAILABLE":
            resource_status["available"] += cnt
        elif rstat == "DEPLOYED":
            resource_status["deployed"] += cnt
        elif rstat in ("MAINTENANCE", "OFFLINE"):
            resource_status["maintenance"] += cnt

    # 9. Data origins present
    do_sql = text("SELECT DISTINCT data_origin FROM data_sources WHERE status = 'ACTIVE'")
    do_rows = db.execute(do_sql).scalars().all()

    return {
        "risk_counts_by_level": risk_counts,
        "high_risk_zones": high_risk_zones,
        "recent_changes": recent_changes,
        "active_incidents": active_incidents,
        "active_alerts": active_alerts,
        "sensor_health": sensor_health,
        "environmental_indicators": environmental_indicators,
        "resource_status": resource_status,
        "data_origins_present": list(do_rows),
    }
