Set-StrictMode -Version Latest

function Assert-RotationArchiveBindings {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    if ([string]$Context.Journal.phase -cne 'complete') {
        throw 'restore-completed-state-required'
    }
    $manifest = Read-ValidatedQuarantineManifest `
        -Path $Context.QuarantineManifestPath `
        -RotationId ([string]$Context.Journal.rotation_id) `
        -DatabaseId ([string]$Context.Journal.database_id)
    $expectedManifestEntries = if ($Context.Journal.root_environment_present) { 2 } else { 1 }
    if ($manifest.retention -cne $Context.Retention -or
        @($manifest.entries).Count -ne $expectedManifestEntries) {
        throw 'quarantine-manifest-mismatch'
    }
    if ($Context.Journal.root_environment_present) {
        Assert-FileSha256 `
            -Path $Context.QuarantineRootEnvPath `
            -Expected ([string]$Context.Journal.root_before_sha256)
    } elseif (Test-Path -LiteralPath $Context.QuarantineRootEnvPath) {
        throw 'root-env-state-ambiguous'
    }
    Assert-FileSha256 -Path $Context.QuarantineBackendEnvPath -Expected ([string]$Context.Journal.backend_before_sha256)
}

function Initialize-RotationHistoryRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-RotationSecureDirectory -Path $Path
    }
    $identity = Get-PhysicalPathIdentity -Path $Path
    if (-not $identity.IsDirectory) {
        throw 'secure-directory-invalid'
    }
    Assert-SecureAcl -Path $Path
    return $identity
}

function Assert-RotationHistoryInventory {
    param([Parameter(Mandatory = $true)][string]$Path)

    foreach ($archive in @(Get-ChildItem -LiteralPath $Path -Force)) {
        if (-not $archive.PSIsContainer -or
            $archive.Name -notmatch '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$') {
            throw 'history-inventory-invalid'
        }
        $identity = Get-PhysicalPathIdentity -Path $archive.FullName
        if (-not $identity.IsDirectory) {
            throw 'history-inventory-invalid'
        }
        Assert-SecureAcl -Path $archive.FullName
    }
}

function Invoke-RotationArchive {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    Assert-RotationArchiveBindings -Context $Context
    $guardPython = if ($Context.TestMode) {
        [IO.Path]::GetFullPath([string]$Context.PythonOverride)
    } else {
        Join-Path $Context.Workspace 'backend\.venv\Scripts\python.exe'
    }
    $guard = Start-RotationRestoreGuard `
        -PythonPath $guardPython `
        -WorkingDirectory (Join-Path $Context.ProductRoot 'backend') `
        -Request @{
            action = 'begin_restore_guard'
            database_path = $Context.DatabasePath
            recovery_path = $Context.RecoveryPath
            rotation_id = [string]$Context.Journal.rotation_id
            database_id = [string]$Context.Journal.database_id
            recovery_sha256 = [string]$Context.Journal.recovery_sha256
        }
    try {
        if ($Context.InternalDatabaseBarrier -ceq 'hold_after_restore_confirmation') {
            Invoke-TestDatabaseBarrier `
                -WorkspaceRoot $Context.Workspace `
                -Barrier $Context.InternalDatabaseBarrier
        }
        $historyIdentity = Initialize-RotationHistoryRoot -Path $Context.HistoryRoot
        Assert-RotationHistoryInventory -Path $Context.HistoryRoot
        $historyTarget = Join-Path $Context.HistoryRoot ([string]$Context.Journal.rotation_id)
        if (Test-Path -LiteralPath $historyTarget) {
            throw 'history-destination-exists'
        }
        $secureRootIdentity = Get-PhysicalPathIdentity -Path $Context.SecureRoot
        if ($secureRootIdentity.VolumeSerialNumber -ne $historyIdentity.VolumeSerialNumber) {
            throw 'history-volume-mismatch'
        }
        [IO.Directory]::Move($Context.SecureRoot, $historyTarget)
        $archiveIdentity = Get-PhysicalPathIdentity -Path $historyTarget
        Assert-PhysicalContainment -RootIdentity $historyIdentity -ChildIdentity $archiveIdentity
        Assert-SecureAcl -Path $historyTarget
        Complete-RotationRestoreGuard -Guard $guard
        $guard = $null
        [Console]::Out.WriteLine(
            "status=archived rotation_id=$($Context.Journal.rotation_id) retention=$($Context.Retention)"
        )
    } finally {
        Stop-RotationRestoreGuard -Guard $guard
    }
}

Export-ModuleMember -Function 'Invoke-RotationArchive'
