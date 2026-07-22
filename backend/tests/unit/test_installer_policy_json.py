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
    assert categories == {
        "env-secret",
        "database",
        "storage-runtime",
        "agent-state",
        "dev-artifact",
        "provider-credential-root",
        "credential-dpapi-blob",
        "credential-secure-state",
    }

    env_category = next(c for c in policy.forbidden_categories if c.category == "env-secret")
    assert ".env.example" not in env_category.patterns
    assert any("env.example" in pattern for pattern in env_category.allow_patterns)

    assert len(policy.allow_top_level_entries) > 0
    assert "storage" not in policy.allow_top_level_entries
    # 폐쇄망 운영자가 부팅·복구에 쓰는 세 배치는 반드시 패키지에 실려야 한다. stop_offline.bat 은
    # start_offline.bat 이 exit 98(게이트 경합)로 실패할 때 안내하는 유일한 복구 도구인데, allow-list
    # 누락으로 어떤 오프라인 ZIP 에도 실린 적이 없어 1.19.0 폐쇄망 부팅 복구 불가 회귀를 냈다.
    for required_batch in ("setup_offline.bat", "start_offline.bat", "stop_offline.bat"):
        assert required_batch in policy.allow_top_level_entries, (
            f"{required_batch} 가 allow_top_level_entries 에 없어 오프라인 패키지에서 누락된다."
        )
