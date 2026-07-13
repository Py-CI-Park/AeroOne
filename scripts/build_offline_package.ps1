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
    [string]$PythonExecutable = 'py',
    [string[]]$PythonArguments = @('-3.12'),
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

function Assert-Python312 {
    $version = & $PythonExecutable @PythonArguments -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0 -or ([string]$version).Trim() -ne '3.12') {
        throw 'python-version-mismatch'
    }
}
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
      Gathers cleanliness, captured HEAD, and only the requested annotated tag.
    #>
    param([Parameter(Mandatory = $true)] [string]$RequestedVersion)

    Push-Location $RepoRoot
    try {
        $statusLines = git status --porcelain
        if ($LASTEXITCODE -ne 0) { throw 'git-status-failed' }
        $isClean = -not ($statusLines | Where-Object { $_ -ne '' })
        $headCommit = (git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $headCommit -notmatch '^[0-9a-f]{40}$') { throw 'git-head-failed' }
        $exactTag = $null
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'SilentlyContinue'
        try {
            $tagName = "v$RequestedVersion"
            $tagObject = git rev-parse --verify --quiet "refs/tags/$tagName^{tag}"
            if ($LASTEXITCODE -eq 0 -and $tagObject) {
                $peeledCommit = git rev-parse --verify --quiet "refs/tags/$tagName^{commit}"
                if ($LASTEXITCODE -eq 0 -and ([string]$peeledCommit).Trim() -eq $headCommit) {
                    $exactTag = $tagName
                }
            }
        } finally {
            $ErrorActionPreference = $previousEap
        }
        return [PSCustomObject]@{ IsClean = [bool]$isClean; HeadCommit = $headCommit; HeadTag = $exactTag }
    }
    finally { Pop-Location }
}

function Get-CommitPaths {
    param([Parameter(Mandatory = $true)] [string]$Commit)
    Push-Location $RepoRoot
    try {
        $paths = git ls-tree -r --name-only $Commit
        if ($LASTEXITCODE -ne 0) { throw 'git-ls-tree-failed' }
        return $paths
    }
    finally { Pop-Location }
}

function Get-CapturedGitSource {
    param([Parameter(Mandatory = $true)] [string]$RequestedVersion)
    $state = Get-GitState -RequestedVersion $RequestedVersion
    $paths = @(Get-CommitPaths -Commit $state.HeadCommit)
    return [PSCustomObject]@{ State = $state; Paths = $paths }
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

    $output = & $PythonExecutable @PythonArguments @planArgs
    $exitCode = $LASTEXITCODE
    $result = $output | ConvertFrom-Json
    if ($exitCode -ne 0 -or -not $result.ok) {
        throw "offline-package-build-policy-violation:$($result.code)"
    }
    return $result
}
function Assert-ContainedOutputDirectory {
    param([Parameter(Mandatory = $true)] [string]$OutputDirectory, [Parameter(Mandatory = $true)] [string]$AllowedRoot)
    $root = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\', '/')
    $destination = [System.IO.Path]::GetFullPath($OutputDirectory).TrimEnd('\', '/')
    $prefix = "$root$([System.IO.Path]::DirectorySeparatorChar)"
    if (-not ([string]::Equals($destination, $root, [StringComparison]::OrdinalIgnoreCase) -or $destination.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase))) {
        throw 'offline-package-build-policy-violation:output-path-escape'
    }
    $cursor = $destination
    while ($true) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'offline-package-build-policy-violation:output-path-reparse-point'
        }
        if ([string]::Equals($cursor, $root, [StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if (-not $parent) {
            throw 'offline-package-build-policy-violation:output-path-escape'
        }
        $cursor = $parent.FullName.TrimEnd('\', '/')
    }
    return $destination
}

function New-StageDirectory {
    param([Parameter(Mandatory = $true)] [string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Invoke-GitArchiveAllowList {
    param(
        [Parameter(Mandatory = $true)] [string]$Commit,
        [Parameter(Mandatory = $true)] [string[]]$SelectedPaths,
        [Parameter(Mandatory = $true)] [string]$StageRoot
    )
    $archiveZip = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "$([System.IO.Path]::GetRandomFileName()).zip")
    try {
        Push-Location $RepoRoot
        try {
            & git archive --format=zip -o $archiveZip $Commit -- @SelectedPaths
            if ($LASTEXITCODE -ne 0) { throw 'git-archive-failed' }
        } finally { Pop-Location }
        Expand-Archive -LiteralPath $archiveZip -DestinationPath $StageRoot -Force
    } finally {
        if (Test-Path -LiteralPath $archiveZip) { Remove-Item -LiteralPath $archiveZip -Force -ErrorAction SilentlyContinue }
    }
}

function Invoke-CapturedGitArchive {
    param(
        [Parameter(Mandatory = $true)] $CapturedSource,
        [Parameter(Mandatory = $true)] [string[]]$SelectedPaths,
        [Parameter(Mandatory = $true)] [string]$StageRoot
    )
    Invoke-GitArchiveAllowList `
        -Commit $CapturedSource.State.HeadCommit `
        -SelectedPaths $SelectedPaths `
        -StageRoot $StageRoot
}

function Invoke-FrontendBuild {
    <#
      .SYNOPSIS
      Clean ``npm ci`` (never reused from the source workspace) + production
      build + dev-dependency prune, so the staged ``node_modules``/``.next``
      never carry devDependencies or a stale prior install.
    #>
    param(
        [Parameter(Mandatory = $true)] [string]$FrontendDir,
        [Parameter(Mandatory = $true)] [string]$BuildId
    )

    Push-Location $FrontendDir
    try {
        & $NpmExecutable ci
        if ($LASTEXITCODE -ne 0) { throw 'npm-ci-failed' }

        $previousBuildId = [Environment]::GetEnvironmentVariable('AEROONE_BUILD_ID', 'Process')
        try {
            [Environment]::SetEnvironmentVariable('AEROONE_BUILD_ID', $BuildId, 'Process')
            & $NpmExecutable run build
            if ($LASTEXITCODE -ne 0) { throw 'npm-build-failed' }
        }
        finally {
            [Environment]::SetEnvironmentVariable('AEROONE_BUILD_ID', $previousBuildId, 'Process')
        }

        & $NpmExecutable prune --omit=dev
        if ($LASTEXITCODE -ne 0) { throw 'npm-prune-failed' }

        foreach ($cachePath in @('.next\cache', 'node_modules\.cache')) {
            if (Test-Path -LiteralPath $cachePath) {
                Remove-Item -LiteralPath $cachePath -Recurse -Force
            }
        }
    }
    finally {
        Pop-Location
    }
}

    <#
      .SYNOPSIS
      Downloads the production wheelhouse strictly from
      ``backend/requirements.txt`` (never requirements-dev.txt).
    #>
function Invoke-BackendWheelhouse {
    param(
        [Parameter(Mandatory = $true)] [string]$RequirementsPath,
        [Parameter(Mandatory = $true)] [string]$WheelDir,
        [Parameter(Mandatory = $true)] [string]$StageRoot
    )
    $stageFull = [System.IO.Path]::GetFullPath($StageRoot)
    $requirementsFull = [System.IO.Path]::GetFullPath($RequirementsPath)
    $expected = [System.IO.Path]::GetFullPath((Join-Path $stageFull 'backend\requirements.txt'))
    if (-not [string]::Equals($requirementsFull, $expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'offline-package-build-policy-violation:dev-dependencies-forbidden'
    }
    New-Item -ItemType Directory -Path $WheelDir -Force | Out-Null
    & $PythonExecutable @PythonArguments -m pip download -r $RequirementsPath -d $WheelDir
    if ($LASTEXITCODE -ne 0) { throw 'pip-download-failed' }
}

function Copy-RequiredInstallers {
    param(
        [Parameter(Mandatory = $true)] [string]$InstallerSourceDir,
        [Parameter(Mandatory = $true)] [string]$StageRoot,
        [Parameter(Mandatory = $true)] [string]$PolicyPath
    )
    $destination = Join-Path $StageRoot 'offline_assets\installers'
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json

    foreach ($installer in $policy.required_installers) {
        $filename = [string]$installer.filename
        $source = Join-Path $InstallerSourceDir $filename
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw 'installer-missing'
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $destination $filename)
        "offline_assets/installers/$filename"
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
        $output = & $PythonExecutable @PythonArguments @manifestArgs
        if ($LASTEXITCODE -ne 0) { throw "offline-package-manifest-failed:$output" }
    }
    finally {
        Remove-Item -LiteralPath $selectedFile -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

Assert-Python312
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$' -or $Version -match '[^\x00-\x7F]') {
    throw 'offline-package-build-policy-violation:invalid-version'
}
$gitSource = Get-CapturedGitSource -RequestedVersion $Version
$gitState = $gitSource.State
$trackedPathsFile = [System.IO.Path]::GetTempFileName()
$selectedOutFile = [System.IO.Path]::GetTempFileName()
try {
    Write-Utf8NoBom -Path $trackedPathsFile -Value ($gitSource.Paths -join "`n")

    $plan = Invoke-BuildPlan -Version $Version -GitState $gitState -TrackedPathsFile $trackedPathsFile -SelectedOutFile $selectedOutFile
    $selectedPaths = Get-Content -LiteralPath $selectedOutFile

    Write-Output "[PLAN] mode=$($plan.mode) publishable=$($plan.publishable) output_dir=$($plan.output_dir) zip_name=$($plan.zip_name) selected_count=$($plan.selected_count)"

    if ($DryRun) {
        Write-Output '[DRY-RUN] git archive allow-list -> npm ci/build/prune -> wheelhouse -> installers -> manifest -> ZIP -> Task 5 verify (not executed)'
        exit 0
    }

    $outputRoot = if ($plan.mode -eq 'release') { Join-Path $RepoRoot 'dist' } else { Join-Path $RepoRoot 'artifacts\qa' }
    $outputDir = Assert-ContainedOutputDirectory -OutputDirectory (Join-Path $RepoRoot ($plan.output_dir -replace '/', '\')) -AllowedRoot $outputRoot
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

    $stageRoot = Join-Path $outputDir 'AeroOne'
    New-StageDirectory -Path $stageRoot

    Invoke-CapturedGitArchive -CapturedSource $gitSource -SelectedPaths $selectedPaths -StageRoot $stageRoot

    Invoke-FrontendBuild -FrontendDir (Join-Path $stageRoot 'frontend') -BuildId $gitState.HeadCommit

    Invoke-BackendWheelhouse -RequirementsPath (Join-Path $stageRoot 'backend\requirements.txt') -WheelDir (Join-Path $stageRoot 'offline_assets\python-wheels') -StageRoot $stageRoot

    $generatedPaths = @(
        Copy-RequiredInstallers `
            -InstallerSourceDir (Join-Path $RepoRoot 'offline_installers') `
            -StageRoot $stageRoot `
            -PolicyPath $PolicyPath
    )
    $frontendGeneratedPaths = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'frontend\node_modules'), (Join-Path $stageRoot 'frontend\.next') -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.FullName.Substring($stageRoot.Length + 1)) -replace '\\', '/' }
    $wheelGeneratedPaths = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'offline_assets\python-wheels') -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { ($_.FullName.Substring($stageRoot.Length + 1)) -replace '\\', '/' }
    $allPaths = @($selectedPaths) + $generatedPaths + $frontendGeneratedPaths + $wheelGeneratedPaths

    $manifestPath = Join-Path $outputDir 'manifest.json'
    New-PackageManifest -StageRoot $stageRoot -AllPaths $allPaths -GitState $gitState -ManifestOut $manifestPath

    Import-Module $VerifierModule -Force
    $signatureMap = Get-RequiredInstallerSignatureMap -PolicyPath $PolicyPath -StageRoot $stageRoot
    $signaturesPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "$([System.IO.Path]::GetRandomFileName()).json")
    $digestsPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "$([System.IO.Path]::GetRandomFileName()).json")
    try {
        Write-Utf8NoBom -Path $signaturesPath -Value ($signatureMap | ConvertTo-Json -Depth 4)
        $verifyArgs = @(
            $VerifierCli, 'pre-stage',
            '--stage-root', $stageRoot,
            '--manifest', $manifestPath,
            '--policy', $PolicyPath,
            '--origin', 'AeroOne',
            '--commit', $gitState.HeadCommit,
            '--policy-label', 'release-qa@1',
            '--signatures', $signaturesPath,
            '--digests-out', $digestsPath
        )
        if ($gitState.HeadTag) { $verifyArgs += @('--tag', $gitState.HeadTag) }
        & $PythonExecutable @PythonArguments @verifyArgs
        $preStageExit = $LASTEXITCODE
        if ($preStageExit -ne 0) { throw 'pre-stage-verification-failed' }

        $zipPath = Join-Path $outputDir $plan.zip_name
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($stageRoot, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

        & $PythonExecutable @PythonArguments $VerifierCli post-zip --zip $zipPath --manifest $manifestPath --digests $digestsPath
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
