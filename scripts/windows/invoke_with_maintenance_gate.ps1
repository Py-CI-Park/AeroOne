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

# Exit-code contract consumed by setup_offline.bat / start_offline.bat:
#   0..N  the wrapped batch's own exit code (gate acquired, batch ran).
#   97    maintenance gate UNAVAILABLE because THIS host cannot host the gate:
#         no SeCreateGlobalPrivilege for a Global\ mutex (common on locked-down
#         closed-network standard accounts), or a reparse point in the install
#         path. On such a host no other process can hold the gate either, so a
#         caller may fall back to a direct, non-serialized preflight.
#   98    maintenance gate CONTENDED: another maintenance op (e.g. credential
#         rotation) held it past the wait timeout. Callers MUST NOT bypass.
$gateUnavailableExit = 97
$gateContendedExit = 98
$envIncapableReasons = @('reparse-forbidden', 'mutex-create-denied', 'mutex-security-invalid')

$moduleRoot = Join-Path $PSScriptRoot '..\credential_rotation'
$gate = $null
try {
    Import-Module (Join-Path $moduleRoot 'Rotation.PathSecurity.psm1') -Force -DisableNameChecking
    Import-Module (Join-Path $moduleRoot 'Rotation.ProcessLock.psm1') -Force -DisableNameChecking

    $workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $batchIdentity = Assert-SinglePhysicalFile -Path $BatchPath
    Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $batchIdentity
    $gate = Enter-AeroOneMaintenanceGate `
        -WorkspaceRoot $WorkspaceRoot `
        -WaitMilliseconds ($WaitTimeoutSeconds * 1000)
} catch {
    $reason = "$($_.Exception.Message)"
    if ($envIncapableReasons -contains $reason) {
        [Console]::Error.WriteLine("status=gate-unavailable reason=$reason")
        exit $gateUnavailableExit
    }
    throw
}
if ($null -eq $gate) {
    [Console]::Error.WriteLine('status=gate-contended reason=maintenance-gate-timeout')
    exit $gateContendedExit
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
