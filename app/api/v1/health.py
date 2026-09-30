"""Health check router verifying database connectivity and PostGIS version."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.dependencies import get_db

router = APIRouter(tags=["Health"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Check database connection and verify PostGIS version."""
    try:
        ver = db.execute(text("SELECT PostGIS_Version()")).scalar()
        return {
            "status": "healthy",
            "database": "connected",
            "postgis_version": ver,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error: {str(exc)}",
        )
