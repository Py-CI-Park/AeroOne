from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CredentialRotationDatabaseState(Base):
    __tablename__: str = "credential_rotation_database_state"
    __table_args__: tuple[CheckConstraint] = (
        CheckConstraint("singleton_id = 1", name="ck_credential_rotation_database_singleton"),
    )

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    database_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CredentialRotationLedger(Base):
    __tablename__: str = "credential_rotation_ledger"
    __table_args__: tuple[UniqueConstraint | CheckConstraint, ...] = (
        UniqueConstraint(
            "database_id",
            "material_fingerprint",
            name="uq_credential_rotation_database_material",
        ),
        CheckConstraint(
            "user_count_before = user_count_after",
            name="ck_credential_rotation_user_count_preserved",
        ),
        CheckConstraint(
            "user_count_after = password_count_changed",
            name="ck_credential_rotation_password_count",
        ),
        CheckConstraint(
            "session_count_after = 0",
            name="ck_credential_rotation_sessions_cleared",
        ),
    )

    rotation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    database_id: Mapped[str] = mapped_column(
        ForeignKey("credential_rotation_database_state.database_id"),
        nullable=False,
    )
    material_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    user_set_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    pre_state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    post_state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    user_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    user_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    password_count_changed: Mapped[int] = mapped_column(Integer, nullable=False)
    session_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    session_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
