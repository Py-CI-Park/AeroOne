[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)][string]$BatchPath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$BatchArguments = @(),
    [AllowEmptyString()][string]$RawBatchArguments = '',
    [ValidateRange(1, 600)][int]$WaitTimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$moduleRoot = Join-Path $PSScriptRoot '..\credential_rotation'
Import-Module (Join-Path $moduleRoot 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $moduleRoot 'Rotation.ProcessLock.psm1') -Force -DisableNameChecking

$workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
$batchIdentity = Assert-SinglePhysicalFile -Path $BatchPath
Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $batchIdentity
$gate = Enter-AeroOneMaintenanceGate `
    -WorkspaceRoot $WorkspaceRoot `
    -WaitMilliseconds ($WaitTimeoutSeconds * 1000)
if ($null -eq $gate) {
    throw 'maintenance-gate-timeout'
}
try {
    $env:AEROONE_MAINTENANCE_GATE_HELD = '1'
    if ([string]::IsNullOrWhiteSpace($RawBatchArguments)) {
        & $BatchPath @BatchArguments
    } else {
        $commandLine = 'call "' + $BatchPath.Replace('"', '""') + '" ' + $RawBatchArguments
        & $env:ComSpec /d /s /c $commandLine
    }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = if ($?) { 0 } else { 1 }
    }
    exit $exitCode
} finally {
    Remove-Item Env:AEROONE_MAINTENANCE_GATE_HELD -ErrorAction SilentlyContinue
    $gate.ReleaseMutex()
    $gate.Dispose()
}
