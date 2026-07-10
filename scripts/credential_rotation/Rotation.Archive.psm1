Set-StrictMode -Version Latest

function Assert-RotationArchiveBindings {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    if ([string]$Context.Journal.phase -cne 'complete') {
        throw 'restore-completed-state-required'
    }
    Assert-SecureAcl -Path $Context.QuarantineManifestPath
    $manifest = [IO.File]::ReadAllText($Context.QuarantineManifestPath) | ConvertFrom-Json
    if ($manifest.retention -cne $Context.Retention -or @($manifest.entries).Count -ne 2) {
        throw 'quarantine-manifest-mismatch'
    }
    Assert-FileSha256 -Path $Context.QuarantineRootEnvPath -Expected ([string]$Context.Journal.root_before_sha256)
    Assert-FileSha256 -Path $Context.QuarantineBackendEnvPath -Expected ([string]$Context.Journal.backend_before_sha256)
    $null = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'confirm_restore'
        database_path = $Context.DatabasePath
        recovery_path = $Context.RecoveryPath
        rotation_id = [string]$Context.Journal.rotation_id
        database_id = [string]$Context.Journal.database_id
    }
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
    [Console]::Out.WriteLine(
        "status=archived rotation_id=$($Context.Journal.rotation_id) retention=$($Context.Retention)"
    )
}

Export-ModuleMember -Function 'Invoke-RotationArchive'
