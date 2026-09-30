"""PRAVAAH FastAPI Application Main Entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.map import router as map_router
from app.api.v1.zones import router as zones_router
from app.api.v1.risk import router as risk_router
from app.api.v1.sensors import router as sensors_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.observations import router as observations_router
from app.api.v1.data_sources import router as data_sources_router
from app.api.v1.response import router as response_router

app = FastAPI(
    title="PRAVAAH API",
    description="Backend REST API for PRAVAAH Hydro-Meteorological Disaster Warning & Response Platform",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint at root
app.include_router(health_router)

# All v1 routers under /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(map_router, prefix="/api/v1")
app.include_router(zones_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")
app.include_router(sensors_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(observations_router, prefix="/api/v1")
app.include_router(data_sources_router, prefix="/api/v1")
app.include_router(response_router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "platform": "PRAVAAH API",
        "version": "1.0.0",
        "documentation": "/api/v1/docs",
        "health": "/health",
    }
