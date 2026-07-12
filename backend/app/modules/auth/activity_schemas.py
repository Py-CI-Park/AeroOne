from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ActivityIdentity(BaseModel):
    username: str
    display_name: str | None = None
    role: Literal['admin', 'user', 'pending']


class ActivitySession(BaseModel):
    state: Literal['current', 'active']
    last_activity_at: str
    device_label: str


class ActivityAuthEvent(BaseModel):
    kind: Literal['login', 'logout']
    outcome: Literal['success', 'failure']
    occurred_at: str


class ActivityAiRequest(BaseModel):
    status: Literal['completed', 'failed']
    module_key: None = None
    occurred_at: str


class ActivityAccessibleModule(BaseModel):
    key: str
    label: str


class ActivityResponse(BaseModel):
    identity: ActivityIdentity
    active_sessions: list[ActivitySession]
    auth_events: list[ActivityAuthEvent]
    ai_requests: list[ActivityAiRequest]
    accessible_modules: list[ActivityAccessibleModule]
