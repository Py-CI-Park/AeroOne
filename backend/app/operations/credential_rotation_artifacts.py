from __future__ import annotations

from enum import StrEnum, unique
import hashlib
import hmac
import json
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


_SHA256_PATTERN = r"^[a-f0-9]{64}$"


@unique
class RotationPhase(StrEnum):
    PREPARED = "prepared"
    DB_COMMITTED = "db_committed"
    ROOT_ENV_PROMOTED = "root_env_promoted"
    BACKEND_ENV_PROMOTED = "backend_env_promoted"
    CREDENTIALS_PROMOTED = "credentials_promoted"
    COMPLETE = "complete"


_PHASE_SEQUENCE = tuple(RotationPhase)


class RotationJournalPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[2] = 2
    sequence: int = Field(ge=0)
    phase: RotationPhase
    root_environment_present: bool
    rotation_id: UUID
    database_id: UUID
    user_count: int = Field(gt=0)
    retention: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T.*[+-]\d{2}:\d{2}$")
    bundle_sha256: str = Field(pattern=_SHA256_PATTERN)
    recovery_sha256: str = Field(pattern=_SHA256_PATTERN)
    pending_root_sha256: str | None = Field(pattern=_SHA256_PATTERN)
    pending_backend_sha256: str = Field(pattern=_SHA256_PATTERN)
    root_before_sha256: str | None = Field(pattern=_SHA256_PATTERN)
    backend_before_sha256: str = Field(pattern=_SHA256_PATTERN)
    root_after_sha256: str | None = Field(pattern=_SHA256_PATTERN)
    backend_after_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_root_environment_topology(self) -> RotationJournalPayload:
        root_digests = (
            self.pending_root_sha256,
            self.root_before_sha256,
            self.root_after_sha256,
        )
        if self.root_environment_present and any(digest is None for digest in root_digests):
            raise PydanticCustomError(
                "journal_root_topology",
                "present root environment requires bound digests",
            )
        if not self.root_environment_present and any(digest is not None for digest in root_digests):
            raise PydanticCustomError(
                "journal_root_topology",
                "absent root environment forbids root digests",
            )
        return self

    def checksum(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return hashlib.sha256(canonical).hexdigest()


class RotationJournal(RotationJournalPayload):
    checksum_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_checksum(self) -> RotationJournal:
        payload = RotationJournalPayload.model_validate(
            self.model_dump(exclude={"checksum_sha256"})
        )
        if not hmac.compare_digest(self.checksum_sha256, payload.checksum()):
            raise ValueError("journal checksum mismatch")
        return self


def seal_rotation_journal(payload: RotationJournalPayload) -> RotationJournal:
    return RotationJournal.model_validate(
        payload.model_dump() | {"checksum_sha256": payload.checksum()}
    )


def advance_rotation_journal(
    journal: RotationJournal,
    phase: RotationPhase,
) -> RotationJournal:
    current_index = _PHASE_SEQUENCE.index(journal.phase)
    if current_index + 1 >= len(_PHASE_SEQUENCE) or _PHASE_SEQUENCE[current_index + 1] is not phase:
        raise ValueError("journal phase transition invalid")
    payload_values = journal.model_dump(exclude={"checksum_sha256"})
    payload_values["sequence"] = journal.sequence + 1
    payload_values["phase"] = phase
    return seal_rotation_journal(RotationJournalPayload.model_validate(payload_values))
