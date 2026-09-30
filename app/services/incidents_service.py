"""Incident service for listing and detail queries."""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

def get_incidents(
    db: Session,
    authority_id: Optional[int],
    status_filter: Optional[str] = None,
    severity: Optional[str] = None,
    incident_type: Optional[str] = None,
    zone_id: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated incidents filtered by authority, status, severity, incident_type, zone, and date range."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if zone_id is not None:
        where_clauses.append("i.zone_id = :zone_id")
        params["zone_id"] = zone_id
    if status_filter:
        where_clauses.append("i.status = :status_filter")
        params["status_filter"] = status_filter
    if severity:
        where_clauses.append("i.severity = :severity")
        params["severity"] = severity
    if incident_type:
        where_clauses.append("i.incident_type = :incident_type")
        params["incident_type"] = incident_type
    if from_date:
        where_clauses.append("i.created_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        where_clauses.append("i.created_at <= :to_date")
        params["to_date"] = to_date

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"SELECT COUNT(*) FROM incidents i JOIN zones z ON i.zone_id = z.id WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            i.id, i.incident_type, i.severity, i.status, i.zone_id, i.location_id,
            i.started_at, i.resolved_at, i.created_at, i.data_origin
        FROM incidents i
        JOIN zones z ON i.zone_id = z.id
        WHERE {where_sql}
        ORDER BY i.created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, params).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

def get_incident_detail(db: Session, authority_id: Optional[int], incident_id: int) -> Dict[str, Any]:
    """Retrieve complete incident detail including zone, location, source prediction, alerts, and response actions with team/resource details."""
    auth_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    params: Dict[str, Any] = {"iid": incident_id}
    if authority_id is not None:
        params["auth_id"] = authority_id

    sql = text(f"""
        SELECT 
            i.id, i.incident_type, i.severity, i.status, i.zone_id, i.location_id,
            i.source_prediction_id, i.description, ST_AsGeoJSON(i.geom) as geojson,
            i.started_at, i.resolved_at, i.created_at, i.data_origin
        FROM incidents i
        JOIN zones z ON i.zone_id = z.id
        WHERE i.id = :iid {auth_filter}
    """)
    inc = db.execute(sql, params).mappings().first()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found or access denied")

    # Zone
    z_sql = text("SELECT id, name, zone_type, admin_code FROM zones WHERE id = :zid")
    zone_dict = dict(db.execute(z_sql, {"zid": inc["zone_id"]}).mappings().first())

    # Location
    location_dict = None
    if inc["location_id"]:
        loc_sql = text("SELECT id, name, location_type FROM locations WHERE id = :lid")
        loc_row = db.execute(loc_sql, {"lid": inc["location_id"]}).mappings().first()
        if loc_row:
            location_dict = dict(loc_row)

    # Source prediction summary
    pred_dict = None
    if inc["source_prediction_id"]:
        pred_sql = text("SELECT id, model_name, overall_risk_level, predicted_at FROM risk_predictions WHERE id = :pid")
        pred_row = db.execute(pred_sql, {"pid": inc["source_prediction_id"]}).mappings().first()
        if pred_row:
            pred_dict = dict(pred_row)

    # Alerts
    alt_sql = text("SELECT id, alert_type, severity, status, message, issued_at FROM alerts WHERE incident_id = :iid")
    alt_rows = db.execute(alt_sql, {"iid": incident_id}).mappings().all()

    # Response actions with assignments & team/resource details
    act_sql = text("SELECT id, action_type, status, priority, notes, started_at, completed_at FROM response_actions WHERE incident_id = :iid")
    act_rows = db.execute(act_sql, {"iid": incident_id}).mappings().all()
    
    actions_list = []
    for act in act_rows:
        act_id = act["id"]
        asgn_sql = text("""
            SELECT 
                ra.id as assignment_id, ra.status as assignment_status, ra.assigned_at, ra.released_at,
                t.id as team_id, t.name as team_name, t.team_type,
                res.id as resource_id, res.name as resource_name, res.resource_type
            FROM response_assignments ra
            LEFT JOIN rescue_teams t ON ra.team_id = t.id
            LEFT JOIN rescue_resources res ON ra.resource_id = res.id
            WHERE ra.response_action_id = :aid
        """)
        asgn_rows = db.execute(asgn_sql, {"aid": act_id}).mappings().all()
        
        actions_list.append({
            **dict(act),
            "assignments": [dict(a) for a in asgn_rows],
        })

    return {
        "id": inc["id"],
        "incident_type": inc["incident_type"],
        "severity": inc["severity"],
        "status": inc["status"],
        "zone_id": inc["zone_id"],
        "location_id": inc["location_id"],
        "description": inc["description"],
        "geometry": json.loads(inc["geojson"]) if inc["geojson"] else None,
        "started_at": inc["started_at"],
        "resolved_at": inc["resolved_at"],
        "created_at": inc["created_at"],
        "data_origin": inc["data_origin"],
        "zone": zone_dict,
        "location": location_dict,
        "source_prediction": pred_dict,
        "alerts": [dict(a) for a in alt_rows],
        "response_actions": actions_list,
    }


def create_incident(db: Session, current_user, payload) -> Dict[str, Any]:
    """Create a new incident and record an audit log in one transaction."""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)
    started_at = payload.started_at or now_utc

    # Verify zone exists and authority match
    z_sql = text("SELECT id, authority_id FROM zones WHERE id = :zid")
    zone = db.execute(z_sql, {"zid": payload.zone_id}).mappings().first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone {payload.zone_id} not found")
    if current_user.authority_id is not None and zone["authority_id"] != current_user.authority_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create incident outside user authority")

    geom_expr = "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)" if (payload.latitude is not None and payload.longitude is not None) else "NULL"

    insert_sql = text(f"""
        INSERT INTO incidents (
            zone_id, location_id, geom, incident_type, severity, status,
            description, source_prediction_id, started_at, created_by, data_origin
        ) VALUES (
            :zid, :lid, {geom_expr}, :itype, :sev, 'OPEN',
            :desc, :spid, :started_at, :uid, :origin
        ) RETURNING id
    """)

    params = {
        "zid": payload.zone_id,
        "lid": payload.location_id,
        "itype": payload.incident_type,
        "sev": payload.severity,
        "desc": payload.description,
        "spid": payload.source_prediction_id,
        "started_at": started_at,
        "uid": current_user.id,
        "origin": payload.data_origin,
    }
    if payload.latitude is not None and payload.longitude is not None:
        params["lat"] = payload.latitude
        params["lon"] = payload.longitude

    inc_id = db.execute(insert_sql, params).scalar()

    # Audit log
    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'CREATE_INCIDENT', 'incidents', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": inc_id,
        "meta": json.dumps({"incident_type": payload.incident_type, "severity": payload.severity, "zone_id": payload.zone_id}),
    })

    db.commit()
    return get_incident_detail(db, current_user.authority_id, inc_id)


def update_incident(db: Session, current_user, incident_id: int, payload) -> Dict[str, Any]:
    """Update incident status, severity, description, or resolved_at and record an audit log."""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)

    # Check incident existence and authority
    inc_sql = text("""
        SELECT i.id, i.status, i.started_at, z.authority_id
        FROM incidents i
        JOIN zones z ON i.zone_id = z.id
        WHERE i.id = :iid
    """)
    inc = db.execute(inc_sql, {"iid": incident_id}).mappings().first()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found")
    if current_user.authority_id is not None and inc["authority_id"] != current_user.authority_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update incident outside user authority")

    updates = []
    params: Dict[str, Any] = {"iid": incident_id}

    if payload.severity is not None:
        updates.append("severity = :severity")
        params["severity"] = payload.severity

    if payload.description is not None:
        updates.append("description = :description")
        params["description"] = payload.description

    # Status & resolved_at handling per chk_inc_resolved_consistency
    new_status = payload.status if payload.status is not None else inc["status"]
    if payload.status is not None:
        updates.append("status = :status")
        params["status"] = payload.status

    if new_status == "RESOLVED":
        resolved_at = payload.resolved_at or now_utc
        updates.append("resolved_at = :resolved_at")
        params["resolved_at"] = resolved_at
    elif payload.status is not None and new_status != "RESOLVED":
        updates.append("resolved_at = NULL")

    if not updates:
        return get_incident_detail(db, current_user.authority_id, incident_id)

    set_clause = ", ".join(updates)
    update_sql = text(f"UPDATE incidents SET {set_clause} WHERE id = :iid")
    db.execute(update_sql, params)

    # Audit log
    meta = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "resolved_at" in meta and meta["resolved_at"]:
        meta["resolved_at"] = meta["resolved_at"].isoformat()

    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'UPDATE_INCIDENT', 'incidents', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": incident_id,
        "meta": json.dumps(meta),
    })

    db.commit()
    return get_incident_detail(db, current_user.authority_id, incident_id)


def create_response_action(db: Session, current_user, incident_id: int, payload) -> Dict[str, Any]:
    """Create a response action for an incident and record an audit log."""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)

    # Verify incident
    inc_sql = text("""
        SELECT i.id, z.authority_id
        FROM incidents i
        JOIN zones z ON i.zone_id = z.id
        WHERE i.id = :iid
    """)
    inc = db.execute(inc_sql, {"iid": incident_id}).mappings().first()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {incident_id} not found")
    if current_user.authority_id is not None and inc["authority_id"] != current_user.authority_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create response action outside user authority")

    insert_sql = text("""
        INSERT INTO response_actions (incident_id, action_type, status, priority, started_at, notes, created_by)
        VALUES (:iid, :atype, 'PLANNED', :priority, :started, :notes, :uid)
        RETURNING id
    """)
    act_id = db.execute(insert_sql, {
        "iid": incident_id,
        "atype": payload.action_type,
        "priority": payload.priority,
        "started": now_utc,
        "notes": payload.notes,
        "uid": current_user.id,
    }).scalar()

    # Audit log
    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'CREATE_RESPONSE_ACTION', 'response_actions', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": act_id,
        "meta": json.dumps({"incident_id": incident_id, "action_type": payload.action_type, "priority": payload.priority}),
    })

    db.commit()

    # Return action row
    row = db.execute(text("SELECT * FROM response_actions WHERE id = :aid"), {"aid": act_id}).mappings().first()
    d = dict(row)
    d["assignments"] = []
    return d


def update_response_action(db: Session, current_user, action_id: int, payload) -> Dict[str, Any]:
    """Update response action status, priority, or notes."""
    from datetime import timezone
    now_utc = datetime.now(timezone.utc)

    act_sql = text("""
        SELECT ra.id, ra.incident_id, ra.started_at, z.authority_id
        FROM response_actions ra
        JOIN incidents i ON ra.incident_id = i.id
        JOIN zones z ON i.zone_id = z.id
        WHERE ra.id = :aid
    """)
    act = db.execute(act_sql, {"aid": action_id}).mappings().first()
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Response action {action_id} not found")
    if current_user.authority_id is not None and act["authority_id"] != current_user.authority_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update action outside user authority")

    updates = []
    params: Dict[str, Any] = {"aid": action_id}

    if payload.status is not None:
        updates.append("status = :status")
        params["status"] = payload.status
        if payload.status == "COMPLETED":
            updates.append("completed_at = COALESCE(:completed_at, now())")
            params["completed_at"] = payload.completed_at or now_utc
        elif payload.status == "IN_PROGRESS" and act["started_at"] is None:
            updates.append("started_at = COALESCE(:started_at, now())")
            params["started_at"] = payload.started_at or now_utc

    if payload.priority is not None:
        updates.append("priority = :priority")
        params["priority"] = payload.priority

    if payload.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = payload.notes

    if payload.completed_at is not None and "completed_at" not in params:
        updates.append("completed_at = :completed_at")
        params["completed_at"] = payload.completed_at

    if not updates:
        row = db.execute(text("SELECT * FROM response_actions WHERE id = :aid"), {"aid": action_id}).mappings().first()
        return dict(row)

    set_clause = ", ".join(updates)
    db.execute(text(f"UPDATE response_actions SET {set_clause} WHERE id = :aid"), params)

    # Audit log
    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'UPDATE_RESPONSE_ACTION', 'response_actions', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": action_id,
        "meta": json.dumps({k: str(v) for k, v in payload.model_dump(exclude_unset=True).items()}),
    })

    db.commit()
    row = db.execute(text("SELECT * FROM response_actions WHERE id = :aid"), {"aid": action_id}).mappings().first()
    return dict(row)
