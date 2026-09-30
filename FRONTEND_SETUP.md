# PRAVAAH Command Center Frontend Setup & Architecture Guide

## 1. Overview

The PRAVAAH Command Center is a responsive Single-Page Web Application built with **React 18**, **TypeScript**, and **Vite**. It adheres to the dark command-center aesthetic outlined in `03_UI_UX_DESIGN_BRIEF.md`, featuring glassmorphism, responsive data grids, spatial visualization via **MapLibre GL JS & MapTiler**, and real-time operational telemetry displays.

---

## 2. Prerequisites & Installation

- **Node.js**: Node 18+ or 20+
- **NPM**: 9+
- Backend API running on `http://127.0.0.1:8000`

### Setup Steps

From the project root:

```bash
cd frontend
npm install
```

---

## 3. Running the Development Server

Start the local development server:

```bash
npm run dev
```

The application will be accessible at:
[http://localhost:5173](http://localhost:5173)

---

## 4. Building for Production

Compile TypeScript and build the optimized production assets:

```bash
npm run build
```

The output artifacts will be written to `frontend/dist/`. To preview the production bundle locally:

```bash
npm run preview
```

---

## 5. User Personas & Demo Credentials

The login screen provides quick one-click persona selector buttons for rapid evaluation:

1. **State Disaster Authority Officer**
   - Email: `officer@demo.pravaah.local`
   - Scope: State-level oversight across Himachal Pradesh.
   - Capabilities: Global dashboard metrics, alerts issuance, incident coordination.

2. **District Disaster Management Commander**
   - Email: `commander@demo.pravaah.local`
   - Scope: District command (Mandi District).
   - Capabilities: Zone level dispatching, local response management, alert acknowledgment.

3. **Field Rescue Coordinator**
   - Email: `coordinator@demo.pravaah.local`
   - Scope: Field operations and rescue execution.
   - Capabilities: Unit dispatching, resource tracking, telemetry health monitoring.

---

## 6. Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts            # Axios client with JWT bearer interceptor & auto-logout
│   ├── components/
│   │   ├── DataTrustBadge.tsx   # Visual data origin indicator (SIMULATED, REPLAYED, REAL)
│   │   ├── Navbar.tsx           # Global header with live system clock & persona switcher
│   │   ├── PrototypeBanner.tsx  # Persistent advisory warning banner
│   │   ├── RiskBadge.tsx        # High-contrast accessible risk badges (LOW, MODERATE, HIGH, CRITICAL)
│   │   └── StaleIndicator.tsx   # Visual badge for sensor telemetry freshness
│   ├── context/
│   │   └── AuthContext.tsx      # User authentication, token persistence, and role state
│   ├── pages/
│   │   ├── Alerts.tsx           # Effective status filtering, alert modal, 1-click ack
│   │   ├── Dashboard.tsx        # Command metrics, environmental averages, high-risk zones
│   │   ├── Incidents.tsx        # Incident reporting, severity update, response action dispatch
│   │   ├── Login.tsx            # Persona selector and email/password authentication
│   │   ├── MapView.tsx          # MapLibre GL JS & MapTiler GIS visualization with risk choropleth & layer toggles
│   │   ├── Response.tsx         # Rescue teams & resource inventory with spatial radius search
│   │   ├── Sensors.tsx          # Sensor nodes health, staleness indicator, readings modal
│   │   ├── ZoneDetail.tsx       # Zone risk factor breakdown, terrain stats, nearby resources
│   │   └── ZonesList.tsx        # Grid & table of monitored hydrological zones
│   ├── App.tsx                  # Main router and layout wrapper
│   ├── index.css                # Dark command center design tokens and styles
│   └── main.tsx                 # Application entry point
├── index.html                   # HTML5 shell with Inter font
├── package.json                 # Frontend dependencies & scripts
├── tsconfig.json                # TypeScript project config
└── vite.config.ts               # Vite configuration with /api proxy to localhost:8000
```

---

## 7. Key Features & Compliance

- **Decision Support Banner**: The `PrototypeBanner` is permanently pinned to the top of the interface: *"PRAVAAH Advisory Prototype — Decision support only. Not for automated critical life-safety decisions."*
- **Data Trust Transparency**: Every risk prediction, sensor observation, and incident explicitly shows a `DataTrustBadge` (`SIMULATED`, `REPLAYED`, or `REAL`).
- **Explainable Risk**: Zone details render individual risk factor weights (`water_level`, `rainfall_rate`, `soil_saturation`, `slope_factor`) with descriptive rationale.
- **Accessible Design**: Risk levels are distinguished using both distinct colors and textual labels with icons, ensuring accessibility across all monitor conditions.
