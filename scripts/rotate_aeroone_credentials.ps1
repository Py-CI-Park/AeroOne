[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$TestMode,
    [string]$TestWorkspaceRoot,
    [ValidateSet('', 'ARCHIVE_COMPLETED_ROTATION_AND_START_NEW')]
    [string]$RestoreConfirmation = '',
    [ValidateSet('before_db_commit', 'after_db_commit', 'after_root_env_promote', 'before_credentials_promote')]
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
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.DatabaseTransaction.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.ServicePreflight.psm1') -Force -DisableNameChecking

$ProductionWorkspace = 'D:\Chanil_Park\Project\Programming\AeroOne'
$ProductRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$RootAllowedEnvironmentKeys = @(
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
    'NEWSLETTER_IMPORT_ROOT_HOST',
    'NEWSLETTER_IMPORT_ROOT_CONTAINER',
    'CIVIL_AIRCRAFT_ROOT_HOST',
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
$BackendAllowedEnvironmentKeys = @(
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
$RequiredEnvironmentKeys = @(
    'APP_ENV', 'DATABASE_URL', 'JWT_SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD'
)
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
$RotationTransaction = $null

Initialize-RotationRuntime -Configuration @{
    TestMode = [bool]$TestMode
    TestWorkspaceRoot = $TestWorkspaceRoot
    ProductionWorkspace = $ProductionWorkspace
    ProductRoot = $ProductRoot
    ScriptPath = $PSCommandPath
    PythonOverride = $env:AEROONE_ROTATION_PYTHON
    EnvironmentProfiles = @{
        root = @{
            AllowedKeys = $RootAllowedEnvironmentKeys
            RequiredKeys = $RequiredEnvironmentKeys
        }
        backend = @{
            AllowedKeys = $BackendAllowedEnvironmentKeys
            RequiredKeys = $RequiredEnvironmentKeys
        }
    }
}
Initialize-RotationJournal -PhaseOrder $PhaseOrder

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

    if ($InternalCrashpoint -ceq $Expected) {
        [Diagnostics.Process]::GetCurrentProcess().Kill()
        [Environment]::Exit(97)
    }
}

function Invoke-TestDatabaseBarrier {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Barrier
    )

    if ([string]::IsNullOrWhiteSpace($Barrier)) {
        return
    }
    $readyPath = Join-Path $WorkspaceRoot '.aeroone-rotation-db-barrier-ready'
    $releasePath = Join-Path $WorkspaceRoot '.aeroone-rotation-db-barrier-release'
    if ((Test-Path -LiteralPath $readyPath) -or (Test-Path -LiteralPath $releasePath)) {
        throw 'internal-db-barrier-stale'
    }
    $encoding = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($readyPath, 'ready', $encoding)
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    try {
        while (-not (Test-Path -LiteralPath $releasePath -PathType Leaf)) {
            if ([DateTime]::UtcNow -ge $deadline) {
                throw 'internal-db-barrier-timeout'
            }
            Start-Sleep -Milliseconds 50
        }
        if ([IO.File]::ReadAllText($releasePath, $encoding) -cne 'release') {
            throw 'internal-db-barrier-invalid-release'
        }
    } finally {
        Remove-Item -LiteralPath $readyPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $releasePath -Force -ErrorAction SilentlyContinue
    }
}

function Get-ValidatedRotationScope {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    $rootEnvironment = Read-ExactEnv -Path $Context.RootEnvironmentPath -Profile 'root'
    $backendEnvironment = Read-ExactEnv -Path $Context.BackendEnvironmentPath -Profile 'backend'
    $matchingKeys = @('APP_ENV', 'DATABASE_URL', 'ADMIN_USERNAME')
    if ($Context.RequireCredentialMatch) {
        $matchingKeys += @('JWT_SECRET_KEY', 'ADMIN_PASSWORD')
    }
    foreach ($key in $matchingKeys) {
        if ($rootEnvironment[$key] -cne $backendEnvironment[$key]) {
            throw 'env-scope-mismatch'
        }
    }
    $databasePath = Resolve-CanonicalDatabase -DatabaseUrl $rootEnvironment['DATABASE_URL'] -WorkspaceRoot $Context.Workspace
    $backendDatabasePath = Resolve-CanonicalDatabase -DatabaseUrl $backendEnvironment['DATABASE_URL'] -WorkspaceRoot $Context.Workspace
    if (-not $databasePath.Equals($backendDatabasePath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-scope-mismatch'
    }
    $databaseUrl = 'sqlite:///' + $databasePath.Replace('\', '/')
    $inspection = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'inspect'
        database_url = $databaseUrl
        admin_username = $rootEnvironment['ADMIN_USERNAME']
    }
    return [PSCustomObject]@{
        root_environment = $rootEnvironment
        backend_environment = $backendEnvironment
        database_path = $databasePath
        database_url = $databaseUrl
        inspection = $inspection
    }
}

try {
    if (-not $TestMode -and -not [string]::IsNullOrWhiteSpace([string]$env:AEROONE_ROTATION_INTERNAL_CRASH)) {
        throw 'internal-crashpoint-forbidden'
    }
    if (-not $TestMode -and -not [string]::IsNullOrWhiteSpace([string]$env:AEROONE_ROTATION_INTERNAL_DB_BARRIER)) {
        throw 'internal-db-barrier-forbidden'
    }
    if (-not $TestMode -and -not [string]::IsNullOrWhiteSpace($Failpoint)) {
        throw 'failpoint-forbidden'
    }
    $workspace = Get-WorkspaceRoot
    $InternalCrashpoint = Get-RotationInternalCrashpoint -WorkspaceRoot $workspace
    $InternalDatabaseBarrier = Get-RotationInternalDatabaseBarrier -WorkspaceRoot $workspace
    Initialize-RotationQuarantine -Retention $Retention -InternalCrashpoint $InternalCrashpoint
    $RotationMutex = Enter-RotationMutex -WorkspaceRoot $workspace
    if ($null -eq $RotationMutex) {
        throw 'rotation-already-running'
    }
    $rootEnvPath = Join-Path $workspace '.env'
    $backendEnvPath = Join-Path $workspace 'backend\.env'
    $environmentBindings = Get-LiveEnvironmentBindings `
        -WorkspaceRoot $workspace `
        -RootEnvironmentPath $rootEnvPath `
        -BackendEnvironmentPath $backendEnvPath `
        -AllowMissing
    $preflightSecureRoot = if ($TestMode) {
        Join-Path $workspace '.rotation-secure'
    } else {
        Join-Path $env:USERPROFILE 'AeroOne-secure\incident-20260710'
    }
    $preflightResume = (
        (Test-Path -LiteralPath (Join-Path $preflightSecureRoot 'rotation-state.json.dpapi') -PathType Leaf) -or
        (Test-Path -LiteralPath (Join-Path $preflightSecureRoot 'rotation-state.previous.json.dpapi') -PathType Leaf)
    )
    $rootEnvironmentExists = Test-Path -LiteralPath $rootEnvPath -PathType Leaf
    $backendEnvironmentExists = Test-Path -LiteralPath $backendEnvPath -PathType Leaf
    if ($rootEnvironmentExists -and $backendEnvironmentExists) {
        $preflightRootEnvironment = Read-ExactEnv -Path $rootEnvPath -Profile 'root'
        $preflightBackendEnvironment = Read-ExactEnv -Path $backendEnvPath -Profile 'backend'
    } elseif ($preflightResume -and $rootEnvironmentExists) {
        $preflightRootEnvironment = Read-ExactEnv -Path $rootEnvPath -Profile 'root'
        $preflightBackendEnvironment = $preflightRootEnvironment
    } elseif ($preflightResume -and $backendEnvironmentExists) {
        $preflightBackendEnvironment = Read-ExactEnv -Path $backendEnvPath -Profile 'backend'
        $preflightRootEnvironment = $preflightBackendEnvironment
    } else {
        throw 'env-missing'
    }
    Assert-AeroOneServicesStopped `
        -RootEnvironment $preflightRootEnvironment `
        -BackendEnvironment $preflightBackendEnvironment `
        -CheckWindowsServices:(-not $TestMode)
    if ($DryRun) {
        $scope = Get-ValidatedRotationScope -Context @{
            Workspace = $workspace
            RootEnvironmentPath = $rootEnvPath
            BackendEnvironmentPath = $backendEnvPath
            RequireCredentialMatch = $true
        }
        [Console]::Out.WriteLine("status=dry-run scope=valid users=$($scope.inspection.user_count_before)")
        exit 0
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
                AfterSha256Field = 'root_after_sha256'
                PhaseOrder = $PhaseOrder
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
                AfterSha256Field = 'backend_after_sha256'
                PhaseOrder = $PhaseOrder
                JournalPath = $journalPath
                JournalPreviousPath = $journalPreviousPath
                Workspace = $workspace
            }
        }
        $journal = $reconciled.journal
        $resumePhase = [string]$reconciled.phase
        $secureInitialized = $true
    }
    $environmentBindings = Assert-LiveEnvironmentBindings `
        -Expected $environmentBindings `
        -RootEnvironmentPath $rootEnvPath `
        -BackendEnvironmentPath $backendEnvPath
    $scope = Get-ValidatedRotationScope -Context @{
        Workspace = $workspace
        RootEnvironmentPath = $rootEnvPath
        BackendEnvironmentPath = $backendEnvPath
        RequireCredentialMatch = (-not $resume)
    }
    $rootEnv = $scope.root_environment
    $backendEnv = $scope.backend_environment
    $databasePath = [string]$scope.database_path
    $databaseUrl = [string]$scope.database_url
    $inspection = $scope.inspection

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
        $CurrentStage = 'pending_env'
        Write-PendingEnvironment -SourcePath $rootEnvPath -PendingPath $pendingRootEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password -Purpose 'pending-root-environment'
        Write-PendingEnvironment -SourcePath $backendEnvPath -PendingPath $pendingBackendEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password -Purpose 'pending-backend-environment'
        $CurrentStage = 'recovery'
        Publish-RotationSecureBytes -Bytes (New-Object byte[] 0) -DestinationPath $recoveryPath
        $transactionPython = if ($TestMode) {
            [IO.Path]::GetFullPath([string]$env:AEROONE_ROTATION_PYTHON)
        } else {
            Join-Path $workspace 'backend\.venv\Scripts\python.exe'
        }
        $RotationTransaction = Start-RotationDatabaseTransaction `
            -PythonPath $transactionPython `
            -WorkingDirectory (Join-Path $ProductRoot 'backend') `
            -Request @{
                action = 'begin'
                database_url = $databaseUrl
                bundle_path = $pendingCredentialPath
                recovery_path = $recoveryPath
                fail_before_commit = ($Failpoint -ceq 'before_db_commit')
            }
        if ([int]$RotationTransaction.ready.user_count_before -ne [int]$prepared.user_count_before) {
            throw 'prepare-drift-detected'
        }
        Set-SecureFileAcl -Path $recoveryPath
        Assert-SecureAcl -Path $recoveryPath
        Assert-FileSha256 -Path $recoveryPath -Expected ([string]$RotationTransaction.ready.recovery_sha256)
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
                recovery_sha256 = [string]$RotationTransaction.ready.recovery_sha256
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
        $environmentBindings = Assert-LiveEnvironmentBindings `
            -Expected $environmentBindings `
            -RootEnvironmentPath $rootEnvPath `
            -BackendEnvironmentPath $backendEnvPath
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
        $environmentBindings = Assert-LiveEnvironmentBindings `
            -Expected $environmentBindings `
            -RootEnvironmentPath $rootEnvPath `
            -BackendEnvironmentPath $backendEnvPath
        Assert-SecureAcl -Path $pendingCredentialPath
        if ($null -eq $RotationTransaction) {
            Assert-SecureAcl -Path $recoveryPath
            Assert-FileSha256 -Path $recoveryPath -Expected ([string]$journal.recovery_sha256)
            Remove-Item -LiteralPath $recoveryPath -Force
            Publish-RotationSecureBytes -Bytes (New-Object byte[] 0) -DestinationPath $recoveryPath
            $transactionPython = if ($TestMode) {
                [IO.Path]::GetFullPath([string]$env:AEROONE_ROTATION_PYTHON)
            } else {
                Join-Path $workspace 'backend\.venv\Scripts\python.exe'
            }
            $RotationTransaction = Start-RotationDatabaseTransaction `
                -PythonPath $transactionPython `
                -WorkingDirectory (Join-Path $ProductRoot 'backend') `
                -Request @{
                    action = 'begin'
                    database_url = $databaseUrl
                    bundle_path = $pendingCredentialPath
                    recovery_path = $recoveryPath
                    fail_before_commit = ($Failpoint -ceq 'before_db_commit')
                }
            if ([int]$RotationTransaction.ready.user_count_before -ne [int]$journal.user_count) {
                throw 'prepare-drift-detected'
            }
            Set-SecureFileAcl -Path $recoveryPath
            Assert-SecureAcl -Path $recoveryPath
            Assert-FileSha256 -Path $recoveryPath -Expected ([string]$RotationTransaction.ready.recovery_sha256)
            $journalPayload = @{}
            foreach ($property in $journal.PSObject.Properties) {
                if ($property.Name -cne 'checksum_sha256') {
                    $journalPayload[$property.Name] = $property.Value
                }
            }
            $journalPayload['sequence'] = [int]$journal.sequence + 1
            $journalPayload['recovery_sha256'] = [string]$RotationTransaction.ready.recovery_sha256
            $resealed = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
                action = 'journal_seal'
                journal = $journalPayload
            }
            $journal = $resealed.journal
            Write-ProtectedJson -Value $journal -Path $journalPath -Purpose 'rotation-journal' -BackupPath $journalPreviousPath
        }
        try {
            Invoke-TestDatabaseBarrier -WorkspaceRoot $workspace -Barrier $InternalDatabaseBarrier
            $committed = Complete-RotationDatabaseTransaction -Transaction $RotationTransaction
        } finally {
            $RotationTransaction = $null
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
        Copy-EnvironmentToQuarantine `
            -SourcePath $rootEnvPath `
            -SourceLabel '.env' `
            -DestinationPath $quarantineRootEnvPath `
            -ManifestPath $quarantineManifestPath `
            -RotationId ([string]$journal.rotation_id) `
            -DatabaseId ([string]$journal.database_id)
        Promote-ProtectedEnvironment -PendingPath $pendingRootEnvPath -DestinationPath $rootEnvPath -Purpose 'pending-root-environment' -CrashAfterPartialWrite:($InternalCrashpoint -ceq 'crash_during_root_env_temp_write')
        Invoke-TestCrashpoint -Expected 'crash_after_root_env_publish'
        $journal = Write-JournalPhase -Journal $journal -Phase 'root_env_promoted' -JournalPath $journalPath -PreviousPath $journalPreviousPath -WorkspaceRoot $workspace
        $phase = 'root_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'after_root_env_promote'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['backend_env_promoted']) {
        $CurrentStage = 'backend_env_quarantine'
        Copy-EnvironmentToQuarantine `
            -SourcePath $backendEnvPath `
            -SourceLabel 'backend/.env' `
            -DestinationPath $quarantineBackendEnvPath `
            -ManifestPath $quarantineManifestPath `
            -RotationId ([string]$journal.rotation_id) `
            -DatabaseId ([string]$journal.database_id)
        $CurrentStage = 'backend_env_write'
        Promote-ProtectedEnvironment -PendingPath $pendingBackendEnvPath -DestinationPath $backendEnvPath -Purpose 'pending-backend-environment'
        Invoke-TestCrashpoint -Expected 'crash_after_backend_env_publish'
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
    $finalRootEnv = Read-ExactEnv -Path $rootEnvPath -Profile 'root'
    $finalBackendEnv = Read-ExactEnv -Path $backendEnvPath -Profile 'backend'
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
    $manifest = Read-ValidatedQuarantineManifest `
        -Path $quarantineManifestPath `
        -RotationId ([string]$journal.rotation_id) `
        -DatabaseId ([string]$journal.database_id)
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
    $capturedFailure = $_
    Stop-RotationDatabaseTransaction -Transaction $RotationTransaction
    $failureCode = $capturedFailure.Exception.Message
    if ($failureCode -notmatch '^[a-z0-9_-]+$') {
        $failureCode = "stage_$CurrentStage"
    }
    Stop-Rotation -Code $failureCode
}
