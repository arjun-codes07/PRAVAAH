# PRAVAAH End-to-End Demonstration Guide

This guide walks you through running the complete PRAVAAH Multi-Hazard Early Warning & Response Decision Support Platform locally on Windows.

---

## 1. Prerequisites Check

Before starting, confirm that your local environment is configured:
1. Local PostgreSQL 18 with PostGIS is running on port 5432.
2. Python virtual environment is ready at `.venv`.
3. Node.js (18+) is installed.

Verify database readiness:
```powershell
.venv\Scripts\python.exe -m scripts.verify
```

---

## 2. Launching the Services

You will need **three terminal windows**:

### Terminal 1: FastAPI Backend
```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### Terminal 2: React Command Center Frontend
```powershell
cd frontend
npm run dev
```
- Open browser at: [http://localhost:5173](http://localhost:5173)

### Terminal 3: Telemetry Simulator
Keep this terminal ready to inject real-time flood or landslide telemetry.

---

## 3. Demo Walkthrough Steps

### Step 1: Login to Command Center
1. Navigate to [http://localhost:5173](http://localhost:5173) in your browser.
2. Click **"Disaster Authority Officer"** to auto-populate credentials (`officer@demo.pravaah.local`).
3. Click **"Sign In to Command Center"**.
4. Notice the persistent advisory prototype banner at the very top:
   > *"PRAVAAH Advisory Prototype — Decision support only. Not for automated critical life-safety decisions."*

### Step 2: Observe Dashboard & GIS Map
1. **Executive Dashboard**:
   - Inspect the zone risk counts by level (Low, Moderate, High, Critical).
   - Observe real-time environmental averages (rainfall, soil moisture, river level).
   - Notice the explicit `DataTrustBadge` (`SIMULATED`, `REPLAYED`, or `REAL`) indicating data origin.
2. **GIS Map View**:
   - Click **"Map View"** in the top navigation.
   - Explore the interactive Leaflet map of Himachal Pradesh with dark CARTO tiles.
   - Toggle the layer controls in the top-right corner (`Zones`, `Sensors`, `Incidents`, `Resources`).
   - Click on Zone 1 (Beas River Basin) polygon to open the quick details popup.

### Step 3: Trigger Live Flood Escalation Simulation
In Terminal 3, run the multi-step flood escalation scenario:
```powershell
.venv\Scripts\python.exe scripts\simulate.py --scenario flood_escalation --steps 10 --speed 1.0
```
- Watch as rainfall surges to >80 mm/h and river level rises above 7.5 meters.
- Notice the simulator logs displaying:
  `[Step 1/10] Node HP-MANDI-001: rainfall=52.3mm, water_lvl=5.8m -> Ingested (obs_id=...)`
  `Triggered risk re-evaluation for zone 1 -> Level HIGH / CRITICAL`

### Step 4: Inspect Zone Risk Explainability
1. In the web browser, navigate to **"Monitored Zones"** and select **"Beas Basin - Mandi Urban"**.
2. Notice the live risk badge is updated to **HIGH** or **CRITICAL**.
3. Scroll down to the **"Risk Factor Contributions"** panel:
   - See how each environmental metric contributed to the score (e.g., `water_level_m` weight 0.35, `rainfall_1h_mm` weight 0.30).
   - Read the human-readable explanation and recommended advisory response.
4. View the list of nearby response resources located within spatial proximity of the zone.

### Step 5: Issue & Acknowledge an Emergency Alert
1. In the web interface, navigate to **"Emergency Alerts"**.
2. Click **"+ Issue Emergency Alert"**:
   - Select Zone: `Beas Basin - Mandi Urban`
   - Severity: `CRITICAL`
   - Alert Type: `FLOOD_FLASH`
   - Headline: `Flash Flood Advisory for Beas River Lowlands`
   - Description: `Rapidly rising water levels detected at Mandi Urban sensor. Low-lying areas advised to enact pre-evacuation protocols.`
   - Click **"Publish Emergency Alert"**.
3. Notice the newly issued alert appears with status `ACTIVE`.
4. Click **"Acknowledge"** on the alert:
   - The alert transitions to `ACKNOWLEDGED`.
   - An immutable audit trail entry is logged in PostgreSQL.

### Step 6: Incident Management & Resource Dispatch
1. Navigate to **"Incidents"** in the navigation bar.
2. Click **"+ Report Incident"**:
   - Title: `Waterlogging and Silt Accumulation on NH-21`
   - Zone: `Beas Basin - Mandi Urban`
   - Severity: `HIGH`
   - Click **"Submit Incident Report"**.
3. Open the incident detail view and click **"+ Create Action Plan"**:
   - Title: `Clear culverts and deploy de-watering pumps`
   - Click **"Create Action"**.
4. In the Response Action, click **"Dispatch Team / Resource"**:
   - Select an available rescue team or resource (e.g. `NDRF Team 14`).
   - Click **"Dispatch Unit"**.
   - Notice the unit status automatically transitions to `DEPLOYED`, and double-dispatch conflicts are blocked.

### Step 7: Sensor Health & Staleness Detection
1. Navigate to **"Sensors"** in the navigation bar.
2. Observe the active telemetry nodes, their battery levels, and last reported timestamps.
3. In Terminal 3, run a simulation with a silenced node to test watchdog staleness:
```powershell
.venv\Scripts\python.exe scripts\simulate.py --scenario baseline --silence-node HP-MANDI-002 --steps 5
```
4. Observe that sensor `HP-MANDI-002` displays a visual **STALE** indicator after its threshold is exceeded.

---

## 4. Running the Automated Test Suite

To verify all components end-to-end programmatically:

```powershell
# Run the complete 26-test suite
.venv\Scripts\python.exe -m pytest tests/ -v
```

All 26 tests will execute against your local database, validating:
- JWT authentication & role-based scoping
- Risk engine scoring, thresholds, and supersession logic
- Multi-hazard telemetry ingestion & rate calculation
- Leaflet GeoJSON layer generation
- Response dispatching & spatial proximity queries
- Full multi-step E2E lifecycle
