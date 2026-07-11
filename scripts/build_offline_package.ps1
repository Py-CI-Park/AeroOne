#Requires -Version 5.1
<#
  .SYNOPSIS
  Public offline-package builder (Task 6, AeroOne v1.13.0): git-archive
  allow-list -> clean temp stage -> npm ci/build/production-prune ->
  backend wheelhouse -> Task 5 installers -> manifest/ZIP/SHA-256.

  .DESCRIPTION
  Boundary decisions (release vs QA mode, allow-list path selection,
  fail-closed rejection of reuse/dev-dependency/public-data/timestamp-
  fallback options) are delegated to the Python CLI
  ``packaging/build_offline_package_plan.py``, which wraps the pure
  functions in ``backend/app/operations/offline_package_policy.py``. This
  script performs only the OS-layer mechanics: git plumbing, npm/pip
  invocation, staging, zipping, and Task 5 verification.

  Replaces the legacy ``offline_package.bat`` robocopy deny-list approach
  (workspace robocopy, node_modules/.next/wheelhouse reuse, requirements-dev
  install, timestamp-only naming) with a git-archive allow-list build that
  is fail-closed by construction and verified end-to-end by the Task 5
  pre-stage/post-ZIP policy verifier before the ZIP is trusted.

  .PARAMETER Version
  The AeroOne version this build targets (e.g. "1.13.0"). Release mode
  requires an exact annotated tag "v<Version>" pointing at HEAD; anything
  else (no tag, mismatched tag) automatically falls back to QA mode.

  .PARAMETER DryRun
  Print the resolved plan (mode, output location, selected path count) and
  exit without touching disk beyond the plan/tracked-paths temp files.

  .PARAMETER ReuseNodeModules / ReuseNextBuild / ReuseWheelhouse /
  IncludeDevDependencies / AllowPublicData / AllowTimestampFallback
  Every one of these switches is always rejected by the underlying policy
  plan (fail-closed, no override). They exist only so operators/tests can
  attempt the forbidden legacy behaviors and observe the exact rejection
  code, matching the Task 5 verifier's redacted-category-code contract.
#>
[CmdletBinding()]
param(
    [string]$Version = '1.13.0',
    [switch]$DryRun,
    [switch]$Help,
    [switch]$ReuseNodeModules,
    [switch]$ReuseNextBuild,
    [switch]$ReuseWheelhouse,
    [switch]$IncludeDevDependencies,
    [switch]$AllowPublicData,
    [switch]$AllowTimestampFallback,
    [string]$PythonExecutable = 'python',
    [string]$NpmExecutable = 'npm'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Help) {
    Write-Output 'Usage: build_offline_package.ps1 [-Version <x.y.z>] [-DryRun] [-Help]'
    Write-Output ''
    Write-Output 'Builds a public offline-package ZIP from a git-archive allow-list.'
    Write-Output 'Release mode requires an exact annotated tag v<Version> at HEAD.'
    Write-Output 'Otherwise the build lands in QA mode under artifacts\qa\ (publishable=false).'
    exit 0
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PlanCli = Join-Path $RepoRoot 'packaging\build_offline_package_plan.py'
$PolicyPath = Join-Path $RepoRoot 'packaging\installer-policy.json'
$VerifierModule = Join-Path $RepoRoot 'scripts\packaging\Verify-OfflinePackage.psm1'
$VerifierCli = Join-Path $RepoRoot 'packaging\verify_offline_package.py'
function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Value
    )
    $encoding = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Value, $encoding)
}


function Get-GitState {
    <#
      .SYNOPSIS
      Gathers the fail-closed-relevant git facts: worktree cleanliness, HEAD
      commit, and the exact annotated tag at HEAD (if any). Never falls back
      to a wall-clock timestamp.
    #>
    Push-Location $RepoRoot
    try {
        $statusLines = git status --porcelain
        $isClean = -not ($statusLines | Where-Object { $_ -ne '' })

        $headCommit = (git rev-parse HEAD).Trim()

        $exactTag = $null
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        try {
            $describeOutput = git describe --tags --exact-match HEAD 2>$null
            if ($LASTEXITCODE -eq 0 -and $describeOutput) {
                $exactTag = ([string]$describeOutput).Trim()
            }
        } finally {
            $ErrorActionPreference = $previousEap
        }

        return [PSCustomObject]@{
            IsClean    = [bool]$isClean
            HeadCommit = $headCommit
            HeadTag    = $exactTag
        }
    }
    finally {
        Pop-Location
    }
}

function Get-TrackedPaths {
    <#
      .SYNOPSIS
      The git-archive source-of-truth path list: every path git tracks at
      HEAD, unfiltered. Allow-list filtering happens exclusively in the
      Python policy layer (``select_allowlisted_paths``), never here.
    #>
    Push-Location $RepoRoot
    try {
        return git ls-files
    }
    finally {
        Pop-Location
    }
}

function Invoke-BuildPlan {
    param(
        [Parameter(Mandatory = $true)] [string]$Version,
        [Parameter(Mandatory = $true)] $GitState,
        [Parameter(Mandatory = $true)] [string]$TrackedPathsFile,
        [Parameter(Mandatory = $true)] [string]$SelectedOutFile
    )

    $planArgs = @(
        $PlanCli, 'plan',
        '--version', $Version,
        '--commit', $GitState.HeadCommit,
        '--policy', $PolicyPath,
        '--tracked-paths', $TrackedPathsFile,
        '--selected-out', $SelectedOutFile
    )
    if ($GitState.IsClean) { $planArgs += '--clean' }
    if ($GitState.HeadTag) { $planArgs += @('--tag', $GitState.HeadTag) }
    if ($ReuseNodeModules) { $planArgs += '--reuse-node-modules' }
    if ($ReuseNextBuild) { $planArgs += '--reuse-next-build' }
    if ($ReuseWheelhouse) { $planArgs += '--reuse-wheelhouse' }
    if ($IncludeDevDependencies) { $planArgs += '--include-dev-dependencies' }
    if ($AllowPublicData) { $planArgs += '--allow-public-data' }
    if ($AllowTimestampFallback) { $planArgs += '--allow-timestamp-fallback' }

    $output = & $PythonExecutable @planArgs
    $exitCode = $LASTEXITCODE
    $result = $output | ConvertFrom-Json
    if ($exitCode -ne 0 -or -not $result.ok) {
        throw "offline-package-build-policy-violation:$($result.code)"
    }
    return $result
}

function New-StageDirectory {
    param([Parameter(Mandatory = $true)] [string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Invoke-GitArchiveAllowList {
    <#
      .SYNOPSIS
      Materializes the allow-listed source tree using ``git archive`` with
      the already-computed (Python-validated) selected-path list as an
      explicit pathspec, so the archive itself can never contain a path the
      policy layer did not approve.
    #>
    param(
        [Parameter(Mandatory = $true)] [string[]]$SelectedPaths,
        [Parameter(Mandatory = $true)] [string]$StageRoot
    )
    $archiveZip = [System.IO.Path]::GetTempFileName() + '.zip'
    try {
        Push-Location $RepoRoot
        try {
            & git archive --format=zip -o $archiveZip HEAD -- @SelectedPaths
            if ($LASTEXITCODE -ne 0) { throw 'git-archive-failed' }
        }
        finally {
            Pop-Location
        }
        Expand-Archive -LiteralPath $archiveZip -DestinationPath $StageRoot -Force
    }
    finally {
        if (Test-Path -LiteralPath $archiveZip) {
            Remove-Item -LiteralPath $archiveZip -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-FrontendBuild {
    <#
      .SYNOPSIS
      Clean ``npm ci`` (never reused from the source workspace) + production
      build + dev-dependency prune, so the staged ``node_modules``/``.next``
      never carry devDependencies or a stale prior install.
    #>
    param([Parameter(Mandatory = $true)] [string]$FrontendDir)

    Push-Location $FrontendDir
    try {
        & $NpmExecutable ci
        if ($LASTEXITCODE -ne 0) { throw 'npm-ci-failed' }

        & $NpmExecutable run build
        if ($LASTEXITCODE -ne 0) { throw 'npm-build-failed' }

        & $NpmExecutable prune --omit=dev
        if ($LASTEXITCODE -ne 0) { throw 'npm-prune-failed' }
    }
    finally {
        Pop-Location
    }
}

function Invoke-BackendWheelhouse {
    <#
      .SYNOPSIS
      Downloads the production wheelhouse strictly from
      ``backend/requirements.txt`` (never requirements-dev.txt).
    #>
    param(
        [Parameter(Mandatory = $true)] [string]$RequirementsPath,
        [Parameter(Mandatory = $true)] [string]$WheelDir
    )

    # Fail-closed guard mirrored from the Python policy layer: refuse
    # anything but the production requirements file before ever shelling
    # out to pip.
    if ([System.IO.Path]::GetFileName($RequirementsPath) -ne 'requirements.txt') {
        throw 'offline-package-build-policy-violation:dev-dependencies-forbidden'
    }
    New-Item -ItemType Directory -Path $WheelDir -Force | Out-Null
    & $PythonExecutable -m pip download -r $RequirementsPath -d $WheelDir
    if ($LASTEXITCODE -ne 0) { throw 'pip-download-failed' }
}

function Copy-RequiredInstallers {
    param(
        [Parameter(Mandatory = $true)] [string]$InstallerSourceDir,
        [Parameter(Mandatory = $true)] [string]$StageRoot
    )
    $destination = Join-Path $StageRoot 'offline_assets\installers'
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    if (Test-Path -LiteralPath $InstallerSourceDir) {
        robocopy $InstallerSourceDir $destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
    }
}

function New-PackageManifest {
    param(
        [Parameter(Mandatory = $true)] [string]$StageRoot,
        [Parameter(Mandatory = $true)] [string[]]$AllPaths,
        [Parameter(Mandatory = $true)] $GitState,
        [Parameter(Mandatory = $true)] [string]$ManifestOut
    )
    $selectedFile = [System.IO.Path]::GetTempFileName()
    try {
        Write-Utf8NoBom -Path $selectedFile -Value ($AllPaths -join "`n")
        $manifestArgs = @(
            $PlanCli, 'manifest',
            '--stage-root', $StageRoot,
            '--selected-paths', $selectedFile,
            '--commit', $GitState.HeadCommit,
            '--policy-label', 'release-qa@1',
            '--manifest-out', $ManifestOut
        )
        if ($GitState.HeadTag) { $manifestArgs += @('--tag', $GitState.HeadTag) }
        $output = & $PythonExecutable @manifestArgs
        if ($LASTEXITCODE -ne 0) { throw "offline-package-manifest-failed:$output" }
    }
    finally {
        Remove-Item -LiteralPath $selectedFile -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

$gitState = Get-GitState
$trackedPathsFile = [System.IO.Path]::GetTempFileName()
$selectedOutFile = [System.IO.Path]::GetTempFileName()
try {
    Write-Utf8NoBom -Path $trackedPathsFile -Value ((Get-TrackedPaths) -join "`n")

    $plan = Invoke-BuildPlan -Version $Version -GitState $gitState -TrackedPathsFile $trackedPathsFile -SelectedOutFile $selectedOutFile
    $selectedPaths = Get-Content -LiteralPath $selectedOutFile

    Write-Output "[PLAN] mode=$($plan.mode) publishable=$($plan.publishable) output_dir=$($plan.output_dir) zip_name=$($plan.zip_name) selected_count=$($plan.selected_count)"

    if ($DryRun) {
        Write-Output '[DRY-RUN] git archive allow-list -> npm ci/build/prune -> wheelhouse -> installers -> manifest -> ZIP -> Task 5 verify (not executed)'
        exit 0
    }

    $outputDir = Join-Path $RepoRoot ($plan.output_dir -replace '/', '\')
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

    $stageRoot = Join-Path $outputDir 'AeroOne'
    New-StageDirectory -Path $stageRoot

    Invoke-GitArchiveAllowList -SelectedPaths $selectedPaths -StageRoot $stageRoot

    Invoke-FrontendBuild -FrontendDir (Join-Path $stageRoot 'frontend')

    Invoke-BackendWheelhouse -RequirementsPath (Join-Path $stageRoot 'backend\requirements.txt') -WheelDir (Join-Path $stageRoot 'offline_assets\python-wheels')

    Copy-RequiredInstallers -InstallerSourceDir (Join-Path $RepoRoot 'offline_installers') -StageRoot $stageRoot

    $generatedPaths = @(
        'offline_assets\installers\python-3.12.7-amd64.exe',
        'offline_assets\installers\node-v20.18.0-x64.msi'
    ) | ForEach-Object { $_ -replace '\\', '/' }
    $frontendGeneratedPaths = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'frontend\node_modules'), (Join-Path $stageRoot 'frontend\.next') -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.FullName.Substring($stageRoot.Length + 1)) -replace '\\', '/' }
    $wheelGeneratedPaths = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'offline_assets\python-wheels') -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.FullName.Substring($stageRoot.Length + 1)) -replace '\\', '/' }
    $allPaths = @($selectedPaths) + $generatedPaths + $frontendGeneratedPaths + $wheelGeneratedPaths

    $manifestPath = Join-Path $outputDir 'manifest.json'
    New-PackageManifest -StageRoot $stageRoot -AllPaths $allPaths -GitState $gitState -ManifestOut $manifestPath

    Import-Module $VerifierModule -Force
    $signatureMap = Get-RequiredInstallerSignatureMap -PolicyPath $PolicyPath -StageRoot $stageRoot
    $signaturesPath = [System.IO.Path]::GetTempFileName() + '.json'
    $digestsPath = [System.IO.Path]::GetTempFileName() + '.json'
    try {
        Write-Utf8NoBom -Path $signaturesPath -Value ($signatureMap | ConvertTo-Json -Depth 4)
        $verifyTag = if ($gitState.HeadTag) { $gitState.HeadTag } else { '' }
        & $PythonExecutable $VerifierCli pre-stage `
            --stage-root $stageRoot --manifest $manifestPath --policy $PolicyPath `
            --origin AeroOne --tag $verifyTag --commit $gitState.HeadCommit `
            --policy-label release-qa@1 --signatures $signaturesPath --digests-out $digestsPath
        $preStageExit = $LASTEXITCODE
        if ($preStageExit -ne 0) { throw 'pre-stage-verification-failed' }

        $zipPath = Join-Path $outputDir $plan.zip_name
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($stageRoot, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

        & $PythonExecutable $VerifierCli post-zip --zip $zipPath --manifest $manifestPath --digests $digestsPath
        $postZipExit = $LASTEXITCODE
        if ($postZipExit -ne 0) { throw 'post-zip-verification-failed' }

        $sha256 = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Set-Content -LiteralPath "$zipPath.sha256" -Value "$sha256  $($plan.zip_name)" -Encoding ascii

        Write-Output "[OK] offline package created: $zipPath"
        Write-Output "[OK] publishable=$($plan.publishable) manifest=$manifestPath sha256=$sha256"
    }
    finally {
        Remove-Item -LiteralPath $signaturesPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $digestsPath -Force -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-Item -LiteralPath $trackedPathsFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $selectedOutFile -Force -ErrorAction SilentlyContinue
}
