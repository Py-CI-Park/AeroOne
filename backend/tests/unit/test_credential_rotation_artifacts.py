from __future__ import annotations

from uuid import uuid4

from pydantic import ValidationError
import pytest

from app.operations.credential_rotation_artifacts import (
    RotationJournal,
    RotationJournalPayload,
    RotationPhase,
    advance_rotation_journal,
    seal_rotation_journal,
)


def _payload() -> RotationJournalPayload:
    digest = "a" * 64
    return RotationJournalPayload(
        sequence=0,
        phase=RotationPhase.PREPARED,
        root_environment_present=True,
        rotation_id=uuid4(),
        database_id=uuid4(),
        user_count=1,
        retention="2027-07-10T00:00:00+09:00",
        bundle_sha256=digest,
        recovery_sha256=digest,
        pending_root_sha256=digest,
        pending_backend_sha256=digest,
        root_before_sha256=digest,
        backend_before_sha256=digest,
        root_after_sha256=digest,
        backend_after_sha256=digest,
    )


def test_journal_rejects_extra_fields_and_checksum_tampering() -> None:
    journal = seal_rotation_journal(_payload())
    values = journal.model_dump()

    with pytest.raises(ValidationError):
        RotationJournal.model_validate(values | {"unexpected": True})
    with pytest.raises(ValidationError):
        RotationJournal.model_validate(values | {"bundle_sha256": "b" * 64})


def test_journal_only_advances_one_phase_and_increments_sequence() -> None:
    journal = seal_rotation_journal(_payload())

    advanced = advance_rotation_journal(journal, RotationPhase.DB_COMMITTED)

    assert advanced.sequence == journal.sequence + 1
    assert advanced.phase is RotationPhase.DB_COMMITTED
    with pytest.raises(ValueError, match="phase transition"):
        advance_rotation_journal(advanced, RotationPhase.PREPARED)


def test_journal_binds_absent_root_environment_without_placeholder_digests() -> None:
    # Given: a prepared journal payload for an installer topology with no root .env.
    values = _payload().model_dump()
    values.update(
        root_environment_present=False,
        pending_root_sha256=None,
        root_before_sha256=None,
        root_after_sha256=None,
    )

    # When: the strict journal boundary parses and seals the topology.
    payload = RotationJournalPayload.model_validate(values)
    journal = seal_rotation_journal(payload)

    # Then: absence is explicit, checksum-bound, and carries no synthetic root digest.
    assert journal.schema_version == 2
    assert journal.root_environment_present is False
    assert journal.pending_root_sha256 is None
