"""Auth Pydantic schemas."""

from typing import List, Optional
from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str
    authority_id: Optional[int] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo

class AuthMeResponse(BaseModel):
    user: UserInfo
    role: str
    permissions: List[str]
    authority: Optional[str] = None
