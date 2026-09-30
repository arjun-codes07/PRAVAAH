"""Rescue teams, resources, and response assignments service."""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

def get_rescue_teams(
    db: Session,
    authority_id: Optional[int],
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve list of rescue teams with active assignment counts."""
    where_clauses = ["1=1"]
    params: Dict[str, Any] = {}

    if authority_id is not None:
        where_clauses.append("rt.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if status_filter:
        where_clauses.append("rt.status = :status_filter")
        params["status_filter"] = status_filter

    where_sql = " AND ".join(where_clauses)
    query_sql = text(f"""
        SELECT 
            rt.id, rt.authority_id, rt.name, rt.team_type, rt.status,
            ST_Y(rt.geom) as latitude, ST_X(rt.geom) as longitude,
            rt.created_at, rt.updated_at,
            COALESCE(ac.active_count, 0) as active_assignment_count
        FROM rescue_teams rt
        LEFT JOIN (
            SELECT team_id, COUNT(*) as active_count
            FROM response_assignments
            WHERE status <> 'RELEASED' AND team_id IS NOT NULL
            GROUP BY team_id
        ) ac ON ac.team_id = rt.id
        WHERE {where_sql}
        ORDER BY rt.id ASC
    """)
    rows = db.execute(query_sql, params).mappings().all()
    return [dict(r) for r in rows]


def get_rescue_resources(
    db: Session,
    authority_id: Optional[int],
    status_filter: Optional[str] = None,
    resource_type: Optional[str] = None,
    near_lat: Optional[float] = None,
    near_lon: Optional[float] = None,
    radius_m: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Retrieve rescue resources, optionally filtered by proximity using PostGIS ST_DWithin."""
    where_clauses = ["1=1"]
    params: Dict[str, Any] = {}

    if authority_id is not None:
        where_clauses.append("rr.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if status_filter:
        where_clauses.append("rr.status = :status_filter")
        params["status_filter"] = status_filter
    if resource_type:
        where_clauses.append("rr.resource_type = :resource_type")
        params["resource_type"] = resource_type

    dist_col = "NULL as distance_m"
    order_by = "rr.id ASC"

    if near_lat is not None and near_lon is not None:
        params["nlat"] = near_lat
        params["nlon"] = near_lon
        ref_geom = "ST_SetSRID(ST_MakePoint(:nlon, :nlat), 4326)::geography"
        dist_col = f"ST_Distance(rr.geom::geography, {ref_geom}) as distance_m"
        order_by = "distance_m ASC NULLS LAST"

        if radius_m is not None and radius_m > 0:
            params["radius"] = radius_m
            where_clauses.append(f"ST_DWithin(rr.geom::geography, {ref_geom}, :radius)")

    where_sql = " AND ".join(where_clauses)
    query_sql = text(f"""
        SELECT 
            rr.id, rr.authority_id, rr.team_id, t.name as team_name,
            rr.resource_type, rr.name, rr.quantity, rr.status,
            ST_Y(rr.geom) as latitude, ST_X(rr.geom) as longitude,
            {dist_col},
            rr.created_at, rr.updated_at
        FROM rescue_resources rr
        LEFT JOIN rescue_teams t ON rr.team_id = t.id
        WHERE {where_sql}
        ORDER BY {order_by}
    """)
    rows = db.execute(query_sql, params).mappings().all()
    items = []
    for r in rows:
        d = dict(r)
        if d["distance_m"] is not None:
            d["distance_m"] = round(float(d["distance_m"]), 2)
        items.append(d)
    return items


def create_assignment(
    db: Session,
    current_user,
    action_id: int,
    payload,
) -> Dict[str, Any]:
    """Assign a team or resource to a response action, ensuring no duplicate active assignments."""
    now_utc = datetime.now(timezone.utc)

    # 1. Verify response action exists
    ra_sql = text("""
        SELECT ra.id, ra.incident_id, z.authority_id
        FROM response_actions ra
        JOIN incidents i ON ra.incident_id = i.id
        JOIN zones z ON i.zone_id = z.id
        WHERE ra.id = :aid
    """)
    act = db.execute(ra_sql, {"aid": action_id}).mappings().first()
    if not act:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Response action {action_id} not found")
    if current_user.authority_id is not None and act["authority_id"] != current_user.authority_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign outside user authority")

    team_id = payload.team_id
    resource_id = payload.resource_id

    # 2. Check team conflict
    if team_id:
        team = db.execute(text("SELECT id, name, status FROM rescue_teams WHERE id = :tid"), {"tid": team_id}).mappings().first()
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rescue team {team_id} not found")
        
        # Check active assignment
        active_count = db.execute(
            text("SELECT count(*) FROM response_assignments WHERE team_id = :tid AND status <> 'RELEASED'"),
            {"tid": team_id},
        ).scalar()
        if active_count > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Team '{team['name']}' is already actively assigned")

    # 3. Check resource conflict
    if resource_id:
        res = db.execute(text("SELECT id, name, status FROM rescue_resources WHERE id = :rid"), {"rid": resource_id}).mappings().first()
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rescue resource {resource_id} not found")
        
        # Check active assignment
        active_count = db.execute(
            text("SELECT count(*) FROM response_assignments WHERE resource_id = :rid AND status <> 'RELEASED'"),
            {"rid": resource_id},
        ).scalar()
        if active_count > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Resource '{res['name']}' is already actively assigned")

    # 4. Insert assignment
    insert_sql = text("""
        INSERT INTO response_assignments (
            response_action_id, team_id, resource_id, status, assigned_at, assigned_by
        ) VALUES (
            :aid, :tid, :rid, 'ASSIGNED', :now, :uid
        ) RETURNING id
    """)
    asgn_id = db.execute(insert_sql, {
        "aid": action_id,
        "tid": team_id,
        "rid": resource_id,
        "now": now_utc,
        "uid": current_user.id,
    }).scalar()

    # 5. Sync team / resource status to DEPLOYED
    if team_id:
        db.execute(text("UPDATE rescue_teams SET status = 'DEPLOYED' WHERE id = :tid"), {"tid": team_id})
    if resource_id:
        db.execute(text("UPDATE rescue_resources SET status = 'DEPLOYED' WHERE id = :rid"), {"rid": resource_id})

    # 6. Audit log
    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'CREATE_ASSIGNMENT', 'response_assignments', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": asgn_id,
        "meta": json.dumps({"response_action_id": action_id, "team_id": team_id, "resource_id": resource_id}),
    })

    db.commit()

    # 7. Return detailed response
    asgn_sql = text("""
        SELECT 
            ra.id, ra.response_action_id, ra.team_id, t.name as team_name,
            ra.resource_id, res.name as resource_name, ra.status,
            ra.assigned_at, ra.released_at, ra.assigned_by
        FROM response_assignments ra
        LEFT JOIN rescue_teams t ON ra.team_id = t.id
        LEFT JOIN rescue_resources res ON ra.resource_id = res.id
        WHERE ra.id = :asgn_id
    """)
    row = db.execute(asgn_sql, {"asgn_id": asgn_id}).mappings().first()
    return dict(row)


def update_assignment(
    db: Session,
    current_user,
    assignment_id: int,
    payload,
) -> Dict[str, Any]:
    """Update assignment status (ASSIGNED, DEPLOYED, RELEASED) and sync team/resource status."""
    now_utc = datetime.now(timezone.utc)

    # 1. Fetch assignment
    asgn_sql = text("""
        SELECT ra.id, ra.team_id, ra.resource_id, ra.status, ra.response_action_id
        FROM response_assignments ra
        WHERE ra.id = :asgn_id
    """)
    asgn = db.execute(asgn_sql, {"asgn_id": assignment_id}).mappings().first()
    if not asgn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assignment {assignment_id} not found")

    new_status = payload.status
    released_at = now_utc if new_status == "RELEASED" else None

    # Update assignment
    db.execute(text("""
        UPDATE response_assignments
        SET status = :status, released_at = :rel_at
        WHERE id = :asgn_id
    """), {"status": new_status, "rel_at": released_at, "asgn_id": assignment_id})

    # If RELEASED, sync team and resource back to AVAILABLE if no other active assignments
    if new_status == "RELEASED":
        if asgn["team_id"]:
            other = db.execute(
                text("SELECT count(*) FROM response_assignments WHERE team_id = :tid AND id <> :aid AND status <> 'RELEASED'"),
                {"tid": asgn["team_id"], "aid": assignment_id},
            ).scalar()
            if other == 0:
                db.execute(text("UPDATE rescue_teams SET status = 'AVAILABLE' WHERE id = :tid"), {"tid": asgn["team_id"]})

        if asgn["resource_id"]:
            other = db.execute(
                text("SELECT count(*) FROM response_assignments WHERE resource_id = :rid AND id <> :aid AND status <> 'RELEASED'"),
                {"rid": asgn["resource_id"], "aid": assignment_id},
            ).scalar()
            if other == 0:
                db.execute(text("UPDATE rescue_resources SET status = 'AVAILABLE' WHERE id = :rid"), {"rid": asgn["resource_id"]})

    # Audit log
    audit_sql = text("""
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata, created_at)
        VALUES (:uid, 'UPDATE_ASSIGNMENT', 'response_assignments', :eid, CAST(:meta AS jsonb), now())
    """)
    db.execute(audit_sql, {
        "uid": current_user.id,
        "eid": assignment_id,
        "meta": json.dumps({"status": new_status}),
    })

    db.commit()

    # Return updated assignment
    res_sql = text("""
        SELECT 
            ra.id, ra.response_action_id, ra.team_id, t.name as team_name,
            ra.resource_id, res.name as resource_name, ra.status,
            ra.assigned_at, ra.released_at, ra.assigned_by
        FROM response_assignments ra
        LEFT JOIN rescue_teams t ON ra.team_id = t.id
        LEFT JOIN rescue_resources res ON ra.resource_id = res.id
        WHERE ra.id = :asgn_id
    """)
    row = db.execute(res_sql, {"asgn_id": assignment_id}).mappings().first()
    return dict(row)
