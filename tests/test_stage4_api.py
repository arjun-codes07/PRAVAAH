"""Comprehensive pytest suite for PRAVAAH Stage 4 backend endpoints."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.tables import Incident, ResponseAction, ResponseAssignment, AuditLog, RescueTeam, RescueResource

client = TestClient(app)


@pytest.fixture(scope="module")
def officer_token():
    res = client.post("/api/v1/auth/login", json={
        "email": "officer@demo.pravaah.local",
        "password": "DemoOfficer123!"
    })
    assert res.status_code == 200
    return res.json()["access_token"]


def test_list_zones_endpoint(officer_token):
    """Test #5 GET /api/v1/zones."""
    res = client.get("/api/v1/zones", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    zone = data["items"][0]
    assert "name" in zone
    assert "current_risk_level" in zone
    assert "sensor_count" in zone
    assert "active_incident_count" in zone


def test_zone_observations_endpoint(officer_token):
    """Test #7 GET /api/v1/zones/{id}/observations."""
    res = client.get("/api/v1/zones/1/observations", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    if len(data["items"]) > 0:
        obs = data["items"][0]
        assert "observed_at" in obs
        assert "quality_status" in obs


def test_zone_risk_history_endpoint(officer_token):
    """Test #8 GET /api/v1/zones/{id}/risk-history."""
    res = client.get("/api/v1/zones/1/risk-history", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert "overall_risk_level" in data["items"][0]


def test_global_observations_endpoint(officer_token):
    """Test #12 GET /api/v1/observations."""
    res = client.get("/api/v1/observations", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1


def test_sensor_readings_endpoint(officer_token):
    """Test #14 GET /api/v1/sensors/{node_id}/readings."""
    res = client.get("/api/v1/sensors/HP-MANDI-001/readings", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1


def test_data_sources_endpoint(officer_token):
    """Test #15 GET /api/v1/data-sources."""
    res = client.get("/api/v1/data-sources", headers={"Authorization": f"Bearer {officer_token}"})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "source_type" in data[0]
    assert "data_origin" in data[0]


def test_incident_lifecycle_and_audit(officer_token):
    """Test #18 POST /incidents, #19 PATCH /incidents/{id}, #26 POST response-actions,

    #27 PATCH response-actions, #28 POST assignments, #29 PATCH assignments.
    """
    headers = {"Authorization": f"Bearer {officer_token}"}

    # 1. Create Incident
    create_payload = {
        "zone_id": 1,
        "incident_type": "FLOOD",
        "severity": "HIGH",
        "description": "Rising water level near Mandi Beas bridge",
        "latitude": 31.710,
        "longitude": 76.930,
        "data_origin": "SIMULATED",
    }
    res = client.post("/api/v1/incidents", json=create_payload, headers=headers)
    assert res.status_code == 201, f"Failed creating incident: {res.text}"
    inc = res.json()
    inc_id = inc["id"]
    assert inc["incident_type"] == "FLOOD"
    assert inc["severity"] == "HIGH"
    assert inc["status"] == "OPEN"

    # Verify audit log was created for incident
    db = SessionLocal()
    audit = db.query(AuditLog).filter(
        AuditLog.entity_type == "incidents",
        AuditLog.entity_id == inc_id,
        AuditLog.action == "CREATE_INCIDENT"
    ).first()
    assert audit is not None
    db.close()

    # 2. Update Incident
    patch_payload = {
        "status": "IN_PROGRESS",
        "severity": "CRITICAL",
        "description": "Water overflowing onto road",
    }
    res = client.patch(f"/api/v1/incidents/{inc_id}", json=patch_payload, headers=headers)
    assert res.status_code == 200
    updated_inc = res.json()
    assert updated_inc["status"] == "IN_PROGRESS"
    assert updated_inc["severity"] == "CRITICAL"

    # 3. Create Response Action
    action_payload = {
        "action_type": "EVACUATION_ASSISTANCE",
        "priority": "HIGH",
        "notes": "Deploy rescue team to lower market area",
    }
    res = client.post(f"/api/v1/incidents/{inc_id}/response-actions", json=action_payload, headers=headers)
    assert res.status_code == 201
    action = res.json()
    action_id = action["id"]
    assert action["status"] == "PLANNED"
    assert action["priority"] == "HIGH"

    # 4. Update Response Action
    res = client.patch(f"/api/v1/response-actions/{action_id}", json={
        "status": "IN_PROGRESS",
        "priority": "CRITICAL",
    }, headers=headers)
    assert res.status_code == 200
    act_updated = res.json()
    assert act_updated["status"] == "IN_PROGRESS"
    assert act_updated["priority"] == "CRITICAL"

    # 5. List Rescue Teams & Resources
    res = client.get("/api/v1/response/teams", headers=headers)
    assert res.status_code == 200
    teams = res.json()
    assert len(teams) >= 1
    available_teams = [t for t in teams if t["status"] == "AVAILABLE"]
    assert len(available_teams) >= 1, "Expected at least one available team"
    team_id = available_teams[0]["id"]

    res = client.get("/api/v1/response/resources?near_lat=31.71&near_lon=76.93", headers=headers)
    assert res.status_code == 200
    resources = res.json()
    assert len(resources) >= 1
    assert "distance_m" in resources[0]

    # 6. Assign Team to Response Action
    res = client.post(f"/api/v1/response-actions/{action_id}/assignments", json={"team_id": team_id}, headers=headers)
    assert res.status_code == 201
    asgn = res.json()
    asgn_id = asgn["id"]
    assert asgn["team_id"] == team_id
    assert asgn["status"] == "ASSIGNED"

    # Check team status changed to DEPLOYED
    db = SessionLocal()
    team = db.query(RescueTeam).filter(RescueTeam.id == team_id).first()
    assert team.status == "DEPLOYED"

    # 7. Attempt duplicate active assignment -> 409 Conflict!
    res = client.post(f"/api/v1/response-actions/{action_id}/assignments", json={"team_id": team_id}, headers=headers)
    assert res.status_code == 409, f"Expected 409 conflict, got: {res.status_code}"

    # 8. Release Assignment -> team reverts to AVAILABLE
    res = client.patch(f"/api/v1/assignments/{asgn_id}", json={"status": "RELEASED"}, headers=headers)
    assert res.status_code == 200
    rel_asgn = res.json()
    assert rel_asgn["status"] == "RELEASED"

    db.refresh(team)
    assert team.status == "AVAILABLE"
    db.close()

    # 9. Resolve Incident
    res = client.patch(f"/api/v1/incidents/{inc_id}", json={"status": "RESOLVED"}, headers=headers)
    assert res.status_code == 200
    resolved = res.json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None
