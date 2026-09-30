"""Data Sources API router."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])

class DataSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    provider: Optional[str] = None
    description: Optional[str] = None
    data_origin: str
    status: str
    stale_after_minutes: Optional[int] = None
    provenance_notes: Optional[str] = None
    created_at: datetime

@router.get("", response_model=List[DataSourceResponse])
def list_data_sources(
    status: Optional[str] = Query(default=None, description="Filter by status (ACTIVE/INACTIVE)"),
    source_type: Optional[str] = Query(default=None, description="Filter by source type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve list of registered data sources."""
    where_clauses = ["1=1"]
    params: Dict[str, Any] = {}

    if status:
        where_clauses.append("status = :status")
        params["status"] = status
    if source_type:
        where_clauses.append("source_type = :source_type")
        params["source_type"] = source_type

    where_sql = " AND ".join(where_clauses)
    query = text(f"""
        SELECT id, name, source_type, provider, description, data_origin, status,
               stale_after_minutes, provenance_notes, created_at
        FROM data_sources
        WHERE {where_sql}
        ORDER BY id ASC
    """)
    rows = db.execute(query, params).mappings().all()
    return [dict(r) for r in rows]
