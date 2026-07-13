[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [ValidateRange(1, 600)][int]$WaitTimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$moduleRoot = Join-Path $PSScriptRoot '..\credential_rotation'
Import-Module (Join-Path $moduleRoot 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $moduleRoot 'Rotation.ProcessLock.psm1') -Force -DisableNameChecking

$gate = Enter-AeroOneMaintenanceGate `
    -WorkspaceRoot $WorkspaceRoot `
    -WaitMilliseconds ($WaitTimeoutSeconds * 1000)
if ($null -eq $gate) {
    throw 'maintenance-gate-timeout'
}
try {
    [Console]::Out.WriteLine('status=maintenance-gate-ready')
    $null = [Console]::In.ReadLine()
} finally {
    $gate.ReleaseMutex()
    $gate.Dispose()
}
