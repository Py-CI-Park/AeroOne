#Requires -Version 5.1
<#
  .SYNOPSIS
  Host-side Windows Sandbox launcher for the offline-package smoke test
  (Task 6, AeroOne v1.13.0). Never executed by this task — requires the
  Windows Sandbox optional feature, administrator elevation, and a real
  offline package (npm ci/build + wheelhouse + Task 5 installer binaries)
  none of which are available in this sandbox environment. Written and
  AST-validated only.

  .DESCRIPTION
  Renders ``AeroOnePackageSmoke.wsb.template`` with resolved host folder
  paths (package: read-only; receipt: writable), always with
  ``<Networking>Disable</Networking>`` and no interactive prompt in the
  logon command, launches ``WindowsSandbox.exe``, and polls the mapped
  receipt folder for ``receipt.json`` up to ``-TimeoutMinutes`` (capped at
  20, matching ``validate_sandbox_launch_options`` in the Python policy
  layer). A missing or ``ok: false`` receipt after timeout is a FAIL.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PackageZipPath,
    [Parameter(Mandatory = $true)] [string]$ManifestPath,
    [int]$TimeoutMinutes = 20,
    [string]$WorkDir = (Join-Path $env:TEMP 'AeroOneSandboxSmoke'),
    [string]$WindowsSandboxExecutable = 'WindowsSandbox.exe'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MaxTimeoutMinutes = 20

function Assert-LaunchOptionsAreSafe {
    <#
      .SYNOPSIS
      Fail-closed guard mirroring ``validate_sandbox_launch_options``: the
      harness never exposes a networking-enable switch or an interactive
      pause switch at all (the WSB template hardcodes both to the safe
      value), so the only variable input worth re-checking here is the
      timeout ceiling.
    #>
    param([Parameter(Mandatory = $true)] [int]$TimeoutMinutes)
    if ($TimeoutMinutes -le 0 -or $TimeoutMinutes -gt $MaxTimeoutMinutes) {
        throw "sandbox-timeout-invalid:$TimeoutMinutes"
    }
}

function New-SandboxConfig {
    param(
        [Parameter(Mandatory = $true)] [string]$PackageHostFolder,
        [Parameter(Mandatory = $true)] [string]$ReceiptHostFolder,
        [Parameter(Mandatory = $true)] [string]$OutputWsbPath
    )
    $templatePath = Join-Path $PSScriptRoot 'AeroOnePackageSmoke.wsb.template'
    $template = Get-Content -LiteralPath $templatePath -Raw
    $rendered = $template.
        Replace('{{PACKAGE_HOST_FOLDER}}', $PackageHostFolder).
        Replace('{{RECEIPT_HOST_FOLDER}}', $ReceiptHostFolder)
    Set-Content -LiteralPath $OutputWsbPath -Value $rendered -Encoding utf8
}

function Wait-ForReceipt {
    param(
        [Parameter(Mandatory = $true)] [string]$ReceiptDir,
        [Parameter(Mandatory = $true)] [int]$TimeoutMinutes
    )
    $receiptPath = Join-Path $ReceiptDir 'receipt.json'
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $receiptPath) {
            return Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        }
        Start-Sleep -Seconds 10
    }
    throw 'sandbox-smoke-timeout'
}

Assert-LaunchOptionsAreSafe -TimeoutMinutes $TimeoutMinutes

if (Test-Path -LiteralPath $WorkDir) {
    Remove-Item -LiteralPath $WorkDir -Recurse -Force
}
$packageHostFolder = Join-Path $WorkDir 'package'
$receiptHostFolder = Join-Path $WorkDir 'receipt'
New-Item -ItemType Directory -Path $packageHostFolder -Force | Out-Null
New-Item -ItemType Directory -Path $receiptHostFolder -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packageHostFolder 'sandbox') -Force | Out-Null

Copy-Item -LiteralPath $PackageZipPath -Destination $packageHostFolder -Force
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $packageHostFolder 'manifest.json') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'guest_bootstrap.ps1') -Destination (Join-Path $packageHostFolder 'sandbox') -Force

$wsbPath = Join-Path $WorkDir 'smoke.wsb'
New-SandboxConfig -PackageHostFolder $packageHostFolder -ReceiptHostFolder $receiptHostFolder -OutputWsbPath $wsbPath

Write-Output "[SANDBOX] launching $WindowsSandboxExecutable $wsbPath (networking disabled, timeout ${TimeoutMinutes}m)"
Start-Process -FilePath $WindowsSandboxExecutable -ArgumentList $wsbPath

$receipt = Wait-ForReceipt -ReceiptDir $receiptHostFolder -TimeoutMinutes $TimeoutMinutes

if (-not $receipt.ok) {
    Write-Output "[FAIL] sandbox smoke failed at step '$($receipt.failed_step)'"
    exit 1
}

Write-Output '[OK] sandbox smoke passed: verifier, Python/Node silent installs, unattended setup/start/health/frontend/login/empty-NSA/stop all recorded ok=true'
exit 0
