[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$TestMode,
    [string]$TestWorkspaceRoot,
    [ValidateSet('', 'ARCHIVE_COMPLETED_ROTATION_AND_START_NEW')]
    [string]$RestoreConfirmation = '',
    [ValidateSet('', 'before_db_commit', 'after_db_commit', 'after_root_env_promote', 'before_credentials_promote', 'crash_after_secure_root_init', 'crash_during_root_quarantine_copy', 'crash_after_root_quarantine_finalize', 'crash_after_credentials_move')]
    [string]$Failpoint = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Security
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.PathSecurity.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.ProcessLock.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.SecureIO.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Security.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Crypto.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Runtime.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Environment.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Bootstrap.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Journal.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Quarantine.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Archive.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Reconciliation.psm1') -Force -DisableNameChecking

$ProductionWorkspace = 'D:\Chanil_Park\Project\Programming\AeroOne'
$ProductRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$AllowedEnvironmentKeys = @(
    'APP_ENV',
    'APP_NAME',
    'BACKEND_PORT',
    'FRONTEND_PORT',
    'DATABASE_URL',
    'JWT_SECRET_KEY',
    'ADMIN_SESSION_COOKIE_NAME',
    'ACCESS_TOKEN_TTL_MINUTES',
    'ADMIN_USERNAME',
    'ADMIN_PASSWORD',
    'CSRF_COOKIE_NAME',
    'NEWSLETTER_IMPORT_ROOT_CONTAINER',
    'CIVIL_AIRCRAFT_ROOT',
    'DOCUMENT_ROOT',
    'NSA_ROOT',
    'STORAGE_ROOT',
    'THUMBNAILS_DIR_NAME',
    'ATTACHMENTS_DIR_NAME',
    'MARKDOWN_DIR_NAME',
    'CORS_ORIGINS',
    'NEXT_PUBLIC_API_BASE_URL',
    'SERVER_API_BASE_URL',
    'AI_FEATURES_ENABLED',
    'OLLAMA_BASE_URL',
    'OLLAMA_DEFAULT_MODEL',
    'LAN_HOST'
)
$RequiredKeys = @('DATABASE_URL', 'JWT_SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD')
$Retention = '2027-07-10T00:00:00+09:00'
$PhaseOrder = @{
    prepared = 0
    db_committed = 1
    root_env_promoted = 2
    backend_env_promoted = 3
    credentials_promoted = 4
    complete = 5
}
$CurrentStage = 'validate'

Initialize-RotationRuntime -Configuration @{
    TestMode = [bool]$TestMode
    TestWorkspaceRoot = $TestWorkspaceRoot
    ProductionWorkspace = $ProductionWorkspace
    ProductRoot = $ProductRoot
    ScriptPath = $PSCommandPath
    PythonOverride = $env:AEROONE_ROTATION_PYTHON
    AllowedEnvironmentKeys = $AllowedEnvironmentKeys
    RequiredKeys = $RequiredKeys
}
Initialize-RotationJournal -PhaseOrder $PhaseOrder
Initialize-RotationQuarantine -Retention $Retention -Failpoint $Failpoint

function Stop-Rotation {
    param([string]$Code)

    if ($Code -notmatch '^[a-z0-9_-]+$') {
        $Code = 'operation-failed'
    }
    [Console]::Error.WriteLine("status=error code=$Code")
    exit 1
}

function Invoke-TestFailpoint {
    param([string]$Expected)

    if ($Failpoint -ceq $Expected) {
        throw "injected_$Expected"
    }
}

function Invoke-TestCrashpoint {
    param([string]$Expected)

    if ($Failpoint -ceq $Expected) {
        [Diagnostics.Process]::GetCurrentProcess().Kill()
        [Environment]::Exit(97)
    }
}

try {
    if (-not $TestMode -and -not [string]::IsNullOrWhiteSpace($Failpoint)) {
        throw 'failpoint-forbidden'
    }
    $workspace = Get-WorkspaceRoot
    $RotationMutex = Enter-RotationMutex -WorkspaceRoot $workspace
    if ($null -eq $RotationMutex) {
        throw 'rotation-already-running'
    }
    if ($TestMode) {
        $secureBase = $workspace
        $secureRoot = Join-Path $workspace '.rotation-secure'
        $historyRoot = Join-Path $workspace '.rotation-history'
    } else {
        $secureBase = Join-Path $env:USERPROFILE 'AeroOne-secure'
        if (-not (Test-Path -LiteralPath $secureBase)) {
            New-RotationSecureDirectory -Path $secureBase
        } else {
            $secureBaseIdentity = Get-PhysicalPathIdentity -Path $secureBase
            if (-not $secureBaseIdentity.IsDirectory) {
                throw 'secure-directory-invalid'
            }
        }
        Assert-SecureAcl -Path $secureBase
        $secureRoot = Join-Path $secureBase 'incident-20260710'
        $historyRoot = Join-Path $secureBase 'history'
    }
    $finalCredentialPath = Join-Path $secureRoot '1.12.3-credentials.dpapi'
    $journalPath = Join-Path $secureRoot 'rotation-state.json.dpapi'
    $journalPreviousPath = Join-Path $secureRoot 'rotation-state.previous.json.dpapi'
    $resume = (
        (Test-Path -LiteralPath $journalPath -PathType Leaf) -or
        (Test-Path -LiteralPath $journalPreviousPath -PathType Leaf)
    )
    $rootEnvPath = Join-Path $workspace '.env'
    $backendEnvPath = Join-Path $workspace 'backend\.env'
    $recoveryDirectory = Join-Path $secureRoot 'recovery'
    $pendingDirectory = Join-Path $secureRoot 'pending'
    $quarantineDirectory = Join-Path $secureRoot 'quarantine'
    $quarantineEnvDirectory = Join-Path $quarantineDirectory 'environment'
    $recoveryPath = Join-Path $recoveryDirectory 'aeroone-db-before-rotation.dpapi'
    $pendingCredentialPath = Join-Path $pendingDirectory 'credentials.dpapi'
    $pendingRootEnvPath = Join-Path $pendingDirectory 'root-env.dpapi'
    $pendingBackendEnvPath = Join-Path $pendingDirectory 'backend-env.dpapi'
    $quarantineRootEnvPath = Join-Path $quarantineEnvDirectory 'root.env.before-rotation'
    $quarantineBackendEnvPath = Join-Path $quarantineEnvDirectory 'backend.env.before-rotation'
    $quarantineManifestPath = Join-Path $quarantineDirectory 'quarantine-manifest.json'
    $bootstrapMarkerPath = Join-Path $secureRoot 'bootstrap-marker.json.dpapi'
    $secureInitialized = $false

    if (-not [string]::IsNullOrWhiteSpace($RestoreConfirmation) -and -not $resume) {
        throw 'restore-completed-state-required'
    }

    if (-not $resume -and (Test-Path -LiteralPath $finalCredentialPath)) {
        throw 'credential-destination-exists'
    }
    if (-not $resume -and (Test-Path -LiteralPath $secureRoot -PathType Container)) {
        Reset-AbandonedBootstrapRoot -SecureRoot $secureRoot -WorkspaceRoot $workspace
    }

    if ($resume) {
        $CurrentStage = 'resume_preflight'
        $reconciled = Invoke-RotationReconciliation -Context @{
            Workspace = $workspace
            Retention = $Retention
            PhaseOrder = $PhaseOrder
            SecureRoot = $secureRoot
            RecoveryDirectory = $recoveryDirectory
            PendingDirectory = $pendingDirectory
            QuarantineDirectory = $quarantineDirectory
            QuarantineEnvDirectory = $quarantineEnvDirectory
            BootstrapMarkerPath = $bootstrapMarkerPath
            JournalPath = $journalPath
            JournalPreviousPath = $journalPreviousPath
            RecoveryPath = $recoveryPath
            PendingCredentialPath = $pendingCredentialPath
            FinalCredentialPath = $finalCredentialPath
            PendingRootEnvPath = $pendingRootEnvPath
            PendingBackendEnvPath = $pendingBackendEnvPath
            RootRepair = @{
                ActivePath = $rootEnvPath
                QuarantinePath = $quarantineRootEnvPath
                PendingPath = $pendingRootEnvPath
                ManifestPath = $quarantineManifestPath
                SourceLabel = '.env'
                Purpose = 'pending-root-environment'
                ExpectedPhase = 'db_committed'
                NewPhase = 'root_env_promoted'
                AmbiguousCode = 'root-env-state-ambiguous'
                BeforeSha256Field = 'root_before_sha256'
                JournalPath = $journalPath
                JournalPreviousPath = $journalPreviousPath
                Workspace = $workspace
            }
            BackendRepair = @{
                ActivePath = $backendEnvPath
                QuarantinePath = $quarantineBackendEnvPath
                PendingPath = $pendingBackendEnvPath
                ManifestPath = $quarantineManifestPath
                SourceLabel = 'backend/.env'
                Purpose = 'pending-backend-environment'
                ExpectedPhase = 'root_env_promoted'
                NewPhase = 'backend_env_promoted'
                AmbiguousCode = 'backend-env-state-ambiguous'
                BeforeSha256Field = 'backend_before_sha256'
                JournalPath = $journalPath
                JournalPreviousPath = $journalPreviousPath
                Workspace = $workspace
            }
        }
        $journal = $reconciled.journal
        $resumePhase = [string]$reconciled.phase
        $secureInitialized = $true
    }
    $rootEnv = Read-ExactEnv -Path $rootEnvPath
    $backendEnv = Read-ExactEnv -Path $backendEnvPath
    $matchingKeys = @('DATABASE_URL', 'ADMIN_USERNAME')
    if (-not $resume) {
        $matchingKeys += @('JWT_SECRET_KEY', 'ADMIN_PASSWORD')
    }
    foreach ($key in $matchingKeys) {
        if ($rootEnv[$key] -cne $backendEnv[$key]) {
            throw 'env-scope-mismatch'
        }
    }
    $databasePath = Resolve-CanonicalDatabase -DatabaseUrl $rootEnv['DATABASE_URL'] -WorkspaceRoot $workspace
    $backendDatabasePath = Resolve-CanonicalDatabase -DatabaseUrl $backendEnv['DATABASE_URL'] -WorkspaceRoot $workspace
    if (-not $databasePath.Equals($backendDatabasePath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-scope-mismatch'
    }
    $databaseUrl = 'sqlite:///' + $databasePath.Replace('\', '/')
    $inspection = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
        action = 'inspect'
        database_url = $databaseUrl
        admin_username = $rootEnv['ADMIN_USERNAME']
    }
    if ($DryRun) {
        [Console]::Out.WriteLine("status=dry-run scope=valid users=$($inspection.user_count_before)")
        exit 0
    }

    $CurrentStage = 'secure_acl'
    if (-not $secureInitialized) {
        Initialize-SecureDirectory -Path $secureRoot -Resume $resume
        foreach ($directory in @($recoveryDirectory, $pendingDirectory, $quarantineDirectory, $quarantineEnvDirectory)) {
            Initialize-SecureDirectory -Path $directory -Resume $resume
        }
        Write-RotationBootstrapMarker -Path $bootstrapMarkerPath -WorkspaceRoot $workspace
        Invoke-TestCrashpoint -Expected 'crash_after_secure_root_init'
    }

    if (-not $resume) {
        $CurrentStage = 'prepare'
        $prepared = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'prepare'
            database_url = $databaseUrl
            admin_username = $rootEnv['ADMIN_USERNAME']
            bundle_path = $pendingCredentialPath
        }
        Set-SecureFileAcl -Path $pendingCredentialPath
        Assert-SecureAcl -Path $pendingCredentialPath
        $bundle = Read-CredentialBundle -Path $pendingCredentialPath
        $adminCredential = Get-AdminCredential -Bundle $bundle
        $CurrentStage = 'recovery'
        $null = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'backup'
            database_path = $databasePath
            recovery_path = $recoveryPath
            rotation_id = [string]$bundle.rotation_id
            database_id = [string]$bundle.database_id
        }
        Set-SecureFileAcl -Path $recoveryPath
        Assert-SecureAcl -Path $recoveryPath
        $CurrentStage = 'pending_env'
        Write-PendingEnvironment -SourcePath $rootEnvPath -PendingPath $pendingRootEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password -Purpose 'pending-root-environment'
        Write-PendingEnvironment -SourcePath $backendEnvPath -PendingPath $pendingBackendEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password -Purpose 'pending-backend-environment'
        $sealed = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'journal_seal'
            journal = @{
                schema_version = 1
                sequence = 0
                phase = 'prepared'
                rotation_id = [string]$bundle.rotation_id
                database_id = [string]$bundle.database_id
                user_count = [int]$prepared.user_count_before
                retention = $Retention
                bundle_sha256 = Get-FileSha256 -Path $pendingCredentialPath
                recovery_sha256 = Get-FileSha256 -Path $recoveryPath
                pending_root_sha256 = Get-FileSha256 -Path $pendingRootEnvPath
                pending_backend_sha256 = Get-FileSha256 -Path $pendingBackendEnvPath
                root_before_sha256 = Get-FileSha256 -Path $rootEnvPath
                backend_before_sha256 = Get-FileSha256 -Path $backendEnvPath
                root_after_sha256 = Get-ProtectedPayloadSha256 -Path $pendingRootEnvPath -Purpose 'pending-root-environment'
                backend_after_sha256 = Get-ProtectedPayloadSha256 -Path $pendingBackendEnvPath -Purpose 'pending-backend-environment'
            }
        }
        $journal = $sealed.journal
        Write-ProtectedJson -Value $journal -Path $journalPath -Purpose 'rotation-journal' -BackupPath $journalPreviousPath
        Set-SecureFileAcl -Path $rootEnvPath
        Assert-SecureAcl -Path $rootEnvPath
        Set-SecureFileAcl -Path $backendEnvPath
        Assert-SecureAcl -Path $backendEnvPath
        $bundle = $null
        $adminCredential = $null
    } else {
        if ([int]$journal.user_count -ne [int]$inspection.user_count_before) {
            throw 'journal-user-count-mismatch'
        }
        $resumePhase = [string]$journal.phase
        if ($PhaseOrder[$resumePhase] -ge $PhaseOrder['root_env_promoted']) {
            Assert-FileSha256 -Path $rootEnvPath -Expected ([string]$journal.root_after_sha256)
        }
        if ($PhaseOrder[$resumePhase] -ge $PhaseOrder['backend_env_promoted']) {
            Assert-FileSha256 -Path $backendEnvPath -Expected ([string]$journal.backend_after_sha256)
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($RestoreConfirmation)) {
        Invoke-RotationArchive -Context @{
            Journal = $journal
            Retention = $Retention
            Workspace = $workspace
            DatabasePath = $databasePath
            RecoveryPath = $recoveryPath
            SecureRoot = $secureRoot
            HistoryRoot = $historyRoot
            QuarantineManifestPath = $quarantineManifestPath
            QuarantineRootEnvPath = $quarantineRootEnvPath
            QuarantineBackendEnvPath = $quarantineBackendEnvPath
        }
        exit 0
    }

    $phase = [string]$journal.phase
    if ($PhaseOrder[$phase] -lt $PhaseOrder['db_committed']) {
        $CurrentStage = 'db_commit'
        Assert-SecureAcl -Path $pendingCredentialPath
        $committed = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'commit'
            database_url = $databaseUrl
            bundle_path = $pendingCredentialPath
            fail_before_commit = ($Failpoint -ceq 'before_db_commit')
        }
        if ([int]$committed.user_count_after -ne [int]$journal.user_count -or [int]$committed.password_count_changed -ne [int]$journal.user_count) {
            throw 'database-commit-count-mismatch'
        }
        $journal = Write-JournalPhase -Journal $journal -Phase 'db_committed' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
        $phase = 'db_committed'
    }
    Invoke-TestFailpoint -Expected 'after_db_commit'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['root_env_promoted']) {
        $CurrentStage = 'root_env_promote'
        Copy-EnvironmentToQuarantine -SourcePath $rootEnvPath -SourceLabel '.env' -DestinationPath $quarantineRootEnvPath -ManifestPath $quarantineManifestPath
        Promote-ProtectedEnvironment -PendingPath $pendingRootEnvPath -DestinationPath $rootEnvPath -Purpose 'pending-root-environment'
        $journal = Write-JournalPhase -Journal $journal -Phase 'root_env_promoted' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
        $phase = 'root_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'after_root_env_promote'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['backend_env_promoted']) {
        $CurrentStage = 'backend_env_quarantine'
        Copy-EnvironmentToQuarantine -SourcePath $backendEnvPath -SourceLabel 'backend/.env' -DestinationPath $quarantineBackendEnvPath -ManifestPath $quarantineManifestPath
        $CurrentStage = 'backend_env_write'
        Promote-ProtectedEnvironment -PendingPath $pendingBackendEnvPath -DestinationPath $backendEnvPath -Purpose 'pending-backend-environment'
        $CurrentStage = 'backend_env_journal'
        $journal = Write-JournalPhase -Journal $journal -Phase 'backend_env_promoted' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
        $phase = 'backend_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'before_credentials_promote'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['credentials_promoted']) {
        $CurrentStage = 'credentials_promote'
        if (Test-Path -LiteralPath $finalCredentialPath) {
            throw 'credential-destination-exists'
        }
        Move-Item -LiteralPath $pendingCredentialPath -Destination $finalCredentialPath
        Set-SecureFileAcl -Path $finalCredentialPath
        Assert-SecureAcl -Path $finalCredentialPath
        Invoke-TestCrashpoint -Expected 'crash_after_credentials_move'
        $journal = Write-JournalPhase -Journal $journal -Phase 'credentials_promoted' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
        $phase = 'credentials_promoted'
    }

    $CurrentStage = 'verify'
    $finalBundle = Read-CredentialBundle -Path $finalCredentialPath
    $finalAdminCredential = Get-AdminCredential -Bundle $finalBundle
    $finalRootEnv = Read-ExactEnv -Path $rootEnvPath
    $finalBackendEnv = Read-ExactEnv -Path $backendEnvPath
    if ($finalRootEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key -or $finalBackendEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key) {
        throw 'jwt-promotion-mismatch'
    }
    if ($finalRootEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password -or $finalBackendEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password) {
        throw 'admin-promotion-mismatch'
    }
    $verified = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
        action = 'verify'
        database_url = $databaseUrl
        bundle_path = $finalCredentialPath
    }
    if ([int]$verified.password_count_changed -ne [int]$journal.user_count -or [int]$verified.session_count_after -ne 0) {
        throw 'database-verification-mismatch'
    }
    Assert-SecureAcl -Path $quarantineManifestPath
    $manifest = [IO.File]::ReadAllText($quarantineManifestPath) | ConvertFrom-Json
    if ($manifest.retention -cne $Retention -or @($manifest.entries).Count -ne 2) {
        throw 'quarantine-manifest-mismatch'
    }
    $finalBundle = $null
    $finalAdminCredential = $null
    if ($phase -ne 'complete') {
        $journal = Write-JournalPhase -Journal $journal -Phase 'complete' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
    }
    [Console]::Out.WriteLine("status=complete scope=valid users=$($verified.user_count_after)")
    exit 0
} catch {
    $failureCode = $_.Exception.Message
    if ($failureCode -notmatch '^[a-z0-9_-]+$') {
        $failureCode = "stage_$CurrentStage"
    }
    Stop-Rotation -Code $failureCode
}
