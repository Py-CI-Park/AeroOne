#Requires -Version 5.1
<#
  .SYNOPSIS
  Windows Sandbox guest bootstrap for the offline-package smoke test
  (Task 6, AeroOne v1.13.0). Runs inside a networking-disabled sandbox via
  the WSB ``LogonCommand``. Never executed by this task (requires the
  Windows Sandbox optional feature, elevation, and real installer
  binaries) — written and AST-validated only.

  .DESCRIPTION
  Order of operations, every step recorded in an atomic receipt so the host
  can assert pass/fail without polling sandbox internals:
    1. Guest-side manifest re-verification (pure PowerShell SHA-256 recompute
       against manifest.json — no Python dependency, since Python is not yet
       installed at this point; this is what "verifier" means for the guest).
    2. Silent Python installer (exit 0 required; 3010 = reboot required = FAIL,
       since the sandbox smoke must complete unattended in one boot).
    3. Silent Node MSI installer (same exit-code contract).
    4. PATH refresh from the machine+user registry (the current process does
       not observe installer-time PATH changes without this).
    5. Exact version assertions for python/node/npm.
    6. Unattended ``setup_offline.bat``/``start_offline.bat`` (no interactive
       pause), backend health check, frontend reachability, login flow, and
       an "empty NSA" check (no NSA-root data staged by default), then
       ``stop_all.bat``.
  Any failure short-circuits to the receipt with ``ok = $false`` and the
  failing step name; the receipt is written to a temp file and atomically
  renamed into the mapped writable folder so the host never observes a
  partially-written receipt.
#>
[CmdletBinding()]
param(
    [string]$PackageDir = 'C:\AeroOnePackage',
    [string]$ReceiptDir = 'C:\AeroOneReceipt',
    [string]$ExpectedPythonVersion = 'Python 3.12.7',
    [string]$ExpectedNodeVersion = 'v20.18.0'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Steps = [ordered]@{}
$Overall = $true
$FailedStep = $null
$CurrentStep = 'bootstrap'

function Set-StepResult {
    param(
        [Parameter(Mandatory = $true)] [string]$Name,
        [Parameter(Mandatory = $true)] [bool]$Ok,
        [string]$Detail = ''
    )
    $Steps[$Name] = [PSCustomObject]@{ ok = $Ok; detail = $Detail }
    if (-not $Ok) {
        $script:Overall = $false
        if (-not $script:FailedStep) { $script:FailedStep = $Name }
    }
}

function Write-Receipt {
    $receipt = [PSCustomObject]@{
        ok          = $Overall
        failed_step = $FailedStep
        steps       = $Steps
        finished_at = (Get-Date).ToUniversalTime().ToString('o')
    }
    $tempPath = Join-Path $ReceiptDir ([System.IO.Path]::GetRandomFileName() + '.json')
    ($receipt | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $tempPath -Encoding utf8
    $finalPath = Join-Path $ReceiptDir 'receipt.json'
    Move-Item -LiteralPath $tempPath -Destination $finalPath -Force
}

function Test-ManifestIntegrity {
    <#
      .SYNOPSIS
      Guest-side re-verification without a Python dependency: recompute
      each manifest entry's SHA-256 against the extracted stage and compare.
      Runs before any installer, matching the "verifier first" contract.
    #>
    param(
        [Parameter(Mandatory = $true)] [string]$StageRoot,
        [Parameter(Mandatory = $true)] [string]$ManifestPath
    )
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    foreach ($entry in $manifest.entries) {
        $entryPath = Join-Path $StageRoot ($entry.path -replace '/', '\')
        if (-not (Test-Path -LiteralPath $entryPath -PathType Leaf)) {
            throw "manifest-entry-missing:$($entry.path)"
        }
        $actualHash = (Get-FileHash -LiteralPath $entryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $entry.sha256) {
            throw "manifest-hash-mismatch:$($entry.path)"
        }
    }
}

try {
    # --- 1. Guest-side manifest verification -----------------------------
    $CurrentStep = 'verify_manifest'
    $packageZip = Get-ChildItem -LiteralPath $PackageDir -Filter 'AeroOne-offline-*.zip' | Select-Object -First 1
    $localWork = 'C:\AeroOneWork'
    New-Item -ItemType Directory -Path $localWork -Force | Out-Null
    Expand-Archive -LiteralPath $packageZip.FullName -DestinationPath $localWork -Force
    $stageRoot = Join-Path $localWork 'AeroOne'
    $manifestPath = Join-Path $PackageDir 'manifest.json'
    Test-ManifestIntegrity -StageRoot $stageRoot -ManifestPath $manifestPath
    Set-StepResult -Name 'verify_manifest' -Ok $true

    # --- 2. Python silent install ------------------------------------------
    $CurrentStep = 'install_python'
    $pythonInstaller = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'offline_assets\installers') -Filter 'python-*.exe' | Select-Object -First 1
    $pythonProc = Start-Process -FilePath $pythonInstaller.FullName -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0' -Wait -PassThru
    if ($pythonProc.ExitCode -eq 3010) { throw 'python-installer-reboot-required' }
    if ($pythonProc.ExitCode -ne 0) { throw "python-installer-exit-$($pythonProc.ExitCode)" }
    Set-StepResult -Name 'install_python' -Ok $true

    # --- 3. Node silent install ---------------------------------------------
    $CurrentStep = 'install_node'
    $nodeInstaller = Get-ChildItem -LiteralPath (Join-Path $stageRoot 'offline_assets\installers') -Filter 'node-*.msi' | Select-Object -First 1
    $nodeProc = Start-Process -FilePath 'msiexec.exe' -ArgumentList '/i', "`"$($nodeInstaller.FullName)`"", '/quiet', '/norestart' -Wait -PassThru
    if ($nodeProc.ExitCode -eq 3010) { throw 'node-installer-reboot-required' }
    if ($nodeProc.ExitCode -ne 0) { throw "node-installer-exit-$($nodeProc.ExitCode)" }
    Set-StepResult -Name 'install_node' -Ok $true

    # --- 4. PATH refresh -----------------------------------------------------
    $CurrentStep = 'refresh_path'
    $machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
    Set-StepResult -Name 'refresh_path' -Ok $true

    # --- 5. Exact version assertions ------------------------------------------
    $CurrentStep = 'assert_versions'
    $pythonVersion = (& python --version 2>&1).ToString().Trim()
    if ($pythonVersion -ne $ExpectedPythonVersion) { throw "python-version-mismatch:$pythonVersion" }
    $nodeVersion = (& node --version 2>&1).ToString().Trim()
    if ($nodeVersion -ne $ExpectedNodeVersion) { throw "node-version-mismatch:$nodeVersion" }
    $npmVersion = (& npm --version 2>&1).ToString().Trim()
    if (-not $npmVersion) { throw 'npm-not-available' }
    Set-StepResult -Name 'assert_versions' -Ok $true -Detail "python=$pythonVersion node=$nodeVersion npm=$npmVersion"

    # --- 6. Unattended setup/start/health/frontend/login/empty-NSA/stop -----
    Push-Location $stageRoot
    try {
        $CurrentStep = 'setup_offline'
        & cmd.exe /c 'setup_offline.bat --no-pause --local'
        if ($LASTEXITCODE -ne 0) { throw "setup-offline-exit-$LASTEXITCODE" }
        Set-StepResult -Name 'setup_offline' -Ok $true

        $CurrentStep = 'start_offline'
        & cmd.exe /c 'start_offline.bat --no-pause --local'
        if ($LASTEXITCODE -ne 0) { throw "start-offline-exit-$LASTEXITCODE" }
        Set-StepResult -Name 'start_offline' -Ok $true

        $CurrentStep = 'health_check'
        Start-Sleep -Seconds 5
        $health = Invoke-WebRequest -Uri 'http://127.0.0.1:18437/api/health' -UseBasicParsing -TimeoutSec 30
        if ($health.StatusCode -ne 200) { throw "health-check-status-$($health.StatusCode)" }
        Set-StepResult -Name 'health_check' -Ok $true

        $CurrentStep = 'frontend_reachable'
        $frontend = Invoke-WebRequest -Uri 'http://127.0.0.1:3000/' -UseBasicParsing -TimeoutSec 30
        if ($frontend.StatusCode -ne 200) { throw "frontend-check-status-$($frontend.StatusCode)" }
        Set-StepResult -Name 'frontend_reachable' -Ok $true

        $CurrentStep = 'login_flow'
        $login = Invoke-WebRequest -Uri 'http://127.0.0.1:18437/api/auth/login' -Method Post -UseBasicParsing -TimeoutSec 30 -ContentType 'application/json' -Body '{}'
        if ($login.StatusCode -ge 500) { throw "login-check-status-$($login.StatusCode)" }
        Set-StepResult -Name 'login_flow' -Ok $true

        $CurrentStep = 'empty_nsa'
        $nsaDataRoot = Join-Path $stageRoot '_database\nsa'
        $nsaHasContent = (Test-Path -LiteralPath $nsaDataRoot) -and ((Get-ChildItem -LiteralPath $nsaDataRoot -Recurse -File -ErrorAction SilentlyContinue).Count -gt 0)
        if ($nsaHasContent) { throw 'nsa-root-not-empty-by-default' }
        Set-StepResult -Name 'empty_nsa' -Ok $true

        $CurrentStep = 'stop_all'
        & cmd.exe /c 'scripts\stop_all.bat'
        if ($LASTEXITCODE -ne 0) { throw "stop-all-exit-$LASTEXITCODE" }
        Set-StepResult -Name 'stop_all' -Ok $true
    }
    finally {
        Pop-Location
    }
}
catch {
    Set-StepResult -Name $CurrentStep -Ok $false -Detail $_.Exception.Message
}
finally {
    Write-Receipt
}
