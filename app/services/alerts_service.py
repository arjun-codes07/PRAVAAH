"""Alert service for alert queries, creation, and acknowledgment with effective_status computation and audit logging."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.tables import User, Alert, Zone, RiskPrediction, AuditLog
from app.schemas.alerts import AlertCreateRequest, AlertResponse

def _compute_effective_status(status_str: str, expires_at: Optional[datetime]) -> str:
    """Compute effective status: EXPIRED if expires_at < now() and status is not CANCELLED."""
    if status_str == "CANCELLED":
        return "CANCELLED"
    if expires_at and expires_at < datetime.now(timezone.utc):
        return "EXPIRED"
    return status_str

def get_alerts(
    db: Session,
    authority_id: Optional[int],
    status_filter: Optional[str] = None,
    severity: Optional[str] = None,
    zone_id: Optional[int] = None,
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated alerts with computed effective_status."""
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if authority_id is not None:
        where_clauses.append("z.authority_id = :auth_id")
        params["auth_id"] = authority_id
    if zone_id is not None:
        where_clauses.append("a.zone_id = :zone_id")
        params["zone_id"] = zone_id
    if status_filter:
        where_clauses.append("a.status = :status_filter")
        params["status_filter"] = status_filter
    if severity:
        where_clauses.append("a.severity = :severity")
        params["severity"] = severity
    if active_only:
        where_clauses.append("a.status IN ('ACTIVE', 'ACKNOWLEDGED') AND (a.expires_at IS NULL OR a.expires_at > NOW())")

    where_sql = " AND ".join(where_clauses)

    count_sql = text(f"SELECT COUNT(*) FROM alerts a JOIN zones z ON a.zone_id = z.id WHERE {where_sql}")
    total = db.execute(count_sql, params).scalar() or 0

    query_sql = text(f"""
        SELECT 
            a.id, a.zone_id, a.location_id, a.incident_id, a.source_prediction_id,
            a.alert_type, a.severity, a.status, a.message, a.issued_at, a.expires_at,
            a.issued_by, a.acknowledged_at, a.acknowledged_by, a.data_origin
        FROM alerts a
        JOIN zones z ON a.zone_id = z.id
        WHERE {where_sql}
        ORDER BY a.issued_at DESC
        LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(query_sql, params).mappings().all()

    items = []
    for r in rows:
        eff_status = _compute_effective_status(r["status"], r["expires_at"])
        items.append({
            "id": r["id"],
            "zone_id": r["zone_id"],
            "location_id": r["location_id"],
            "incident_id": r["incident_id"],
            "source_prediction_id": r["source_prediction_id"],
            "alert_type": r["alert_type"],
            "severity": r["severity"],
            "status": r["status"],
            "effective_status": eff_status,
            "message": r["message"],
            "issued_at": r["issued_at"],
            "expires_at": r["expires_at"],
            "issued_by": r["issued_by"],
            "acknowledged_at": r["acknowledged_at"],
            "acknowledged_by": r["acknowledged_by"],
            "data_origin": r["data_origin"],
        })

    return {"items": items, "total": total, "limit": limit, "offset": offset}

def get_alert_detail(db: Session, authority_id: Optional[int], alert_id: int) -> Dict[str, Any]:
    """Retrieve alert detail by ID."""
    auth_filter = "AND z.authority_id = :auth_id" if authority_id is not None else ""
    params: Dict[str, Any] = {"aid": alert_id}
    if authority_id is not None:
        params["auth_id"] = authority_id

    sql = text(f"""
        SELECT 
            a.id, a.zone_id, a.location_id, a.incident_id, a.source_prediction_id,
            a.alert_type, a.severity, a.status, a.message, a.issued_at, a.expires_at,
            a.issued_by, a.acknowledged_at, a.acknowledged_by, a.data_origin
        FROM alerts a
        JOIN zones z ON a.zone_id = z.id
        WHERE a.id = :aid {auth_filter}
    """)
    r = db.execute(sql, params).mappings().first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found or access denied")

    eff_status = _compute_effective_status(r["status"], r["expires_at"])
    return {
        "id": r["id"],
        "zone_id": r["zone_id"],
        "location_id": r["location_id"],
        "incident_id": r["incident_id"],
        "source_prediction_id": r["source_prediction_id"],
        "alert_type": r["alert_type"],
        "severity": r["severity"],
        "status": r["status"],
        "effective_status": eff_status,
        "message": r["message"],
        "issued_at": r["issued_at"],
        "expires_at": r["expires_at"],
        "issued_by": r["issued_by"],
        "acknowledged_at": r["acknowledged_at"],
        "acknowledged_by": r["acknowledged_by"],
        "data_origin": r["data_origin"],
    }

def create_alert(db: Session, user: User, payload: AlertCreateRequest) -> AlertResponse:
    """Issue a new alert, enforcing authority scoping and writing an audit log entry."""
    zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zone {payload.zone_id} not found")

    if user.authority_id is not None and zone.authority_id != user.authority_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Zone {payload.zone_id} is outside user's authority scope",
        )

    # Resolve data_origin from source prediction if present, otherwise SIMULATED
    data_origin = "SIMULATED"
    if payload.source_prediction_id:
        sp = db.query(RiskPrediction).filter(RiskPrediction.id == payload.source_prediction_id).first()
        if sp:
            data_origin = sp.data_origin

    alert = Alert(
        zone_id=payload.zone_id,
        location_id=payload.location_id,
        incident_id=payload.incident_id,
        source_prediction_id=payload.source_prediction_id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        status="ACTIVE",
        message=payload.message,
        issued_at=datetime.now(timezone.utc),
        expires_at=payload.expires_at,
        issued_by=user.id,
        data_origin=data_origin,
    )
    db.add(alert)
    db.flush()

    audit = AuditLog(
        action="CREATE_ALERT",
        entity_type="alert",
        entity_id=alert.id,
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    eff_status = _compute_effective_status(alert.status, alert.expires_at)
    return AlertResponse(
        id=alert.id,
        zone_id=alert.zone_id,
        location_id=alert.location_id,
        incident_id=alert.incident_id,
        source_prediction_id=alert.source_prediction_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        effective_status=eff_status,
        message=alert.message,
        issued_at=alert.issued_at,
        expires_at=alert.expires_at,
        issued_by=alert.issued_by,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        data_origin=alert.data_origin,
    )

def acknowledge_alert(db: Session, user: User, alert_id: int) -> AlertResponse:
    """Acknowledge an active alert, updating status, acknowledged_at, acknowledged_by, and audit log."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert {alert_id} not found")

    zone = db.query(Zone).filter(Zone.id == alert.zone_id).first()
    if user.authority_id is not None and zone and zone.authority_id != user.authority_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alert is outside user's authority scope",
        )

    if alert.status == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot acknowledge a cancelled alert")

    now = datetime.now(timezone.utc)
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = now
    alert.acknowledged_by = user.id

    audit = AuditLog(
        action="ACKNOWLEDGE_ALERT",
        entity_type="alert",
        entity_id=alert.id,
        user_id=user.id,
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)

    eff_status = _compute_effective_status(alert.status, alert.expires_at)
    return AlertResponse(
        id=alert.id,
        zone_id=alert.zone_id,
        location_id=alert.location_id,
        incident_id=alert.incident_id,
        source_prediction_id=alert.source_prediction_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status=alert.status,
        effective_status=eff_status,
        message=alert.message,
        issued_at=alert.issued_at,
        expires_at=alert.expires_at,
        issued_by=alert.issued_by,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        data_origin=alert.data_origin,
    )
