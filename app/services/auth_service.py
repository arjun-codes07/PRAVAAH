"""Authentication service handling user login and auth user profile lookup."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.tables import User, Role, Authority
from app.core.security import verify_password, create_access_token
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo, AuthMeResponse

def authenticate_user(db: Session, creds: LoginRequest) -> TokenResponse:
    """Authenticate email & password, check ACTIVE status, return JWT access token."""
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not verify_password(creds.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    role = db.query(Role).filter(Role.id == user.role_id).first()
    role_name = role.name if role else "USER"
    
    token_data = {"sub": str(user.id), "role": role_name, "authority_id": user.authority_id}
    access_token = create_access_token(data=token_data)
    
    user_info = UserInfo(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role_name,
        authority_id=user.authority_id,
    )
    
    return TokenResponse(
        access_token=access_token,
        expires_in=480 * 60,
        user=user_info,
    )

def get_auth_me_data(db: Session, user: User) -> AuthMeResponse:
    """Return user profile, role, permissions array, and authority name."""
    role = db.query(Role).filter(Role.id == user.role_id).first()
    role_name = role.name if role else "USER"
    permissions = role.permissions if role and role.permissions else []
    
    authority_name = None
    if user.authority_id:
        auth = db.query(Authority).filter(Authority.id == user.authority_id).first()
        if auth:
            authority_name = auth.name
            
    user_info = UserInfo(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role_name,
        authority_id=user.authority_id,
    )
    
    return AuthMeResponse(
        user=user_info,
        role=role_name,
        permissions=permissions,
        authority=authority_name,
    )
