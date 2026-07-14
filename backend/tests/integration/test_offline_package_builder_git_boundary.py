from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


VERSION = "1.13.1"
BUILDER = Path(__file__).parents[3] / "scripts" / "build_offline_package.ps1"
RUNNER = r'''
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:BUILDER, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'builder-parse-failed' }
$names = @(
    'Get-GitState',
    'Get-CommitPaths',
    'Get-CapturedGitSource',
    'Invoke-GitArchiveAllowList',
    'Invoke-CapturedGitArchive',
    'Invoke-BackendWheelhouse',
    'Assert-ContainedOutputDirectory'
)
$texts = foreach ($name in $names) {
    $node = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true))[0]
    if (-not $node) { throw "function-missing:$name" }
    $node.Extent.Text
}
. ([scriptblock]::Create(($texts -join "`n")))
$RepoRoot = $env:REPO
if ($env:FAIL_STATUS) {
    Set-Item -Path Function:git -Value { $global:LASTEXITCODE = 1 }
    try {
        Get-GitState -RequestedVersion $env:VERSION | Out-Null
        @{ statusError = $null } | ConvertTo-Json -Compress
    } catch {
        @{ statusError = $_.Exception.Message } | ConvertTo-Json -Compress
    }
    exit
}
if ($env:FAIL_TAG_INSPECTION) {
    $gitApplication = (Get-Command git -CommandType Application | Select-Object -First 1).Source
    $gitShim = {
        param([Parameter(ValueFromRemainingArguments = $true)] [object[]]$GitArgs)
        if ($GitArgs.Count -gt 0 -and $GitArgs[0] -eq 'show-ref') {
            $global:LASTEXITCODE = 2
            return
        }
        & $gitApplication @GitArgs
    }.GetNewClosure()
    Set-Item -Path Function:git -Value $gitShim
    try {
        Get-GitState -RequestedVersion $env:VERSION | Out-Null
        @{ tagError = $null } | ConvertTo-Json -Compress
    } catch {
        @{ tagError = $_.Exception.Message } | ConvertTo-Json -Compress
    }
    exit
}
$source = Get-CapturedGitSource -RequestedVersion $env:VERSION
$state = $source.State
$result = [ordered]@{
    clean = $state.IsClean
    commit = $state.HeadCommit
    tag = $state.HeadTag
    paths = @($source.Paths)
}
if ($env:ADVANCE) {
    [IO.File]::WriteAllText((Join-Path $RepoRoot 'tracked.txt'), "commit-B`n")
    Push-Location $RepoRoot
    try {
        git add tracked.txt
        if ($LASTEXITCODE -ne 0) { throw 'advance-add-failed' }
        git commit -qm B
        if ($LASTEXITCODE -ne 0) { throw 'advance-commit-failed' }
        $result.headAfterCapture = (git rev-parse HEAD).Trim()
    } finally {
        Pop-Location
    }
    $stage = $env:STAGE
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Invoke-CapturedGitArchive -CapturedSource $source -SelectedPaths @('tracked.txt') -StageRoot $stage
    $result.archived = [IO.File]::ReadAllText((Join-Path $stage 'tracked.txt'))
}
if ($env:CHECK_OUTPUT) {
    try {
        $result.output = Assert-ContainedOutputDirectory -OutputDirectory $env:OUTPUT -AllowedRoot $env:ROOT
        $result.outputError = $null
    } catch {
        $result.output = $null
        $result.outputError = $_.Exception.Message
    }
}
if ($env:CHECK_REQUIREMENTS) {
    try {
        Invoke-BackendWheelhouse -RequirementsPath $env:REQUIREMENTS -WheelDir $env:WHEELS -StageRoot $env:STAGE | Out-Null
        $result.requirementsError = $null
    } catch {
        $result.requirementsError = $_.Exception.Message
    }
}
$result | ConvertTo-Json -Compress
'''


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, capture_output=True
    ).stdout.strip()


def _repo_at_a(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Boundary Test")
    (repo / "tracked.txt").write_text("commit-A\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "A")
    return repo, _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo, commit_a = _repo_at_a(tmp_path)
    (repo / "tracked.txt").write_text("commit-B\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "B")
    return repo, commit_a, _git(repo, "rev-parse", "HEAD")


def _run(
    ps: str,
    runner_path: Path,
    repo: Path,
    *,
    tag: str | None = None,
    annotated: bool = False,
    advance: bool = False,
    stage: Path | None = None,
    fail_status: bool = False,
    fail_tag_inspection: bool = False,
    output_root: Path | None = None,
    output: Path | None = None,
    requirements: Path | None = None,
) -> dict[str, object]:
    if tag:
        args = ["tag"]
        if annotated:
            args += ["-a", "-m", tag]
        args += [tag]
        _git(repo, *args)
    env = os.environ.copy()
    env.update({"BUILDER": str(BUILDER), "REPO": str(repo), "VERSION": VERSION})
    if advance:
        env["ADVANCE"] = "1"
        env["STAGE"] = str(stage)
    if fail_status:
        env["FAIL_STATUS"] = "1"
    if fail_tag_inspection:
        env["FAIL_TAG_INSPECTION"] = "1"
    if output_root is not None and output is not None:
        env["CHECK_OUTPUT"] = "1"
        env["ROOT"] = str(output_root)
        env["OUTPUT"] = str(output)
    if requirements is not None:
        env["CHECK_REQUIREMENTS"] = "1"
        env["REQUIREMENTS"] = str(requirements)
        env["WHEELS"] = str(repo / "wheels")
        env["STAGE"] = str(repo)
    output_text = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(runner_path)],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    ).stdout.strip()
    return json.loads(output_text)


@pytest.fixture(scope="module")
def powershell_runner(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, Path]:
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        pytest.skip("PowerShell is required for the executable builder boundary")
    path = tmp_path_factory.mktemp("builder-boundary") / "runner.ps1"
    path.write_text(RUNNER, encoding="utf-8")
    return ps, path


def test_git_state_tag_classification_and_commit_bound_archive(
    tmp_path: Path, powershell_runner: tuple[str, Path]
) -> None:
    ps, runner_path = powershell_runner

    repo, commit_a, commit_b = _repo(tmp_path / "no-tag")
    no_tag = _run(ps, runner_path, repo)
    assert no_tag["clean"] is True and no_tag["tag"] is None
    assert no_tag["commit"] == commit_b

    repo, _, _ = _repo(tmp_path / "lightweight")
    lightweight = _run(ps, runner_path, repo, tag=f"v{VERSION}")
    assert lightweight["tag"] is None

    repo, commit_a, _ = _repo(tmp_path / "mismatch")
    _git(repo, "tag", "-a", "-m", "wrong", VERSION, commit_a)
    mismatch = _run(ps, runner_path, repo)
    assert mismatch["tag"] is None

    repo, _, commit_b = _repo(tmp_path / "exact")
    exact = _run(ps, runner_path, repo, tag=VERSION, annotated=True)
    assert exact["tag"] == VERSION and exact["commit"] == commit_b

    repo, _, _ = _repo(tmp_path / "prefixed")
    prefixed = _run(ps, runner_path, repo, tag=f"v{VERSION}", annotated=True)
    assert prefixed["tag"] is None

    repo, _, _ = _repo(tmp_path / "multiple")
    _git(repo, "tag", "-a", "-m", "other", "v9.9.9")
    multiple = _run(ps, runner_path, repo, tag=VERSION, annotated=True)
    assert multiple["tag"] == VERSION
    root = tmp_path / "output-root"
    contained = _run(ps, runner_path, repo, output_root=root, output=root / "Version" / "AeroOne")
    assert contained["output"] == str(root / "Version" / "AeroOne")
    escaped = _run(ps, runner_path, repo, output_root=root, output=tmp_path / "outside")
    assert "output-path-escape" in str(escaped["outputError"])

    repo, commit_a = _repo_at_a(tmp_path / "captured")
    stage = tmp_path / "captured-stage"
    captured = _run(ps, runner_path, repo, advance=True, stage=stage)
    assert captured["commit"] == commit_a
    assert captured["headAfterCapture"] != commit_a
    assert captured["paths"] == ["tracked.txt"]
    assert str(captured["archived"]).splitlines() == ["commit-A"]

    repo, _, _ = _repo(tmp_path / "status-failure")
    failed_status = _run(ps, runner_path, repo, fail_status=True)
    assert failed_status["statusError"] == "git-status-failed"
    tag_inspection_failure = _run(ps, runner_path, repo, fail_tag_inspection=True)
    assert tag_inspection_failure["tagError"] == "git-tag-inspection-failed"

    invalid_requirements = repo / "other" / "requirements.txt"
    requirements_result = _run(
        ps,
        runner_path,
        repo,
        requirements=invalid_requirements,
    )
    assert "dev-dependencies-forbidden" in str(requirements_result["requirementsError"])


def test_output_root_reparse_point_is_rejected(
    tmp_path: Path,
    powershell_runner: tuple[str, Path],
) -> None:
    ps, runner_path = powershell_runner
    repo, _, _ = _repo(tmp_path / "reparse-repo")
    outside = tmp_path / "outside-target"
    outside.mkdir()
    junction = tmp_path / "output-junction"
    env = os.environ.copy()
    env.update({"LINK": str(junction), "TARGET": str(outside)})
    created = subprocess.run(
        [
            ps,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item -ItemType Junction -Path $env:LINK -Target $env:TARGET | Out-Null",
        ],
        text=True,
        capture_output=True,
        env=env,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr.strip()}")

    result = _run(
        ps,
        runner_path,
        repo,
        output_root=junction,
        output=junction / "AeroOne",
    )
    assert "output-path-reparse-point" in str(result["outputError"])