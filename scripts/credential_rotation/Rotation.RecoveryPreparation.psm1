Set-StrictMode -Version Latest

function New-RotationReconciliationContext {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    return @{
        Workspace = $Context.Workspace
        Retention = $Context.Retention
        PhaseOrder = $Context.PhaseOrder
        SecureRoot = $Context.SecureRoot
        RecoveryDirectory = $Context.RecoveryDirectory
        PendingDirectory = $Context.PendingDirectory
        QuarantineDirectory = $Context.QuarantineDirectory
        QuarantineEnvDirectory = $Context.QuarantineEnvDirectory
        BootstrapMarkerPath = $Context.BootstrapMarkerPath
        JournalPath = $Context.JournalPath
        JournalPreviousPath = $Context.JournalPreviousPath
        PendingCredentialPath = $Context.PendingCredentialPath
        FinalCredentialPath = $Context.FinalCredentialPath
        PendingRootEnvPath = $Context.PendingRootEnvPath
        PendingBackendEnvPath = $Context.PendingBackendEnvPath
        RootEnvironmentPresent = [bool]$Context.RootEnvironmentPresent
        RootRepair = @{
            ActivePath = $Context.RootEnvPath
            QuarantinePath = $Context.QuarantineRootEnvPath
            PendingPath = $Context.PendingRootEnvPath
            ManifestPath = $Context.QuarantineManifestPath
            SourceLabel = '.env'
            Purpose = 'pending-root-environment'
            ExpectedPhase = 'db_committed'
            NewPhase = 'root_env_promoted'
            AmbiguousCode = 'root-env-state-ambiguous'
            BeforeSha256Field = 'root_before_sha256'
            AfterSha256Field = 'root_after_sha256'
            PhaseOrder = $Context.PhaseOrder
            JournalPath = $Context.JournalPath
            JournalPreviousPath = $Context.JournalPreviousPath
            Workspace = $Context.Workspace
        }
        BackendRepair = @{
            ActivePath = $Context.BackendEnvPath
            QuarantinePath = $Context.QuarantineBackendEnvPath
            PendingPath = $Context.PendingBackendEnvPath
            ManifestPath = $Context.QuarantineManifestPath
            SourceLabel = 'backend/.env'
            Purpose = 'pending-backend-environment'
            ExpectedPhase = 'root_env_promoted'
            NewPhase = 'backend_env_promoted'
            AmbiguousCode = 'backend-env-state-ambiguous'
            BeforeSha256Field = 'backend_before_sha256'
            AfterSha256Field = 'backend_after_sha256'
            PhaseOrder = $Context.PhaseOrder
            JournalPath = $Context.JournalPath
            JournalPreviousPath = $Context.JournalPreviousPath
            Workspace = $Context.Workspace
        }
    }
}

function Start-RotationPreparedTransaction {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [Parameter(Mandatory = $true)]$Prepared,
        [Parameter(Mandatory = $true)]$Bundle
    )

    $recoveryPath = Join-Path `
        $Context.RecoveryDirectory `
        ("aeroone-db-before-rotation.$([string]$Bundle.rotation_id).dpapi")
    if (Test-Path -LiteralPath $recoveryPath) {
        throw 'recovery-destination-exists'
    }
    $recoveryTemporaryPath = Join-Path `
        $Context.RecoveryDirectory `
        ('.aeroone-rotation-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    Publish-RotationSecureBytes `
        -Bytes (New-Object byte[] 0) `
        -DestinationPath $recoveryTemporaryPath
    $transactionPython = if ($Context.TestMode) {
        [IO.Path]::GetFullPath([string]$Context.PythonOverride)
    } else {
        Join-Path $Context.Workspace 'backend\.venv\Scripts\python.exe'
    }
    $transaction = Start-RotationDatabaseTransaction `
        -PythonPath $transactionPython `
        -WorkingDirectory (Join-Path $Context.ProductRoot 'backend') `
        -Request @{
            action = 'begin'
            database_url = $Context.DatabaseUrl
            bundle_path = $Context.PendingCredentialPath
            recovery_path = $recoveryTemporaryPath
            reuse_recovery = $false
            fail_before_commit = ($Context.Failpoint -ceq 'before_db_commit')
        }
    if ([int]$transaction.ready.user_count_before -ne [int]$Prepared.user_count_before) {
        throw 'prepare-drift-detected'
    }
    Set-SecureFileAcl -Path $recoveryTemporaryPath
    Assert-SecureAcl -Path $recoveryTemporaryPath
    Assert-FileSha256 `
        -Path $recoveryTemporaryPath `
        -Expected ([string]$transaction.ready.recovery_sha256)
    Complete-RotationSecurePublish `
        -TemporaryPath $recoveryTemporaryPath `
        -DestinationPath $recoveryPath `
        -BackupPath ''
    Assert-FileSha256 -Path $recoveryPath -Expected ([string]$transaction.ready.recovery_sha256)
    Invoke-TestCrashpoint -Expected 'crash_after_recovery_publish'
    $pendingRootSha256 = if ($Context.RootEnvironmentPresent) {
        Get-FileSha256 -Path $Context.PendingRootEnvPath
    } else {
        $null
    }
    $rootBeforeSha256 = if ($Context.RootEnvironmentPresent) {
        Get-FileSha256 -Path $Context.RootEnvPath
    } else {
        $null
    }
    $rootAfterSha256 = if ($Context.RootEnvironmentPresent) {
        Get-ProtectedPayloadSha256 `
            -Path $Context.PendingRootEnvPath `
            -Purpose 'pending-root-environment'
    } else {
        $null
    }
    $sealed = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'journal_seal'
        journal = @{
            schema_version = 2
            sequence = 0
            phase = 'prepared'
            root_environment_present = [bool]$Context.RootEnvironmentPresent
            rotation_id = [string]$Bundle.rotation_id
            database_id = [string]$Bundle.database_id
            user_count = [int]$Prepared.user_count_before
            retention = $Context.Retention
            bundle_sha256 = Get-FileSha256 -Path $Context.PendingCredentialPath
            recovery_sha256 = [string]$transaction.ready.recovery_sha256
            pending_root_sha256 = $pendingRootSha256
            pending_backend_sha256 = Get-FileSha256 -Path $Context.PendingBackendEnvPath
            root_before_sha256 = $rootBeforeSha256
            backend_before_sha256 = Get-FileSha256 -Path $Context.BackendEnvPath
            root_after_sha256 = $rootAfterSha256
            backend_after_sha256 = Get-ProtectedPayloadSha256 `
                -Path $Context.PendingBackendEnvPath `
                -Purpose 'pending-backend-environment'
        }
    }
    return [PSCustomObject]@{
        Journal = $sealed.journal
        Transaction = $transaction
        RecoveryPath = $recoveryPath
    }
}

Export-ModuleMember -Function @(
    'New-RotationReconciliationContext',
    'Start-RotationPreparedTransaction'
)
