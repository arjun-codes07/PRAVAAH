"""Comprehensive pytest suite for PRAVAAH FastAPI P0 endpoints."""

import os
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.dependencies import get_db
from app.models.tables import User, Zone, Authority, Role, Alert, AuditLog, Observation

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_tokens():
    """Obtain access tokens for seeded demo users."""
    response = client.post("/api/v1/auth/login", json={
        "email": "officer@demo.pravaah.local",
        "password": "DemoOfficer123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token_officer = response.json()["access_token"]

    response = client.post("/api/v1/auth/login", json={
        "email": "commander@demo.pravaah.local",
        "password": "DemoCommander123!"
    })
    assert response.status_code == 200
    token_commander = response.json()["access_token"]

    return {
        "officer": token_officer,
        "commander": token_commander,
    }

def test_health_endpoint():
    """Verify /health returns 200 with PostGIS version."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "PostGIS" in data["postgis_version"] or "3." in data["postgis_version"]

def test_auth_login_invalid():
    """Verify login with wrong password returns 401."""
    res = client.post("/api/v1/auth/login", json={
        "email": "officer@demo.pravaah.local",
        "password": "WrongPassword123!"
    })
    assert res.status_code == 401

def test_auth_me(auth_tokens):
    """Verify /auth/me returns current user info, role, permissions, and authority."""
    res = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "officer@demo.pravaah.local"
    assert data["role"] == "AUTHORITY_OFFICER"
    assert "view_dashboard" in data["permissions"]

def test_protected_route_without_token():
    """Verify accessing protected routes without bearer token returns 401."""
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 401

def test_dashboard_summary(auth_tokens):
    """Verify #3 GET /dashboard/summary returns exact SPEC structure."""
    res = client.get("/api/v1/dashboard/summary", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert "risk_counts_by_level" in data
    assert "high_risk_zones" in data
    assert "recent_changes" in data
    assert "active_incidents" in data
    assert "active_alerts" in data
    assert "sensor_health" in data
    assert "environmental_indicators" in data
    assert "resource_status" in data
    assert "data_origins_present" in data

def test_map_features_geojson(auth_tokens):
    """Verify #4 GET /map/features returns valid GeoJSON FeatureCollection."""
    res = client.get("/api/v1/map/features?layers=zones,incidents,sensors,resources", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) > 0
    for feat in data["features"]:
        assert "geometry" in feat
        assert "properties" in feat
        assert "layer" in feat["properties"]
        assert "data_origin" in feat["properties"]

def test_zone_detail_and_nearby_resources(auth_tokens):
    """Verify #6 GET /zones/{id} with geometry and nearby resources ordering by distance."""
    res = client.get("/api/v1/zones/1?include_geometry=true&nearby_radius_m=50000", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == 1
    assert data["geometry"] is not None
    assert "current_risk" in data
    assert "top_factors" in data
    assert "sensors" in data
    assert data["nearby_resources"] is not None
    
    # Check nearby resources ordered by distance ASC
    distances = [r["distance_m"] for r in data["nearby_resources"]]
    assert distances == sorted(distances)

def test_risk_predictions_and_detail(auth_tokens):
    """Verify #9 GET /risk/predictions and #10 GET /risk/predictions/{id}."""
    res = client.get("/api/v1/risk/predictions?status=ACTIVE", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    pred_id = data["items"][0]["id"]
    
    # Check valid_until = predicted_at + horizon_minutes
    item = data["items"][0]
    pred_at = datetime.fromisoformat(item["predicted_at"])
    valid_until = datetime.fromisoformat(item["valid_until"])
    assert valid_until == pred_at + timedelta(minutes=item["horizon_minutes"])

    # Detail query
    res_detail = client.get(f"/api/v1/risk/predictions/{pred_id}", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == pred_id
    assert "explanations" in detail_data

def test_sensors_list_stale_computation(auth_tokens):
    """Verify #13 GET /sensors computes is_stale and includes latest_reading via lateral join."""
    res = client.get("/api/v1/sensors", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    sensor = data["items"][0]
    assert "is_stale" in sensor
    assert "latest_reading" in sensor

def test_incidents_list_and_detail(auth_tokens):
    """Verify #16 GET /incidents and #17 GET /incidents/{id}."""
    res = client.get("/api/v1/incidents", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    inc_id = data["items"][0]["id"]

    res_detail = client.get(f"/api/v1/incidents/{inc_id}", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == inc_id
    assert "zone" in detail_data
    assert "response_actions" in detail_data

def test_alerts_effective_status_and_creation(auth_tokens):
    """Verify #20 GET /alerts, #22 POST /alerts, and #23 POST /alerts/{id}/acknowledge."""
    # List alerts
    res = client.get("/api/v1/alerts", headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    alert_item = data["items"][0]
    assert "effective_status" in alert_item

    # Post new alert
    new_alert_payload = {
        "zone_id": 1,
        "alert_type": "FLOOD",
        "severity": "HIGH",
        "message": "Test evacuation warning alert for Mandi Town",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }
    res_post = client.post("/api/v1/alerts", json=new_alert_payload, headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_post.status_code == 201, f"Create alert failed: {res_post.text}"
    created_alert = res_post.json()
    assert created_alert["status"] == "ACTIVE"
    assert created_alert["message"] == new_alert_payload["message"]
    created_id = created_alert["id"]

    # Acknowledge alert
    res_ack = client.post(f"/api/v1/alerts/{created_id}/acknowledge", headers={
        "Authorization": f"Bearer {auth_tokens['commander']}"
    })
    assert res_ack.status_code == 200
    ack_alert_data = res_ack.json()
    assert ack_alert_data["status"] == "ACKNOWLEDGED"
    assert ack_alert_data["acknowledged_by"] is not None

def test_telemetry_ingestion_flow(auth_tokens):
    """Verify #11 POST /ingest/telemetry (201 success, 404 unknown node, 409 duplicate, 422 invalid payload)."""
    ts = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    ingest_payload = {
        "node_id": "HP-MANDI-001",
        "timestamp": ts,
        "rainfall_1h": 45.5,
        "soil_moisture": 82.0,
        "water_level": 3.85,
        "slope_angle": 25.0,
        "temperature": 18.5,
        "humidity": 92.0,
        "data_origin": "SIMULATED",
    }
    
    # 201 Success
    res = client.post("/api/v1/ingest/telemetry", json=ingest_payload, headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res.status_code == 201, f"Ingest failed: {res.text}"
    data = res.json()
    assert "observation_id" in data
    assert data["quality_status"] == "VALID"

    # 409 Duplicate timestamp
    res_dup = client.post("/api/v1/ingest/telemetry", json=ingest_payload, headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_dup.status_code == 409

    # 404 Unknown sensor node ID
    bad_node_payload = {**ingest_payload, "node_id": "UNKNOWN-NODE-999", "timestamp": datetime.now(timezone.utc).isoformat()}
    res_404 = client.post("/api/v1/ingest/telemetry", json=bad_node_payload, headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_404.status_code == 404

    # 422 Schema-invalid payload (soil_moisture > 100)
    bad_val_payload = {**ingest_payload, "soil_moisture": 150.0, "timestamp": datetime.now(timezone.utc).isoformat()}
    res_422 = client.post("/api/v1/ingest/telemetry", json=bad_val_payload, headers={
        "Authorization": f"Bearer {auth_tokens['officer']}"
    })
    assert res_422.status_code == 422

def test_authority_scoping_isolation():
    """Verify that a user assigned to a different authority cannot access zones outside their authority."""
    # Create temporary authority and user in database, query, then clean up
    from app.db import SessionLocal
    from app.core.security import create_access_token, hash_password
    
    db = SessionLocal()
    try:
        auth2 = Authority(name="Demo Second Authority", authority_type="DISTRICT_AUTHORITY", region_scope="Shimla", status="ACTIVE")
        db.add(auth2)
        db.flush()
        
        user2 = User(
            name="Shimla Officer",
            email="shimla_officer@demo.pravaah.local",
            password_hash=hash_password("DemoPassword123!"),
            role_id=1,
            authority_id=auth2.id,
            status="ACTIVE",
        )
        db.add(user2)
        db.commit()
        db.refresh(user2)
        
        token2 = create_access_token(data={"sub": str(user2.id), "role": "AUTHORITY_OFFICER", "authority_id": user2.authority_id})
        
        # User from authority 2 attempts to query zone 1 (belonging to authority 1) -> expects 404 Not Found
        res = client.get("/api/v1/zones/1", headers={"Authorization": f"Bearer {token2}"})
        assert res.status_code == 404
        
        # Dashboard for authority 2 has 0 high_risk_zones
        res_dash = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token2}"})
        assert res_dash.status_code == 200
        assert len(res_dash.json()["high_risk_zones"]) == 0

    finally:
        db.execute(text("DELETE FROM users WHERE email = 'shimla_officer@demo.pravaah.local'"))
        db.execute(text("DELETE FROM authorities WHERE name = 'Demo Second Authority'"))
        db.commit()
        db.close()
