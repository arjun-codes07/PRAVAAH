"""Auth API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_current_user
from app.models.tables import User
from app.schemas.auth import LoginRequest, TokenResponse, AuthMeResponse
from app.services.auth_service import authenticate_user, get_auth_me_data

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=TokenResponse)
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email/password and return JWT access token."""
    return authenticate_user(db, creds)

@router.get("/me", response_model=AuthMeResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return profile, role, permissions, and authority of currently authenticated user."""
    return get_auth_me_data(db, current_user)
