from __future__ import annotations

from pathlib import Path

from app.operations.package_policy_verifier import load_policy

_POLICY_PATH = Path(__file__).resolve().parents[3] / "packaging" / "installer-policy.json"


def test_installer_policy_declares_the_two_required_release_installers() -> None:
    policy = load_policy(_POLICY_PATH)

    assert policy.profile == "release-qa"
    assert len(policy.required_installers) == 2

    by_filename = {installer.filename: installer for installer in policy.required_installers}

    python_installer = by_filename["python-3.12.7-amd64.exe"]
    assert python_installer.sha256 == "1206721601a62c925d4e4a0dcfc371e88f2ddbe8c0c07962ebb2be9b5bde4570"
    assert python_installer.authenticode_thumbprint == "36168EE17C1A240517388540C903BB6717DD2563"
    assert python_installer.authenticode_subject == "Python Software Foundation"

    node_installer = by_filename["node-v20.18.0-x64.msi"]
    assert node_installer.sha256 == "93d1d30341d7d38b7a8f3ab0fa3be1f9e6436b90338b2bd8b8af4e80d00bd036"
    assert node_installer.authenticode_thumbprint == "6153EB0186DD8FEBD9E3693F4F110DEFC007715D"
    assert node_installer.authenticode_subject == "OpenJS Foundation"


def test_installer_policy_declares_forbidden_categories_beyond_a_bare_deny_list() -> None:
    policy = load_policy(_POLICY_PATH)

    categories = {category.category for category in policy.forbidden_categories}
    assert categories == {"env-secret", "database", "storage-runtime", "agent-state", "dev-artifact"}

    env_category = next(c for c in policy.forbidden_categories if c.category == "env-secret")
    assert ".env.example" not in env_category.patterns
    assert any("env.example" in pattern for pattern in env_category.allow_patterns)

    assert len(policy.allow_top_level_entries) > 0
    assert "storage" not in policy.allow_top_level_entries
