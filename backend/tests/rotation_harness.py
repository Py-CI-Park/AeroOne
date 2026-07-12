from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import secrets
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.modules.admin.models import UserSessionActivity
from app.modules.auth.models import User
from app.operations import credential_rotation_models  # noqa: F401  (create_all model registration)


ROTATION_PROCESS_TIMEOUT_SECONDS = 180
ACL_PROCESS_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class SyntheticWorkspace:
    root: Path
    database_url: str
    jwt_secret: str
    admin_password: str


def create_synthetic_workspace(tmp_path: Path) -> SyntheticWorkspace:
    test_nonce = secrets.token_hex(16)
    root = tmp_path / f"aeroone-rotation-test-{test_nonce}"
    backend = root / "backend"
    database_path = backend / "data" / "aeroone.db"
    database_path.parent.mkdir(parents=True)
    (root / ".aeroone-rotation-test-root").write_text(
        f"aeroone-rotation-test-v1:{test_nonce}",
        encoding="utf-8",
    )
    database_url = f"sqlite:///{database_path.as_posix()}"
    jwt_secret = secrets.token_hex(32)
    admin_password = secrets.token_urlsafe(24)
    env_text = "\n".join(
        (
            "APP_ENV=test",
            f"DATABASE_URL={database_url}",
            f"JWT_SECRET_KEY={jwt_secret}",
            "ADMIN_USERNAME=admin",
            f"ADMIN_PASSWORD={admin_password}",
            "",
        )
    )
    (root / ".env").write_text(env_text, encoding="utf-8")
    (backend / ".env").write_text(env_text, encoding="utf-8")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        admin = User(
            username="admin",
            password_hash=hash_password(admin_password),
            role="admin",
            is_active=True,
            session_version=2,
        )
        session.add(admin)
        session.flush()
        now = datetime.now(UTC)
        session.add(
            UserSessionActivity(
                user_id=admin.id,
                session_hash=secrets.token_hex(32),
                last_seen_at=now,
                expires_at=now + timedelta(minutes=30),
            )
        )
    engine.dispose()
    return SyntheticWorkspace(
        root=root,
        database_url=database_url,
        jwt_secret=jwt_secret,
        admin_password=admin_password,
    )


def invoke_rotation(
    workspace: SyntheticWorkspace,
    extra_arguments: tuple[str, ...] = (),
    *,
    internal_crashpoint: str | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy()
    for key in tuple(process_environment):
        if key.startswith("AEROONE_ROTATION_"):
            del process_environment[key]
    process_environment["AEROONE_ROTATION_PYTHON"] = sys.executable
    if internal_crashpoint is not None:
        nonce = workspace.root.name.removeprefix("aeroone-rotation-test-")
        process_environment["AEROONE_ROTATION_INTERNAL_CRASH"] = f"{nonce}:{internal_crashpoint}"
    process_environment["TEMP"] = str(workspace.root.parent)
    process_environment["TMP"] = str(workspace.root.parent)
    script = Path(__file__).resolve().parents[2] / "scripts" / "rotate_aeroone_credentials.ps1"
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TestMode",
            "-TestWorkspaceRoot",
            str(workspace.root),
            *extra_arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=ROTATION_PROCESS_TIMEOUT_SECONDS,
    )


def env_value(path: Path, key: str) -> str:
    prefix = f"{key}="
    matches = [
        line[len(prefix) :]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(prefix)
    ]
    assert len(matches) == 1
    return matches[0]


def has_exact_secure_acl(path: Path) -> bool:
    command = (
        "$acl=Get-Acl -LiteralPath $env:AEROONE_ACL_TEST_PATH;"
        "$current=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
        "$owner=if($acl.Owner.StartsWith('S-')){$acl.Owner}else{"
        "(New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value};"
        "$rules=@($acl.GetAccessRules($true,$false,[Security.Principal.SecurityIdentifier]));"
        "$ids=@($rules | ForEach-Object {$_.IdentityReference.Value} | Sort-Object);"
        "$expected=@('S-1-5-18',$current) | Sort-Object;"
        "$difference=@(Compare-Object $ids $expected);"
        "if($acl.AreAccessRulesProtected -and $owner -eq $current -and $rules.Count -eq 2 -and "
        "$difference.Count -eq 0){exit 0}else{exit 1}"
    )
    process_environment = os.environ.copy()
    process_environment["AEROONE_ACL_TEST_PATH"] = str(path)
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        env=process_environment,
        timeout=ACL_PROCESS_TIMEOUT_SECONDS,
    )
    return completed.returncode == 0
