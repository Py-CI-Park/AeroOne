Set-StrictMode -Version Latest

function Restart-RotationPreparedTransaction {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [Parameter(Mandatory = $true)]$Journal
    )

    Assert-SecureAcl -Path $Context.RecoveryPath
    Assert-FileSha256 -Path $Context.RecoveryPath -Expected ([string]$Journal.recovery_sha256)
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
            recovery_path = $Context.RecoveryPath
            recovery_sha256 = [string]$Journal.recovery_sha256
            reuse_recovery = $true
            fail_before_commit = ($Context.Failpoint -ceq 'before_db_commit')
        }
    if ([int]$transaction.ready.user_count_before -ne [int]$Journal.user_count) {
        throw 'prepare-drift-detected'
    }
    Assert-SecureAcl -Path $Context.RecoveryPath
    Assert-FileSha256 -Path $Context.RecoveryPath -Expected ([string]$Journal.recovery_sha256)
    return [PSCustomObject]@{ Journal = $Journal; Transaction = $transaction }
}

function Invoke-RotationStateMachine {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [Parameter(Mandatory = $true)][ref]$Stage,
        [Parameter(Mandatory = $true)][ref]$Transaction
    )

    $journal = $Context.Journal
    $environmentBindings = $Context.EnvironmentBindings
    if (-not [string]::IsNullOrWhiteSpace($Context.RestoreConfirmation)) {
        Invoke-RotationArchive -Context @{
            Journal = $journal
            Retention = $Context.Retention
            Workspace = $Context.Workspace
            DatabasePath = $Context.DatabasePath
            RecoveryPath = $Context.RecoveryPath
            SecureRoot = $Context.SecureRoot
            HistoryRoot = $Context.HistoryRoot
            QuarantineManifestPath = $Context.QuarantineManifestPath
            QuarantineRootEnvPath = $Context.QuarantineRootEnvPath
            QuarantineBackendEnvPath = $Context.QuarantineBackendEnvPath
            InternalDatabaseBarrier = $Context.InternalDatabaseBarrier
            ProductRoot = $Context.ProductRoot
            TestMode = $Context.TestMode
            PythonOverride = $Context.PythonOverride
        }
        return [PSCustomObject]@{ Archived = $true; Journal = $journal }
    }
    $phase = [string]$journal.phase
    if ($Context.PhaseOrder[$phase] -lt $Context.PhaseOrder['db_committed']) {
        $Stage.Value = 'db_commit'
        $environmentBindings = Assert-LiveEnvironmentBindings `
            -Expected $environmentBindings `
            -RootEnvironmentPath $Context.RootEnvPath `
            -BackendEnvironmentPath $Context.BackendEnvPath
        Assert-SecureAcl -Path $Context.PendingCredentialPath
        if ($null -eq $Transaction.Value) {
            $restarted = Restart-RotationPreparedTransaction -Context $Context -Journal $journal
            $journal = $restarted.Journal
            $Transaction.Value = $restarted.Transaction
        }
        try {
            Invoke-TestDatabaseBarrier `
                -WorkspaceRoot $Context.Workspace `
                -Barrier $Context.InternalDatabaseBarrier
            $committed = Complete-RotationDatabaseTransaction -Transaction $Transaction.Value
        } finally {
            $Transaction.Value = $null
        }
        Invoke-TestCrashpoint -Expected 'crash_after_database_commit'
        if ([int]$committed.user_count_after -ne [int]$journal.user_count -or
            [int]$committed.password_count_changed -ne [int]$journal.user_count) {
            throw 'database-commit-count-mismatch'
        }
        $journal = Write-JournalPhase `
            -Journal $journal `
            -Phase 'db_committed' `
            -JournalPath $Context.JournalPath `
            -PreviousPath $Context.JournalPreviousPath `
            -WorkspaceRoot $Context.Workspace
        $phase = 'db_committed'
    }
    Invoke-TestFailpoint -Expected 'after_db_commit'
    if ($Context.PhaseOrder[$phase] -lt $Context.PhaseOrder['root_env_promoted']) {
        $Stage.Value = 'root_env_promote'
        if ($Context.RootEnvironmentPresent) {
            Copy-EnvironmentToQuarantine `
                -SourcePath $Context.RootEnvPath `
                -SourceLabel '.env' `
                -DestinationPath $Context.QuarantineRootEnvPath `
                -ManifestPath $Context.QuarantineManifestPath `
                -RotationId ([string]$journal.rotation_id) `
                -DatabaseId ([string]$journal.database_id)
            Promote-ProtectedEnvironment `
                -PendingPath $Context.PendingRootEnvPath `
                -DestinationPath $Context.RootEnvPath `
                -Purpose 'pending-root-environment' `
                -CrashAfterPartialWrite:($Context.InternalCrashpoint -ceq 'crash_during_root_env_temp_write')
            Invoke-TestCrashpoint -Expected 'crash_after_root_env_publish'
        }
        $journal = Write-JournalPhase `
            -Journal $journal `
            -Phase 'root_env_promoted' `
            -JournalPath $Context.JournalPath `
            -PreviousPath $Context.JournalPreviousPath `
            -WorkspaceRoot $Context.Workspace
        $phase = 'root_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'after_root_env_promote'
    if ($Context.PhaseOrder[$phase] -lt $Context.PhaseOrder['backend_env_promoted']) {
        $Stage.Value = 'backend_env_quarantine'
        Copy-EnvironmentToQuarantine `
            -SourcePath $Context.BackendEnvPath `
            -SourceLabel 'backend/.env' `
            -DestinationPath $Context.QuarantineBackendEnvPath `
            -ManifestPath $Context.QuarantineManifestPath `
            -RotationId ([string]$journal.rotation_id) `
            -DatabaseId ([string]$journal.database_id)
        $Stage.Value = 'backend_env_write'
        Promote-ProtectedEnvironment `
            -PendingPath $Context.PendingBackendEnvPath `
            -DestinationPath $Context.BackendEnvPath `
            -Purpose 'pending-backend-environment'
        Invoke-TestCrashpoint -Expected 'crash_after_backend_env_publish'
        $Stage.Value = 'backend_env_journal'
        $journal = Write-JournalPhase `
            -Journal $journal `
            -Phase 'backend_env_promoted' `
            -JournalPath $Context.JournalPath `
            -PreviousPath $Context.JournalPreviousPath `
            -WorkspaceRoot $Context.Workspace
        $phase = 'backend_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'before_credentials_promote'
    if ($Context.PhaseOrder[$phase] -lt $Context.PhaseOrder['credentials_promoted']) {
        $Stage.Value = 'credentials_promote'
        if (Test-Path -LiteralPath $Context.FinalCredentialPath) {
            throw 'credential-destination-exists'
        }
        Move-Item -LiteralPath $Context.PendingCredentialPath -Destination $Context.FinalCredentialPath
        Set-SecureFileAcl -Path $Context.FinalCredentialPath
        Assert-SecureAcl -Path $Context.FinalCredentialPath
        Invoke-TestCrashpoint -Expected 'crash_after_credentials_move'
        $journal = Write-JournalPhase `
            -Journal $journal `
            -Phase 'credentials_promoted' `
            -JournalPath $Context.JournalPath `
            -PreviousPath $Context.JournalPreviousPath `
            -WorkspaceRoot $Context.Workspace
        $phase = 'credentials_promoted'
    }
    $Stage.Value = 'verify'
    $finalBundle = Read-CredentialBundle -Path $Context.FinalCredentialPath
    $finalAdminCredential = Get-AdminCredential -Bundle $finalBundle
    $finalBackendEnv = Read-ExactEnv -Path $Context.BackendEnvPath -Profile 'backend'
    if ($finalBackendEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key) {
        throw 'jwt-promotion-mismatch'
    }
    if ($finalBackendEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password) {
        throw 'admin-promotion-mismatch'
    }
    if ($Context.RootEnvironmentPresent) {
        $finalRootEnv = Read-ExactEnv -Path $Context.RootEnvPath -Profile 'root'
        if ($finalRootEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key) {
            throw 'jwt-promotion-mismatch'
        }
        if ($finalRootEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password) {
            throw 'admin-promotion-mismatch'
        }
    }
    $verified = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'verify'
        database_url = $Context.DatabaseUrl
        bundle_path = $Context.FinalCredentialPath
    }
    if ([int]$verified.password_count_changed -ne [int]$journal.user_count -or
        [int]$verified.session_count_after -ne 0) {
        throw 'database-verification-mismatch'
    }
    $manifest = Read-ValidatedQuarantineManifest `
        -Path $Context.QuarantineManifestPath `
        -RotationId ([string]$journal.rotation_id) `
        -DatabaseId ([string]$journal.database_id)
    $expectedManifestEntries = if ($Context.RootEnvironmentPresent) { 2 } else { 1 }
    if ($manifest.retention -cne $Context.Retention -or
        @($manifest.entries).Count -ne $expectedManifestEntries) {
        throw 'quarantine-manifest-mismatch'
    }
    $finalBundle = $null
    $finalAdminCredential = $null
    if ($phase -ne 'complete') {
        $journal = Write-JournalPhase `
            -Journal $journal `
            -Phase 'complete' `
            -JournalPath $Context.JournalPath `
            -PreviousPath $Context.JournalPreviousPath `
            -WorkspaceRoot $Context.Workspace
    }
    return [PSCustomObject]@{
        Archived = $false
        Journal = $journal
        Verified = $verified
        EnvironmentBindings = $environmentBindings
    }
}

Export-ModuleMember -Function 'Invoke-RotationStateMachine'
