Set-StrictMode -Version Latest

function Resolve-VersionedRecoveryPath {
    param([Parameter(Mandatory = $true)][string]$RecoveryDirectory)

    $candidates = @(Get-ChildItem -LiteralPath $RecoveryDirectory -File -Force)
    if ($candidates.Count -ne 1 -or
        $candidates[0].Name -notmatch '^aeroone-db-before-rotation\.[a-f0-9-]{36}\.dpapi$') {
        throw 'unexpected-secure-output'
    }
    return [IO.Path]::GetFullPath($candidates[0].FullName)
}

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
    $recoveryPath = Resolve-VersionedRecoveryPath -RecoveryDirectory $Context.RecoveryDirectory
    Assert-SecureDirectoryInventory -Path $Context.SecureRoot -AllowedNames @(
        'recovery', 'pending', 'quarantine', 'bootstrap-marker.json.dpapi',
        'rotation-state.json.dpapi', 'rotation-state.previous.json.dpapi',
        'credentials.dpapi'
    )
    Assert-SecureDirectoryInventory `
        -Path $Context.RecoveryDirectory `
        -AllowedNames @((Split-Path -Leaf $recoveryPath))
    Assert-SecureDirectoryInventory -Path $Context.PendingDirectory -AllowedNames @(
        'credentials.dpapi', 'root-env.dpapi', 'backend-env.dpapi'
    )
    Assert-SecureDirectoryInventory -Path $Context.QuarantineDirectory -AllowedNames @(
        'environment', 'quarantine-manifest.json', 'quarantine-manifest.json.previous'
    )
    Assert-SecureDirectoryInventory -Path $Context.QuarantineEnvDirectory -AllowedNames @(
        'root.env.before-rotation', 'backend.env.before-rotation'
    )
    return $recoveryPath
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

    if ($Journal.root_environment_present -and
        $Context.PhaseOrder[$Phase] -lt $Context.PhaseOrder['root_env_promoted']) {
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
        $activeIdentity = Assert-SinglePhysicalFile -Path $Repair.ActivePath
        $workspaceIdentity = Get-PhysicalPathIdentity -Path $Repair.Workspace
        Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $activeIdentity
        Assert-SecureAcl -Path $Repair.ActivePath
        $actualDigest = Get-FileSha256 -Path $Repair.ActivePath
        $oldDigest = [string]$Journal.($Repair.BeforeSha256Field)
        $newDigest = [string]$Journal.($Repair.AfterSha256Field)
        if ($Repair.PhaseOrder[$Phase] -ge $Repair.PhaseOrder[$Repair.NewPhase]) {
            if ($actualDigest -cne $newDigest) {
                throw $Repair.AmbiguousCode
            }
            return [PSCustomObject]@{ journal = $Journal; phase = $Phase }
        }
        if ($actualDigest -ceq $oldDigest) {
            return [PSCustomObject]@{ journal = $Journal; phase = $Phase }
        }
        if ($Phase -cne $Repair.ExpectedPhase) {
            throw $Repair.AmbiguousCode
        }
        if ($actualDigest -cne $newDigest -or
            -not (Test-Path -LiteralPath $Repair.QuarantinePath -PathType Leaf)) {
            throw $Repair.AmbiguousCode
        }
        $null = Assert-SinglePhysicalFile -Path $Repair.QuarantinePath
        Assert-SecureAcl -Path $Repair.QuarantinePath
        Assert-FileSha256 -Path $Repair.QuarantinePath -Expected $oldDigest
        $Journal = Write-JournalPhase -Journal $Journal -Phase $Repair.NewPhase -JournalPath $Repair.JournalPath -PreviousPath $Repair.JournalPreviousPath -WorkspaceRoot $Repair.Workspace
        return [PSCustomObject]@{ journal = $Journal; phase = $Repair.NewPhase }
    }
    if ($Phase -cne $Repair.ExpectedPhase -or
        -not (Test-Path -LiteralPath $Repair.QuarantinePath -PathType Leaf)) {
        throw $Repair.AmbiguousCode
    }
    $null = Assert-SinglePhysicalFile -Path $Repair.QuarantinePath
    $expectedDigest = [string]$Journal.($Repair.BeforeSha256Field)
    Assert-SecureAcl -Path $Repair.QuarantinePath
    Assert-FileSha256 -Path $Repair.QuarantinePath -Expected $expectedDigest
    Copy-EnvironmentToQuarantine `
        -SourcePath $Repair.ActivePath `
        -SourceLabel $Repair.SourceLabel `
        -DestinationPath $Repair.QuarantinePath `
        -ManifestPath $Repair.ManifestPath `
        -RotationId ([string]$Journal.rotation_id) `
        -DatabaseId ([string]$Journal.database_id)
    Promote-ProtectedEnvironment -PendingPath $Repair.PendingPath -DestinationPath $Repair.ActivePath -Purpose $Repair.Purpose
    $Journal = Write-JournalPhase -Journal $Journal -Phase $Repair.NewPhase -JournalPath $Repair.JournalPath -PreviousPath $Repair.JournalPreviousPath -WorkspaceRoot $Repair.Workspace
    return [PSCustomObject]@{ journal = $Journal; phase = $Repair.NewPhase }
}

function Invoke-RotationReconciliation {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    $inventoryRecoveryPath = Initialize-RotationResumeTree -Context $Context
    $journal = Read-RotationJournal -CurrentPath $Context.JournalPath -PreviousPath $Context.JournalPreviousPath -WorkspaceRoot $Context.Workspace
    if ($journal.retention -cne $Context.Retention -or
        -not $Context.PhaseOrder.ContainsKey([string]$journal.phase)) {
        throw 'journal-invalid'
    }
    $phase = [string]$journal.phase
    if (-not $journal.root_environment_present -and $Context.RootEnvironmentPresent) {
        throw 'env-topology-changed'
    }
    $recoveryPath = Join-Path `
        $Context.RecoveryDirectory `
        ("aeroone-db-before-rotation.$([string]$journal.rotation_id).dpapi")
    if (-not ([IO.Path]::GetFullPath($recoveryPath)).Equals(
        $inventoryRecoveryPath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'journal-binding-mismatch'
    }
    $plaintextTempParents = @()
    if ($journal.root_environment_present -and $phase -ceq 'db_committed' -and
        -not (Test-Path -LiteralPath $Context.RootRepair.ActivePath -PathType Leaf)) {
        $plaintextTempParents += $Context.Workspace
    }
    if ($phase -ceq 'root_env_promoted' -and
        -not (Test-Path -LiteralPath $Context.BackendRepair.ActivePath -PathType Leaf)) {
        $plaintextTempParents += (Split-Path -Parent $Context.BackendRepair.ActivePath)
    }
    if ($plaintextTempParents.Count -gt 0) {
        Remove-RotationPlaintextOrphanTemps -Directories $plaintextTempParents
    }
    Assert-SecureAcl -Path $recoveryPath
    Assert-FileSha256 -Path $recoveryPath -Expected ([string]$journal.recovery_sha256)
    $resolved = Resolve-RotationResumeBundle -Journal $journal -Phase $phase -Context $Context
    $journal = $resolved.journal
    $phase = $resolved.phase
    Assert-RotationPendingEnvironments -Journal $journal -Phase $phase -Context $Context
    if ($journal.root_environment_present) {
        $root = Repair-MissingRotationEnvironment -Journal $journal -Phase $phase -Repair $Context.RootRepair
    } else {
        if ((Test-Path -LiteralPath $Context.RootRepair.ActivePath) -or
            (Test-Path -LiteralPath $Context.RootRepair.PendingPath) -or
            (Test-Path -LiteralPath $Context.RootRepair.QuarantinePath)) {
            throw 'root-env-state-ambiguous'
        }
        $root = [PSCustomObject]@{ journal = $journal; phase = $phase }
    }
    $backend = Repair-MissingRotationEnvironment `
        -Journal $root.journal `
        -Phase $root.phase `
        -Repair $Context.BackendRepair
    return [PSCustomObject]@{
        journal = $backend.journal
        phase = $backend.phase
        recovery_path = $recoveryPath
    }
}

Export-ModuleMember -Function @(
    'Initialize-RotationResumeTree',
    'Invoke-RotationReconciliation',
    'Resolve-VersionedRecoveryPath'
)
