from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


POWERSHELL_TIMEOUT_SECONDS = 30


class ClipboardProbeResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    textMatches: bool
    excluded: bool
    history: int
    cloud: int
    clearOwned: str
    clearUnrelated: str
    unrelatedPreserved: bool


class ClipboardDecisionResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    KeepOwnership: bool
    ScheduleRetry: bool
    AllowClose: bool
    OperatorActionRequired: bool


def _run_sta_probe(script: str, *, secret: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["AEROONE_CLIPBOARD_TEST_SECRET"] = secret
    environment["AEROONE_CLIPBOARD_MODULE"] = str(
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "credential_rotation"
        / "Rotation.Clipboard.psm1"
    )
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-STA",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=POWERSHELL_TIMEOUT_SECONDS,
    )


def test_secure_clipboard_excludes_history_and_cloud_and_clears_only_owned_text() -> None:
    # Given: an STA process and a synthetic credential that is never printed.
    secret = f"synthetic-{secrets.token_urlsafe(32)}"
    script = r"""
$ErrorActionPreference = 'Stop'
Import-Module $env:AEROONE_CLIPBOARD_MODULE -Force -DisableNameChecking
Add-Type -AssemblyName PresentationCore
$maximumAttempts = 20
$retryDelayMilliseconds = 250
$originalCaptured = $false
for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
    try {
        $original = [Windows.Clipboard]::GetDataObject()
        $originalCaptured = $true
        break
    } catch [Runtime.InteropServices.COMException] {
        if ($attempt -eq $maximumAttempts) { throw }
        Start-Sleep -Milliseconds $retryDelayMilliseconds
    }
}
$result = [ordered]@{}
try {
    Set-RotationSecureClipboard -Text $env:AEROONE_CLIPBOARD_TEST_SECRET
    $status = Get-RotationSecureClipboardStatus -Expected $env:AEROONE_CLIPBOARD_TEST_SECRET
    $result.textMatches = $status.TextMatches
    $result.excluded = $status.Excluded
    $result.history = $status.History
    $result.cloud = $status.Cloud
    for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
        $result.clearOwned = Clear-RotationOwnedClipboard -Expected $env:AEROONE_CLIPBOARD_TEST_SECRET
        if ($result.clearOwned -ne 'Failed') { break }
        Start-Sleep -Milliseconds $retryDelayMilliseconds
    }
    Set-RotationSecureClipboard -Text $env:AEROONE_CLIPBOARD_TEST_SECRET
    for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
        try {
            [Windows.Clipboard]::SetText('synthetic-unrelated')
            break
        } catch [Runtime.InteropServices.COMException] {
            if ($attempt -eq $maximumAttempts) { throw }
            Start-Sleep -Milliseconds $retryDelayMilliseconds
        }
    }
    $result.clearUnrelated = Clear-RotationOwnedClipboard -Expected $env:AEROONE_CLIPBOARD_TEST_SECRET
    $unrelated = Get-RotationSecureClipboardStatus -Expected 'synthetic-unrelated'
    $result.unrelatedPreserved = $unrelated.TextMatches
} finally {
    $restored = $false
    if ($originalCaptured -and $null -ne $original) {
        for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
            try {
                [Windows.Clipboard]::SetDataObject($original, $true)
                $restored = $true
                break
            } catch [Runtime.InteropServices.COMException] {
                if ($attempt -lt $maximumAttempts) { Start-Sleep -Milliseconds $retryDelayMilliseconds }
            }
        }
    } else {
        $restored = $true
        foreach ($owned in @($env:AEROONE_CLIPBOARD_TEST_SECRET, 'synthetic-unrelated')) {
            for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
                $clearResult = Clear-RotationOwnedClipboard -Expected $owned
                if ($clearResult -ne 'Failed') { break }
                Start-Sleep -Milliseconds $retryDelayMilliseconds
            }
            if ($clearResult -eq 'Failed') { $restored = $false }
        }
    }
    if (-not $restored) {
        foreach ($owned in @($env:AEROONE_CLIPBOARD_TEST_SECRET, 'synthetic-unrelated')) {
            for ($attempt = 1; $attempt -le $maximumAttempts; $attempt += 1) {
                $clearResult = Clear-RotationOwnedClipboard -Expected $owned
                if ($clearResult -ne 'Failed') { break }
                Start-Sleep -Milliseconds $retryDelayMilliseconds
            }
        }
        throw 'clipboard-test-restore-failed'
    }
}
$result | ConvertTo-Json -Compress
"""

    # When: the real Windows clipboard is set, inspected, cleared, and replaced.
    completed = _run_sta_probe(script, secret=secret)

    # Then: both exclusion controls are serialized and unrelated text is preserved.
    assert completed.returncode == 0, completed.stderr
    assert secret not in completed.stdout + completed.stderr
    result = ClipboardProbeResult.model_validate_json(completed.stdout)
    assert result.model_dump() == {
        "textMatches": True,
        "excluded": True,
        "history": 0,
        "cloud": 0,
        "clearOwned": "Cleared",
        "clearUnrelated": "NotOwned",
        "unrelatedPreserved": True,
    }


def test_final_clear_failure_keeps_ownership_and_blocks_window_close() -> None:
    # Given: the final bounded automatic clear attempt failed while the secret is owned.
    secret = f"synthetic-{secrets.token_urlsafe(32)}"
    script = r"""
$ErrorActionPreference = 'Stop'
Import-Module $env:AEROONE_CLIPBOARD_MODULE -Force -DisableNameChecking
$decision = Resolve-RotationClipboardDecision -Result Failed -Attempt 5 -MaximumAttempts 5
$decision | ConvertTo-Json -Compress
"""

    # When: the UI state-machine resolves the failed result.
    completed = _run_sta_probe(script, secret=secret)

    # Then: plaintext ownership remains, automatic retries stop, and close is refused.
    assert completed.returncode == 0, completed.stderr
    result = ClipboardDecisionResult.model_validate_json(completed.stdout)
    assert result.model_dump() == {
        "KeepOwnership": True,
        "ScheduleRetry": False,
        "AllowClose": False,
        "OperatorActionRequired": True,
    }
