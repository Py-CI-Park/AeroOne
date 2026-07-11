Set-StrictMode -Version Latest

function Restore-RotationBootstrapJournal {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [Parameter(Mandatory = $true)]$Scope
    )

    $inventoryRecoveryPath = Initialize-RotationResumeTree `
        -Context (New-RotationReconciliationContext -Context $Context)
    Assert-SecureAcl -Path $Context.PendingCredentialPath
    Assert-SecureAcl -Path $Context.PendingBackendEnvPath
    Assert-ProtectedBytesReadable `
        -Path $Context.PendingBackendEnvPath `
        -Purpose 'pending-backend-environment'
    $bundle = Read-CredentialBundle -Path $Context.PendingCredentialPath
    $recoveryPath = Join-Path `
        $Context.RecoveryDirectory `
        ("aeroone-db-before-rotation.$([string]$bundle.rotation_id).dpapi")
    if (-not ([IO.Path]::GetFullPath($recoveryPath)).Equals(
        $inventoryRecoveryPath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'journal-binding-mismatch'
    }
    $null = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'confirm_restore'
        database_path = [string]$Scope.database_path
        recovery_path = $recoveryPath
        rotation_id = [string]$bundle.rotation_id
        database_id = [string]$bundle.database_id
    }
    if ($Context.RootEnvironmentPresent) {
        Set-SecureFileAcl -Path $Context.RootEnvPath
        Assert-SecureAcl -Path $Context.RootEnvPath
    }
    Set-SecureFileAcl -Path $Context.BackendEnvPath
    Assert-SecureAcl -Path $Context.BackendEnvPath
    $pendingRootSha256 = $null
    $rootBeforeSha256 = $null
    $rootAfterSha256 = $null
    if ($Context.RootEnvironmentPresent) {
        Assert-SecureAcl -Path $Context.PendingRootEnvPath
        Assert-ProtectedBytesReadable `
            -Path $Context.PendingRootEnvPath `
            -Purpose 'pending-root-environment'
        $pendingRootSha256 = Get-FileSha256 -Path $Context.PendingRootEnvPath
        $rootBeforeSha256 = Get-FileSha256 -Path $Context.RootEnvPath
        $rootAfterSha256 = Get-ProtectedPayloadSha256 `
            -Path $Context.PendingRootEnvPath `
            -Purpose 'pending-root-environment'
    }
    $sealed = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'journal_seal'
        journal = @{
            schema_version = 2
            sequence = 0
            phase = 'prepared'
            root_environment_present = [bool]$Context.RootEnvironmentPresent
            rotation_id = [string]$bundle.rotation_id
            database_id = [string]$bundle.database_id
            user_count = [int]$Scope.inspection.user_count_before
            retention = $Context.Retention
            bundle_sha256 = Get-FileSha256 -Path $Context.PendingCredentialPath
            recovery_sha256 = Get-FileSha256 -Path $recoveryPath
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
    Write-ProtectedJson `
        -Value $sealed.journal `
        -Path $Context.JournalPath `
        -Purpose 'rotation-journal'
    return [PSCustomObject]@{
        Journal = $sealed.journal
        RecoveryPath = $recoveryPath
    }
}

function Initialize-RotationRecoveryState {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Context,
        [Parameter(Mandatory = $true)][ref]$Stage,
        [Parameter(Mandatory = $true)][ref]$Transaction
    )

    $journal = $null
    $scope = $null
    $environmentBindings = $null
    $recoveryPath = $null
    $secureInitialized = $false
    $effectiveRootEnvironmentPresent = [bool]$Context.RootEnvironmentPresent
    if ($Context.Resume) {
        $Stage.Value = 'resume_preflight'
        $hasJournal = (
            (Test-Path -LiteralPath $Context.JournalPath -PathType Leaf) -or
            (Test-Path -LiteralPath $Context.JournalPreviousPath -PathType Leaf)
        )
        if (-not $hasJournal) {
            $environmentBindings = Assert-LiveEnvironmentBindings `
                -Expected $Context.EnvironmentBindings `
                -RootEnvironmentPath $Context.RootEnvPath `
                -BackendEnvironmentPath $Context.BackendEnvPath
            $scope = Get-ValidatedRotationScope -Context @{
                Workspace = $Context.Workspace
                RootEnvironmentPath = $Context.RootEnvPath
                BackendEnvironmentPath = $Context.BackendEnvPath
                RootEnvironmentPresent = [bool]$Context.RootEnvironmentPresent
                RequireCredentialMatch = $false
            }
            $null = Restore-RotationBootstrapJournal -Context $Context -Scope $scope
        }
        $reconciled = Invoke-RotationReconciliation `
            -Context (New-RotationReconciliationContext -Context $Context)
        $journal = $reconciled.journal
        $recoveryPath = [string]$reconciled.recovery_path
        $secureInitialized = $true
        $effectiveRootEnvironmentPresent = [bool]$journal.root_environment_present
        $environmentBindings = Get-LiveEnvironmentBindings `
            -WorkspaceRoot $Context.Workspace `
            -RootEnvironmentPath $Context.RootEnvPath `
            -BackendEnvironmentPath $Context.BackendEnvPath `
            -AllowMissing
        if ($null -eq $environmentBindings.backend) {
            throw 'env-missing'
        }
        if (($null -ne $environmentBindings.root) -ne $effectiveRootEnvironmentPresent) {
            throw 'env-topology-changed'
        }
    }
    if ($null -eq $environmentBindings) {
        $environmentBindings = Assert-LiveEnvironmentBindings `
            -Expected $Context.EnvironmentBindings `
            -RootEnvironmentPath $Context.RootEnvPath `
            -BackendEnvironmentPath $Context.BackendEnvPath
    }
    if ($null -eq $scope) {
        $scope = Get-ValidatedRotationScope -Context @{
            Workspace = $Context.Workspace
            RootEnvironmentPath = $Context.RootEnvPath
            BackendEnvironmentPath = $Context.BackendEnvPath
            RootEnvironmentPresent = $effectiveRootEnvironmentPresent
            RequireCredentialMatch = (-not $Context.Resume)
        }
    }
    $Stage.Value = 'secure_acl'
    if (-not $secureInitialized) {
        Initialize-SecureDirectory -Path $Context.SecureRoot -Resume $Context.Resume
        foreach ($directory in @(
            $Context.RecoveryDirectory,
            $Context.PendingDirectory,
            $Context.QuarantineDirectory,
            $Context.QuarantineEnvDirectory
        )) {
            Initialize-SecureDirectory -Path $directory -Resume $Context.Resume
        }
        Write-RotationBootstrapMarker `
            -Path $Context.BootstrapMarkerPath `
            -WorkspaceRoot $Context.Workspace
        Invoke-TestCrashpoint -Expected 'crash_after_secure_root_init'
    }
    if (-not $Context.Resume) {
        $Stage.Value = 'prepare'
        $prepared = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
            action = 'prepare'
            database_url = $scope.database_url
            admin_username = $scope.root_environment['ADMIN_USERNAME']
            bundle_path = $Context.PendingCredentialPath
        }
        Set-SecureFileAcl -Path $Context.PendingCredentialPath
        Assert-SecureAcl -Path $Context.PendingCredentialPath
        $bundle = Read-CredentialBundle -Path $Context.PendingCredentialPath
        $adminCredential = Get-AdminCredential -Bundle $bundle
        $Stage.Value = 'pending_env'
        if ($Context.RootEnvironmentPresent) {
            Write-PendingEnvironment `
                -SourcePath $Context.RootEnvPath `
                -PendingPath $Context.PendingRootEnvPath `
                -JwtSecret $bundle.jwt_secret_key `
                -AdminPassword $adminCredential.password `
                -Purpose 'pending-root-environment'
        }
        Write-PendingEnvironment `
            -SourcePath $Context.BackendEnvPath `
            -PendingPath $Context.PendingBackendEnvPath `
            -JwtSecret $bundle.jwt_secret_key `
            -AdminPassword $adminCredential.password `
            -Purpose 'pending-backend-environment'
        $Stage.Value = 'recovery'
        $preparedState = Start-RotationPreparedTransaction `
            -Context ($Context + @{ DatabaseUrl = $scope.database_url }) `
            -Prepared $prepared `
            -Bundle $bundle
        $journal = $preparedState.Journal
        $Transaction.Value = $preparedState.Transaction
        $recoveryPath = [string]$preparedState.RecoveryPath
        Write-ProtectedJson `
            -Value $journal `
            -Path $Context.JournalPath `
            -Purpose 'rotation-journal' `
            -BackupPath $Context.JournalPreviousPath
        $environmentBindings = Assert-LiveEnvironmentBindings `
            -Expected $environmentBindings `
            -RootEnvironmentPath $Context.RootEnvPath `
            -BackendEnvironmentPath $Context.BackendEnvPath
        if ($Context.RootEnvironmentPresent) {
            Set-SecureFileAcl -Path $Context.RootEnvPath
            Assert-SecureAcl -Path $Context.RootEnvPath
        }
        Set-SecureFileAcl -Path $Context.BackendEnvPath
        Assert-SecureAcl -Path $Context.BackendEnvPath
        $bundle = $null
        $adminCredential = $null
    } else {
        if ([int]$journal.user_count -ne [int]$scope.inspection.user_count_before) {
            throw 'journal-user-count-mismatch'
        }
        $resumePhase = [string]$journal.phase
        if ($effectiveRootEnvironmentPresent -and
            $Context.PhaseOrder[$resumePhase] -ge $Context.PhaseOrder['root_env_promoted']) {
            Assert-FileSha256 -Path $Context.RootEnvPath -Expected ([string]$journal.root_after_sha256)
        }
        if ($Context.PhaseOrder[$resumePhase] -ge $Context.PhaseOrder['backend_env_promoted']) {
            Assert-FileSha256 -Path $Context.BackendEnvPath -Expected ([string]$journal.backend_after_sha256)
        }
    }
    return [PSCustomObject]@{
        Journal = $journal
        Scope = $scope
        EnvironmentBindings = $environmentBindings
        RootEnvironmentPresent = $effectiveRootEnvironmentPresent
        RecoveryPath = $recoveryPath
    }
}

Export-ModuleMember -Function 'Initialize-RotationRecoveryState'
