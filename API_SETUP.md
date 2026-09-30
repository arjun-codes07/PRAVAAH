# PRAVAAH API Setup & Quickstart Guide

## 1. Prerequisites & Environment Setup

Ensure PostgreSQL 18 with PostGIS extension is running on port 5432 and the database migrations and seed data have been applied.

Environment variables are configured in `.env` (git-ignored). Refer to `.env.example` for required configuration key names:

- `DATABASE_URL`: PostgreSQL connection string (`postgresql+psycopg://pravaah_app:***@localhost:5432/pravaah`)
- `JWT_SECRET`: Secret key used to sign access tokens
- `JWT_ALGORITHM`: Signing algorithm (default `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Expiry duration (default `120`)
- `CORS_ORIGINS`: Comma-separated CORS origins (e.g. `http://localhost:5173,http://localhost:3000`)
- `STALE_DEFAULT_MINUTES`: Sensor staleness threshold (default `60`)

---

## 2. Running the API Server

Start the FastAPI application using `uvicorn`:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The interactive OpenAPI documentation is available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 3. Seed Users & Authentication

To log in via `POST /api/v1/auth/login`, use one of the seeded user emails below. Passwords match the seeded password set during `setup_local_db.ps1`:

- **State Disaster Authority**: `officer@demo.pravaah.local` (Role: `AUTHORITY_OFFICER`, Authority: Himachal Pradesh State Disaster Management Authority)
- **District Command Center**: `commander@demo.pravaah.local` (Role: `DISTRICT_COMMANDER`, Authority: Mandi District Disaster Management Authority)
- **Field Operations**: `coordinator@demo.pravaah.local` (Role: `FIELD_COORDINATOR`, Authority: Mandi District Disaster Management Authority)

Sample Login Request:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email":"officer@demo.pravaah.local","password":"<YOUR_SEED_PASSWORD>"}'
```

---

## 4. Running Verification & Tests

Run the full automated test suite (26 passing tests covering auth, risk engine, telemetry, CRUD endpoints, spatial queries, and full E2E workflow):

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

Verify database integrity and schema constraints:

```powershell
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m scripts.verify
```

---

## 5. Complete Implemented API Endpoints (All P0 & P1 Endpoints)

| Category | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| **System** | `/api/v1/health` | `GET` | Health check & PostGIS database connectivity verification |
| **Auth** | `/api/v1/auth/login` | `POST` | User authentication & JWT issuance |
| **Auth** | `/api/v1/auth/me` | `GET` | Current user profile, role, permissions, authority |
| **Dashboard**| `/api/v1/dashboard/summary` | `GET` | Risk counts, high-risk zones, active incidents, alerts, sensor health, environmental averages |
| **Map** | `/api/v1/map/features` | `GET` | GeoJSON FeatureCollection of monitored zones, incidents, sensors, and response units |
| **Zones** | `/api/v1/zones` | `GET` | List all monitored zones with active risk level & summary counts |
| **Zones** | `/api/v1/zones/{id}` | `GET` | Detailed zone status, top contributing risk factors, sensors, incidents, alerts, resources |
| **Zones** | `/api/v1/zones/{id}/observations`| `GET` | Time-series sensor observations in zone |
| **Zones** | `/api/v1/zones/{id}/risk-history`| `GET` | Historical risk predictions for the zone (active & superseded) |
| **Risk** | `/api/v1/risk/predictions` | `GET` | Query active risk predictions with filters |
| **Risk** | `/api/v1/risk/predictions/{id}` | `GET` | Single risk prediction with factors, confidence, data origin |
| **Observations**| `/api/v1/observations` | `GET` | Global list of sensor observations with filtering |
| **Sensors** | `/api/v1/sensors` | `GET` | List sensors with dynamic `is_stale` calculation & latest telemetry |
| **Sensors** | `/api/v1/sensors/{node_id}/readings`| `GET` | Time-series readings for a specific sensor node |
| **Data Sources**| `/api/v1/data-sources` | `GET` | Registered telemetry & geospatial data sources |
| **Incidents**| `/api/v1/incidents` | `GET` | List incidents with zone, severity, and status filters |
| **Incidents**| `/api/v1/incidents/{id}` | `GET` | Incident details with response actions and assignments |
| **Incidents**| `/api/v1/incidents` | `POST` | Report a new incident (writes audit log) |
| **Incidents**| `/api/v1/incidents/{id}` | `PATCH` | Update incident status/severity (`resolved_at` sync, writes audit log) |
| **Alerts** | `/api/v1/alerts` | `GET` | List alerts with derived `effective_status` (`ACTIVE`, `ACKNOWLEDGED`, `EXPIRED`, `CANCELLED`) |
| **Alerts** | `/api/v1/alerts/{id}` | `GET` | Alert details |
| **Alerts** | `/api/v1/alerts` | `POST` | Issue a new emergency alert & write audit log |
| **Alerts** | `/api/v1/alerts/{id}/acknowledge` | `POST` | Acknowledge alert (`ACKNOWLEDGED` + timestamp) & write audit log |
| **Response** | `/api/v1/response/teams` | `GET` | List response teams with active assignment counts |
| **Response** | `/api/v1/response/resources` | `GET` | List response resources, with optional spatial proximity filter (`zone_id` / `radius_km`) |
| **Response** | `/api/v1/incidents/{id}/response-actions` | `POST` | Create a response action plan for an incident |
| **Response** | `/api/v1/response-actions/{id}` | `PATCH` | Update response action status |
| **Response** | `/api/v1/response-actions/{id}/assignments` | `POST` | Dispatch team or resource to action (enforces single-active check, sets `DEPLOYED`) |
| **Response** | `/api/v1/assignments/{id}` | `PATCH` | Update assignment status (syncs unit back to `AVAILABLE` on `RELEASED`) |
| **Telemetry**| `/api/v1/ingest/telemetry` | `POST` | Ingest sensor observation, derive rate, trigger risk evaluation |

---

## 6. Applied Defaults for Unspecified Items

1. **Environmental Indicators Aggregation**: Calculated as the average of the latest `VALID` observation across active sensors per zone metric (`rainfall_1h_mm`, `soil_moisture_pct`, `water_level_m`, `temperature_c`, `humidity_pct`).
2. **Sensor Staleness Default**: Default set to 60 minutes via `STALE_DEFAULT_MINUTES` env var if `data_sources.stale_after_minutes` is NULL.
3. **Alert Authority Scope Permissions**: Any active user can issue/acknowledge alerts within their authority scope (`check_alert_permission` dependency).
4. **Ingest Quality Status**: Default set to `VALID`. Values failing DB range CHECKs are rejected with HTTP 422.
5. **Risk Engine Origin Aggregation**: Worst-origin rule (`SIMULATED` > `REPLAYED` > `REAL`).
6. **Active Assignment Conflict**: An active unit (`team` or `resource`) assigned to another non-released action returns HTTP 409 Conflict.
