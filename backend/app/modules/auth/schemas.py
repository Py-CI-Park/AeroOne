from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    email: str | None = None
    is_active: bool
    requires_password_change: bool = False


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str
