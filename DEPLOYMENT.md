# PRAVAAH — Deployment Guide

Production deployment guide for the **Hydro-Meteorological Disaster Warning & Response System**.

| Layer    | Service      | Stack                                  |
|----------|-------------|----------------------------------------|
| Backend  | Render      | FastAPI · Python · PostgreSQL + PostGIS |
| Frontend | Vercel       | React · Vite · TypeScript · MapLibre   |
| Database | Render (managed) or external PostgreSQL + PostGIS |

---

## 1. Local Backend Setup

```bash
# Clone the repository
git clone <YOUR_GITHUB_URL> && cd PRAVAAH

# Create Python virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env file and fill in values
cp .env.example .env
# Edit .env with your DATABASE_URL, JWT_SECRET, etc.

# Start the backend
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

---

## 2. Local Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy env file and fill in values
cp .env.example .env
# Edit .env — set VITE_API_BASE_URL and VITE_MAPTILER_API_KEY

# Start the dev server
npm run dev
```

Frontend: [http://localhost:5173](http://localhost:5173)

---

## 3. Environment Variables

### Backend (`.env`)

| Variable                     | Description                               | Required |
|------------------------------|-------------------------------------------|----------|
| `DATABASE_URL`               | PostgreSQL connection string              | ✅       |
| `JWT_SECRET`                 | Secret key for JWT token signing          | ✅       |
| `JWT_ALGORITHM`              | JWT algorithm (default: `HS256`)          | ❌       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Token expiry in minutes (default: `480`)  | ❌       |
| `CORS_ORIGINS`               | Comma-separated allowed origins           | ✅       |
| `STALE_DEFAULT_MINUTES`      | Data staleness threshold (default: `60`)  | ❌       |
| `PRAVAAH_APP_USER`           | DB application user                       | ❌       |
| `PRAVAAH_APP_PASSWORD`       | DB application user password              | ❌       |
| `SEED_PASSWORD_OFFICER`      | Demo seed password                        | ❌       |
| `SEED_PASSWORD_COMMANDER`    | Demo seed password                        | ❌       |
| `SEED_PASSWORD_COORDINATOR`  | Demo seed password                        | ❌       |

### Frontend (`frontend/.env`)

| Variable                | Description                          | Required |
|-------------------------|--------------------------------------|----------|
| `VITE_API_BASE_URL`     | Backend API URL (e.g., `https://pravaah-api.onrender.com/api/v1`) | ✅ |
| `VITE_POLL_INTERVAL_MS` | Dashboard polling interval (default: `15000`) | ❌ |
| `VITE_MAPTILER_API_KEY` | MapTiler API key for vector/satellite basemaps | ✅ |

---

## 4. PostgreSQL + PostGIS (Production Database)

PRAVAAH requires **PostgreSQL with the PostGIS extension**. The migration creates geometry columns (`geometry(MultiPolygon, 4326)`, `geometry(Point, 4326)`) for spatial data.

### Option A: Render Managed PostgreSQL

Render's managed PostgreSQL **does NOT include PostGIS** on the free tier. You need a paid plan with PostGIS support, or use an external provider.

### Option B: External PostgreSQL + PostGIS

Recommended providers:
- **Neon** (free tier, PostGIS supported)
- **Supabase** (free tier, PostGIS supported)
- **Railway** (PostGIS available)
- **AWS RDS / Azure / GCP Cloud SQL** (PostGIS available)

After creating the database, enable PostGIS:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

> **Note:** The Alembic migration also runs `CREATE EXTENSION IF NOT EXISTS postgis`, but the database user must have `CREATE` privileges on the database.

### URL Format

The application automatically normalizes database URLs:
- `postgres://...` → `postgresql+psycopg://...`
- `postgresql://...` → `postgresql+psycopg://...`

No manual conversion needed.

---

## 5. Alembic Migrations

```bash
# Run all pending migrations (from project root)
alembic upgrade head

# Check current migration status
alembic current

# Generate a new migration (after model changes)
alembic revision --autogenerate -m "description"
```

For production deployment on Render, migrations run via:

```bash
DATABASE_URL="<your-production-url>" alembic upgrade head
```

Or add as a pre-deploy command in Render dashboard:
**Settings → Pre-Deploy Command:** `alembic upgrade head`

---

## 6. Render Backend Deployment

1. **Push to GitHub** (see below)

2. **Create a Web Service on Render:**
   - Connect your GitHub repository
   - **Root Directory:** *(leave blank — project root)*
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables** in Render dashboard:
   | Variable               | Value                                          |
   |------------------------|-------------------------------------------------|
   | `DATABASE_URL`         | Your PostgreSQL connection string               |
   | `JWT_SECRET`           | A strong random secret (`openssl rand -hex 32`) |
   | `JWT_ALGORITHM`        | `HS256`                                         |
   | `CORS_ORIGINS`         | Your Vercel frontend URL (e.g., `https://pravaah.vercel.app`) |
   | `PYTHON_VERSION`       | `3.12`                                          |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `480`                                    |
   | `STALE_DEFAULT_MINUTES`| `60`                                            |

4. **Pre-Deploy Command** (optional, for auto-migrations):
   ```
   alembic upgrade head
   ```

5. **Deploy** — Render will build and start the service.

> **Alternative:** Use the included `render.yaml` blueprint. Go to Render dashboard → **Blueprints → New Blueprint Instance** → connect your repo.

---

## 7. Vercel Frontend Deployment

1. **Push to GitHub** (see below)

2. **Import project on Vercel:**
   - Connect your GitHub repository
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `dist` (auto-detected)

3. **Set Environment Variables** in Vercel dashboard:
   | Variable                | Value                                                 |
   |-------------------------|-------------------------------------------------------|
   | `VITE_API_BASE_URL`     | `https://pravaah-api.onrender.com/api/v1`             |
   | `VITE_POLL_INTERVAL_MS` | `15000`                                               |
   | `VITE_MAPTILER_API_KEY` | Your MapTiler API key                                 |

4. **Deploy** — Vercel will build and deploy the frontend.

> **Important:** Vite environment variables are baked into the build at build time (they are NOT runtime variables). Any change to `VITE_*` variables requires a redeploy.

---

## 8. CORS Configuration

The `CORS_ORIGINS` environment variable is a comma-separated list of allowed origins.

**Local development:**
```
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**Production:**
```
CORS_ORIGINS=https://pravaah.vercel.app
```

**Multiple origins:**
```
CORS_ORIGINS=https://pravaah.vercel.app,https://www.pravaah.com
```

---

## 9. Production API URL

After deploying the backend on Render, your API will be available at:

```
https://<your-service-name>.onrender.com/api/v1
```

- **API Docs:** `https://<your-service-name>.onrender.com/api/v1/docs`
- **Health Check:** `https://<your-service-name>.onrender.com/health`
- **Root:** `https://<your-service-name>.onrender.com/`

Set this URL as `VITE_API_BASE_URL` in your Vercel environment variables.

---

## 10. MapTiler Configuration

PRAVAAH uses **MapLibre GL JS** with **MapTiler** vector/satellite basemaps.

1. Create a free account at [cloud.maptiler.com](https://cloud.maptiler.com)
2. Go to **Account → API Keys**
3. Copy your API key
4. Set as `VITE_MAPTILER_API_KEY` in your frontend environment

The app gracefully falls back to a CARTO dark basemap if no MapTiler key is provided.

> **Tip:** On MapTiler, restrict your API key to your production domain for security.

---

## 11. Verification Checklist

After deployment, verify the system:

| Check                        | URL / Command                                           | Expected |
|------------------------------|---------------------------------------------------------|----------|
| Backend health               | `GET /health`                                           | `200 OK` |
| API docs load                | `GET /api/v1/docs`                                      | Swagger UI |
| Frontend loads               | Visit Vercel URL                                        | Login page |
| Login works                  | Login with seeded credentials                           | JWT token returned |
| Map renders                  | Navigate to map view                                    | MapTiler/CARTO basemap |
| Dashboard loads              | Navigate to dashboard                                   | Data populates |
| CORS works                   | Frontend API calls succeed (no CORS errors in console)  | ✅ |
| Database connected           | Backend logs show no connection errors                  | ✅ |

```bash
# Quick backend health check
curl https://<your-service-name>.onrender.com/health

# Check API root
curl https://<your-service-name>.onrender.com/
```

---

## Quick Reference: Deployment Order

1. **Push to GitHub**
2. **Set up production database** (with PostGIS)
3. **Run migrations:** `DATABASE_URL="..." alembic upgrade head`
4. **Seed data** (if needed): `DATABASE_URL="..." python -m scripts.seed`
5. **Deploy backend on Render** (set env vars, deploy)
6. **Deploy frontend on Vercel** (set `VITE_API_BASE_URL` to Render URL)
7. **Verify** the deployed system
