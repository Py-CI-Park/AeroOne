Set-StrictMode -Version Latest

function Initialize-RotationResumeTree {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    Initialize-SecureDirectory -Path $Context.SecureRoot -Resume $true
    $directories = @(
        $Context.RecoveryDirectory,
        $Context.PendingDirectory,
        $Context.QuarantineDirectory,
        $Context.QuarantineEnvDirectory
    )
    foreach ($directory in $directories) {
        Initialize-SecureDirectory -Path $directory -Resume $true
    }
    Remove-RotationOrphanTemps -Directories (@($Context.SecureRoot) + $directories)
    Assert-RotationBootstrapMarker -Path $Context.BootstrapMarkerPath -WorkspaceRoot $Context.Workspace
    Assert-SecureDirectoryInventory -Path $Context.SecureRoot -AllowedNames @(
        'recovery', 'pending', 'quarantine', 'bootstrap-marker.json.dpapi',
        'rotation-state.json.dpapi', 'rotation-state.previous.json.dpapi',
        '1.12.3-credentials.dpapi'
    )
    Assert-SecureDirectoryInventory -Path $Context.RecoveryDirectory -AllowedNames @(
        'aeroone-db-before-rotation.dpapi'
    )
    Assert-SecureDirectoryInventory -Path $Context.PendingDirectory -AllowedNames @(
        'credentials.dpapi', 'root-env.dpapi', 'backend-env.dpapi'
    )
    Assert-SecureDirectoryInventory -Path $Context.QuarantineDirectory -AllowedNames @(
        'environment', 'quarantine-manifest.json', 'quarantine-manifest.json.previous'
    )
    Assert-SecureDirectoryInventory -Path $Context.QuarantineEnvDirectory -AllowedNames @(
        'root.env.before-rotation', 'backend.env.before-rotation'
    )
}

function Resolve-RotationResumeBundle {
    param($Journal, [string]$Phase, [Parameter(Mandatory = $true)][hashtable]$Context)

    $pendingExists = Test-Path -LiteralPath $Context.PendingCredentialPath -PathType Leaf
    $finalExists = Test-Path -LiteralPath $Context.FinalCredentialPath -PathType Leaf
    if ($Context.PhaseOrder[$Phase] -lt $Context.PhaseOrder['credentials_promoted']) {
        if ($pendingExists -and $finalExists) {
            throw 'credential-state-ambiguous'
        }
        if ($pendingExists) {
            $bundlePath = $Context.PendingCredentialPath
        } elseif ($Phase -ceq 'backend_env_promoted' -and $finalExists) {
            $bundlePath = $Context.FinalCredentialPath
            $Journal = Write-JournalPhase -Journal $Journal -Phase 'credentials_promoted' -JournalPath $Context.JournalPath -PreviousPath $Context.JournalPreviousPath -WorkspaceRoot $Context.Workspace
            $Phase = 'credentials_promoted'
        } else {
            throw 'credential-state-ambiguous'
        }
    } else {
        if ($pendingExists -or -not $finalExists) {
            throw 'credential-state-ambiguous'
        }
        $bundlePath = $Context.FinalCredentialPath
    }
    Assert-SecureAcl -Path $bundlePath
    Assert-FileSha256 -Path $bundlePath -Expected ([string]$Journal.bundle_sha256)
    $bundle = Read-CredentialBundle -Path $bundlePath
    if ([string]$bundle.rotation_id -cne [string]$Journal.rotation_id -or
        [string]$bundle.database_id -cne [string]$Journal.database_id) {
        throw 'journal-binding-mismatch'
    }
    return [PSCustomObject]@{ journal = $Journal; phase = $Phase }
}

function Assert-RotationPendingEnvironments {
    param($Journal, [string]$Phase, [Parameter(Mandatory = $true)][hashtable]$Context)

    if ($Context.PhaseOrder[$Phase] -lt $Context.PhaseOrder['root_env_promoted']) {
        Assert-ProtectedBytesReadable -Path $Context.PendingRootEnvPath -Purpose 'pending-root-environment'
        Assert-FileSha256 -Path $Context.PendingRootEnvPath -Expected ([string]$Journal.pending_root_sha256)
    }
    if ($Context.PhaseOrder[$Phase] -lt $Context.PhaseOrder['backend_env_promoted']) {
        Assert-ProtectedBytesReadable -Path $Context.PendingBackendEnvPath -Purpose 'pending-backend-environment'
        Assert-FileSha256 -Path $Context.PendingBackendEnvPath -Expected ([string]$Journal.pending_backend_sha256)
    }
}

function Repair-MissingRotationEnvironment {
    param($Journal, [string]$Phase, [Parameter(Mandatory = $true)][hashtable]$Repair)

    if (Test-Path -LiteralPath $Repair.ActivePath -PathType Leaf) {
        return [PSCustomObject]@{ journal = $Journal; phase = $Phase }
    }
    if ($Phase -cne $Repair.ExpectedPhase -or
        -not (Test-Path -LiteralPath $Repair.QuarantinePath -PathType Leaf)) {
        throw $Repair.AmbiguousCode
    }
    $null = Assert-SinglePhysicalFile -Path $Repair.QuarantinePath
    $expectedDigest = [string]$Journal.($Repair.BeforeSha256Field)
    Assert-FileSha256 -Path $Repair.QuarantinePath -Expected $expectedDigest
    Set-SecureFileAcl -Path $Repair.QuarantinePath
    Copy-EnvironmentToQuarantine -SourcePath $Repair.ActivePath -SourceLabel $Repair.SourceLabel -DestinationPath $Repair.QuarantinePath -ManifestPath $Repair.ManifestPath
    Promote-ProtectedEnvironment -PendingPath $Repair.PendingPath -DestinationPath $Repair.ActivePath -Purpose $Repair.Purpose
    $Journal = Write-JournalPhase -Journal $Journal -Phase $Repair.NewPhase -JournalPath $Repair.JournalPath -PreviousPath $Repair.JournalPreviousPath -WorkspaceRoot $Repair.Workspace
    return [PSCustomObject]@{ journal = $Journal; phase = $Repair.NewPhase }
}

function Invoke-RotationReconciliation {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    Initialize-RotationResumeTree -Context $Context
    $journal = Read-RotationJournal -CurrentPath $Context.JournalPath -PreviousPath $Context.JournalPreviousPath -WorkspaceRoot $Context.Workspace
    if ($journal.retention -cne $Context.Retention -or
        -not $Context.PhaseOrder.ContainsKey([string]$journal.phase)) {
        throw 'journal-invalid'
    }
    Assert-SecureAcl -Path $Context.RecoveryPath
    Assert-FileSha256 -Path $Context.RecoveryPath -Expected ([string]$journal.recovery_sha256)
    $resolved = Resolve-RotationResumeBundle -Journal $journal -Phase ([string]$journal.phase) -Context $Context
    $journal = $resolved.journal
    $phase = $resolved.phase
    Assert-RotationPendingEnvironments -Journal $journal -Phase $phase -Context $Context
    $root = Repair-MissingRotationEnvironment -Journal $journal -Phase $phase -Repair $Context.RootRepair
    $backend = Repair-MissingRotationEnvironment -Journal $root.journal -Phase $root.phase -Repair $Context.BackendRepair
    return [PSCustomObject]@{ journal = $backend.journal; phase = $backend.phase }
}

Export-ModuleMember -Function 'Invoke-RotationReconciliation'
