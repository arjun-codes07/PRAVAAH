"""End-to-End Integration & Scenario Test for PRAVAAH.

Executes the complete crisis management sequence:
1. Multi-persona Authentication
2. Baseline Dashboard & Zone Status Check
3. Dynamic Telemetry Simulation & Risk Escalation
4. Verification of Risk Prediction Supersession & Origin Propagation
5. Sensor Staleness Detection
6. Incident Reporting & Severity Tracking
7. Emergency Warning Alert Issuance & Officer Acknowledgment
8. Coordinated Response Action Dispatch & Team Assignment
9. Active Assignment Conflict Prevention (409)
10. Assignment Release & Unit Status Reconciliation
11. Incident Resolution
12. Comprehensive Audit Log Verification
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.tables import (
    RiskPrediction,
    RiskExplanation,
    Incident,
    Alert,
    ResponseAction,
    ResponseAssignment,
    RescueTeam,
    AuditLog,
    SensorNode,
)

client = TestClient(app)


def test_full_pravaah_e2e_workflow():
    """Execute complete end-to-end operational cycle."""
    # -------------------------------------------------------------------------
    # 1. Authenticate seeded users
    # -------------------------------------------------------------------------
    res = client.post("/api/v1/auth/login", json={
        "email": "officer@demo.pravaah.local",
        "password": "DemoOfficer123!",
    })
    assert res.status_code == 200, f"Officer login failed: {res.text}"
    token_officer = res.json()["access_token"]
    headers_officer = {"Authorization": f"Bearer {token_officer}"}

    res = client.post("/api/v1/auth/login", json={
        "email": "commander@demo.pravaah.local",
        "password": "DemoCommander123!",
    })
    assert res.status_code == 200
    token_commander = res.json()["access_token"]
    headers_commander = {"Authorization": f"Bearer {token_commander}"}

    # Verify officer profile
    me_res = client.get("/api/v1/auth/me", headers=headers_officer)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "AUTHORITY_OFFICER"

    # -------------------------------------------------------------------------
    # 2. Check Dashboard Baseline & Map Features
    # -------------------------------------------------------------------------
    dash_res = client.get("/api/v1/dashboard/summary", headers=headers_officer)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "risk_counts_by_level" in dash_data
    assert "sensor_health" in dash_data

    map_res = client.get("/api/v1/map/features", headers=headers_officer)
    assert map_res.status_code == 200
    map_features = map_res.json()
    assert map_features["type"] == "FeatureCollection"
    assert len(map_features["features"]) > 0

    # -------------------------------------------------------------------------
    # 3. Simulate Rising Telemetry (Flood Escalation on Zone 1)
    # -------------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc)
    target_node = "HP-MANDI-001"

    # Ingest severe rainfall and river water levels
    telemetry_payload = {
        "node_id": target_node,
        "timestamp": (now_utc - timedelta(seconds=10)).isoformat(),
        "rainfall_1h": 82.5,          # Extreme rainfall
        "water_level": 7.8,           # Dangerous river level
        "soil_moisture": 88.0,
        "slope_angle": 15.0,
        "temperature": 18.5,
        "humidity": 96.0,
        "data_origin": "SIMULATED",
    }

    ingest_res = client.post("/api/v1/ingest/telemetry", json=telemetry_payload, headers=headers_officer)
    assert ingest_res.status_code == 201
    obs_id = ingest_res.json()["observation_id"]
    assert obs_id > 0

    # -------------------------------------------------------------------------
    # 4. Verify Zone 1 Risk Escalation & Supersession
    # -------------------------------------------------------------------------
    zone1_res = client.get("/api/v1/zones/1", headers=headers_officer)
    assert zone1_res.status_code == 200
    zone1 = zone1_res.json()
    current_risk = zone1["current_risk"]
    assert current_risk is not None
    assert current_risk["overall_risk_level"] in ("HIGH", "CRITICAL")
    assert current_risk["flood_risk_level"] in ("HIGH", "CRITICAL")
    assert current_risk["data_origin"] == "SIMULATED"
    assert len(zone1["top_factors"]) >= 3

    # Verify supersession in database
    db = SessionLocal()
    active_preds = db.query(RiskPrediction).filter(
        RiskPrediction.zone_id == 1,
        RiskPrediction.status == "ACTIVE"
    ).all()
    assert len(active_preds) == 1, "Exactly one ACTIVE prediction must exist per zone"

    superseded_preds = db.query(RiskPrediction).filter(
        RiskPrediction.zone_id == 1,
        RiskPrediction.status == "SUPERSEDED"
    ).all()
    assert len(superseded_preds) >= 1, "Prior predictions must be marked SUPERSEDED"

    # -------------------------------------------------------------------------
    # 5. Verify Sensor Staleness
    # -------------------------------------------------------------------------
    sensors_res = client.get("/api/v1/sensors", headers=headers_officer)
    assert sensors_res.status_code == 200
    sensor_items = sensors_res.json()["items"]
    
    # HP-MANDI-006 is deliberately stale in seed data
    stale_node = next((s for s in sensor_items if s["node_id"] == "HP-MANDI-006"), None)
    if stale_node:
        assert stale_node["is_stale"] is True

    # -------------------------------------------------------------------------
    # 6. Report Emergency Incident on Escalated Zone
    # -------------------------------------------------------------------------
    inc_payload = {
        "zone_id": 1,
        "incident_type": "FLOOD",
        "severity": "CRITICAL",
        "description": "E2E: Severe inundation near Beas riverbank. Immediate road closure required.",
        "latitude": 31.711,
        "longitude": 76.931,
        "data_origin": "SIMULATED",
    }
    inc_res = client.post("/api/v1/incidents", json=inc_payload, headers=headers_commander)
    assert inc_res.status_code == 201
    incident_id = inc_res.json()["id"]

    # -------------------------------------------------------------------------
    # 7. Issue Warning Alert & Acknowledge
    # -------------------------------------------------------------------------
    alert_payload = {
        "zone_id": 1,
        "alert_type": "FLOOD",
        "severity": "CRITICAL",
        "message": "E2E EMERGENCY: Critical flood warning for Mandi Town Core. Relocate from riverbank areas.",
        "expires_at": (now_utc + timedelta(hours=4)).isoformat(),
        "data_origin": "SIMULATED",
    }
    alert_res = client.post("/api/v1/alerts", json=alert_payload, headers=headers_officer)
    assert alert_res.status_code == 201
    alert_id = alert_res.json()["id"]
    assert alert_res.json()["status"] == "ACTIVE"

    # Officer acknowledges alert
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers_officer)
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    assert ack_res.json()["acknowledged_at"] is not None

    # -------------------------------------------------------------------------
    # 8. Dispatch Response Action & Assign Rescue Unit
    # -------------------------------------------------------------------------
    action_payload = {
        "action_type": "EVACUATION_AND_BARRICADE",
        "priority": "CRITICAL",
        "notes": "E2E: Deploy rescue unit to seal lower bridge entrance.",
    }
    action_res = client.post(f"/api/v1/incidents/{incident_id}/response-actions", json=action_payload, headers=headers_commander)
    assert action_res.status_code == 201
    action_id = action_res.json()["id"]

    # Find available team
    teams_res = client.get("/api/v1/response/teams", headers=headers_commander)
    assert teams_res.status_code == 200
    available_teams = [t for t in teams_res.json() if t["status"] == "AVAILABLE"]
    assert len(available_teams) >= 1, "Must have an available team for assignment"
    target_team = available_teams[0]

    # Assign team
    asgn_res = client.post(
        f"/api/v1/response-actions/{action_id}/assignments",
        json={"team_id": target_team["id"]},
        headers=headers_commander
    )
    assert asgn_res.status_code == 201
    assignment_id = asgn_res.json()["id"]

    # Team status must now be DEPLOYED
    team_in_db = db.query(RescueTeam).filter(RescueTeam.id == target_team["id"]).first()
    db.refresh(team_in_db)
    assert team_in_db.status == "DEPLOYED"

    # -------------------------------------------------------------------------
    # 9. Conflict Prevention: Cannot reassign already deployed team
    # -------------------------------------------------------------------------
    dup_asgn_res = client.post(
        f"/api/v1/response-actions/{action_id}/assignments",
        json={"team_id": target_team["id"]},
        headers=headers_commander
    )
    assert dup_asgn_res.status_code == 409

    # -------------------------------------------------------------------------
    # 10. Release Assignment & Reconcile Unit Status
    # -------------------------------------------------------------------------
    rel_res = client.patch(
        f"/api/v1/assignments/{assignment_id}",
        json={"status": "RELEASED"},
        headers=headers_commander
    )
    assert rel_res.status_code == 200
    assert rel_res.json()["status"] == "RELEASED"

    # Team status must revert back to AVAILABLE
    db.refresh(team_in_db)
    assert team_in_db.status == "AVAILABLE"

    # -------------------------------------------------------------------------
    # 11. Complete Action & Resolve Incident
    # -------------------------------------------------------------------------
    client.patch(
        f"/api/v1/response-actions/{action_id}",
        json={"status": "COMPLETED"},
        headers=headers_commander
    )

    resolve_res = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={"status": "RESOLVED"},
        headers=headers_commander
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"
    assert resolve_res.json()["resolved_at"] is not None

    # -------------------------------------------------------------------------
    # 12. Verify Audit Log Trail
    # -------------------------------------------------------------------------
    incident_audits = db.query(AuditLog).filter(
        AuditLog.entity_type == "incidents",
        AuditLog.entity_id == incident_id,
    ).all()
    assert len(incident_audits) >= 2  # CREATE_INCIDENT, UPDATE_INCIDENT

    assignment_audits = db.query(AuditLog).filter(
        AuditLog.entity_type == "response_assignments",
        AuditLog.entity_id == assignment_id,
    ).all()
    assert len(assignment_audits) >= 2  # CREATE_ASSIGNMENT, UPDATE_ASSIGNMENT

    db.close()
