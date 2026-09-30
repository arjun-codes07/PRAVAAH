# PRAVAAH — Database Setup Guide

## Prerequisites

- **Python 3.10+** (using virtual environment at `.venv`)
- **PostgreSQL 18** with **PostGIS 3.6+** installed locally on port 5432
- Powershell ExecutionPolicy enabled for running setup scripts

## Local Database Setup (Recommended Flow)

The database setup is automated via `scripts/setup_local_db.ps1`.

```powershell
# Run local database setup script (prompts securely for superuser password)
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_db.ps1
```

### What `setup_local_db.ps1` does:
1. Prompts for the PostgreSQL superuser (`postgres`) password securely using `Read-Host -AsSecureString`.
2. Verifies PostGIS extension availability in PostgreSQL 18.
3. Generates a secure random 32-character password for `pravaah_app` (or reads existing password from `.env`).
4. Creates non-superuser role `pravaah_app` (or updates password).
5. Creates database `pravaah` owned by `pravaah_app` and runs `CREATE EXTENSION IF NOT EXISTS postgis` as superuser.
6. Grants all required privileges on schema `public` to `pravaah_app`.
7. Creates/updates `.env` with least-privilege `DATABASE_URL=postgresql+psycopg://pravaah_app:<PASSWORD>@localhost:5432/pravaah`.

> **Security Warning**: The repository is located inside `OneDrive\Desktop`. Note that `.env` contains local runtime credentials; ensure OneDrive sync or backup rules do not accidentally expose private keys. `.env` is listed in `.gitignore` and must never be committed.

## Python Virtual Environment Setup

```powershell
# Python commands must use .venv\Scripts\python.exe
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Migration Commands

```powershell
# Run Alembic migrations (creates schema from scratch via hand-written DDL)
.venv\Scripts\python.exe -m alembic upgrade head

# Check current migration revision
.venv\Scripts\python.exe -m alembic current
```

## Seed Commands

```powershell
# Seed baseline demo data (idempotent; fails safely if data already exists)
.venv\Scripts\python.exe -m scripts.seed
```

## Verification Commands

```powershell
# Run 95-point comprehensive database verification suite
.venv\Scripts\python.exe -m scripts.verify
```

---

## `updated_at` Maintenance & System Rules

- **Database trigger**: PostgreSQL trigger function `set_updated_at()` updates `updated_at = now()` on table modification.
- **Backend Rules**:
  1. Sensor zone consistency (`ST_Within(sensor.geom, zone.geom)`).
  2. Provenance rules (`data_origin` is `SIMULATED` for baseline data).
  3. Spatial SRID: All geometry columns use SRID 4326.
