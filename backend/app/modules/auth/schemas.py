from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    email: str | None = None
    is_active: bool


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str
