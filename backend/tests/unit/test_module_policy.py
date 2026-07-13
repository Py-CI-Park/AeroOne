from __future__ import annotations

import pytest

from app.modules.admin.module_policy import validate_module_gate


# --- acceptances ---

def test_admin_visibility_with_no_gate_is_valid() -> None:
    assert validate_module_gate('admin', None, None, None) is None


def test_public_ungated_is_valid() -> None:
    assert validate_module_gate('public', None, None, None) is None


def test_public_global_gate_with_known_permission_is_valid() -> None:
    assert validate_module_gate('public', 'collections.nsa.read', None, None) is None


def test_public_global_gate_with_known_admin_permission_is_valid() -> None:
    assert validate_module_gate('public', 'admin.audit.read', None, None) is None


def test_public_resource_gate_for_nsa_collection_is_valid() -> None:
    assert validate_module_gate('public', 'collections.nsa.read', 'collection', 'nsa') is None


# --- rejections ---

@pytest.mark.parametrize(
    'visibility,required_permission,resource_type,resource_id',
    [
        # partial gates
        ('public', 'collections.nsa.read', None, 'nsa'),
        ('public', 'collections.nsa.read', 'collection', None),
        ('public', None, 'collection', 'nsa'),
        ('public', None, 'collection', None),
        ('public', None, None, 'nsa'),
        # unknown permission
        ('public', 'not.a.real.permission', None, None),
        ('public', 'not.a.real.permission', 'collection', 'nsa'),
        # resource mismatch: only collections.nsa.read + collection + nsa is allowed
        ('public', 'collections.nsa.read', 'collection', 'other-collection'),
        ('public', 'collections.nsa.read', 'newsletter', 'nsa'),
        # unsafe resource_id
        ('public', 'collections.nsa.read', 'collection', 'NSA'),
        ('public', 'collections.nsa.read', 'collection', 'nsa/../etc'),
        ('public', 'collections.nsa.read', 'collection', 'nsa_x'),
        ('public', 'collections.nsa.read', 'collection', ''),
        # the specific rejected combination called out by the spec
        ('public', 'collections.read', 'collection', 'nsa'),
        # admin visibility with any gate field set
        ('admin', 'collections.nsa.read', None, None),
        ('admin', None, 'collection', None),
        ('admin', None, None, 'nsa'),
        ('admin', 'collections.nsa.read', 'collection', 'nsa'),
        # unknown visibility
        ('hidden', None, None, None),
    ],
)
def test_rejections(visibility: str, required_permission: str | None, resource_type: str | None, resource_id: str | None) -> None:
    error = validate_module_gate(visibility, required_permission, resource_type, resource_id)
    assert error is not None
    assert isinstance(error, str)
