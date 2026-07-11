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
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Configuration.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Runtime.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.PythonCommand.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Scope.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.TestSeams.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Environment.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Bootstrap.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Journal.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Quarantine.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Archive.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Reconciliation.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.RecoveryPreparation.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.RecoveryOrchestrator.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.StateMachine.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.DatabaseTransaction.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.ServicePreflight.psm1') -Force -DisableNameChecking

$Configuration = New-RotationConfiguration `
    -ScriptDirectory $PSScriptRoot `
    -ScriptPath $PSCommandPath `
    -ExpectedEntryPoint 'scripts\rotate_aeroone_credentials.ps1' `
    -TestMode ([bool]$TestMode) `
    -TestWorkspaceRoot $TestWorkspaceRoot `
    -PythonOverride ([string]$env:AEROONE_ROTATION_PYTHON)
$ProductRoot = [string]$Configuration.ProductRoot
$Retention = [string]$Configuration.Retention
$PhaseOrder = $Configuration.PhaseOrder
$CurrentStage = 'validate'
$RotationTransaction = $null

Initialize-RotationRuntime -Configuration $Configuration.Runtime
Initialize-RotationPythonCommand -Configuration $Configuration.Runtime
Initialize-RotationJournal -PhaseOrder $PhaseOrder

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
    Initialize-RotationTestSeams -Failpoint $Failpoint -Crashpoint $InternalCrashpoint
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
    $rootEnvironmentExists = Test-Path -LiteralPath $rootEnvPath -PathType Leaf
    $backendEnvironmentExists = Test-Path -LiteralPath $backendEnvPath -PathType Leaf
    if (-not $backendEnvironmentExists) {
        throw 'env-missing'
    }
    $preflightBackendEnvironment = Read-ExactEnv -Path $backendEnvPath -Profile 'backend'
    $preflightRootEnvironment = if ($rootEnvironmentExists) {
        Read-ExactEnv -Path $rootEnvPath -Profile 'root'
    } else {
        $preflightBackendEnvironment
    }
    $rootEnvironmentPresent = [bool]$rootEnvironmentExists
    Assert-AeroOneServicesStopped `
        -RootEnvironment $preflightRootEnvironment `
        -BackendEnvironment $preflightBackendEnvironment `
        -CheckWindowsServices:(-not $TestMode)
    if ($DryRun) {
        $scope = Get-ValidatedRotationScope -Context @{
            Workspace = $workspace
            RootEnvironmentPath = $rootEnvPath
            BackendEnvironmentPath = $backendEnvPath
            RootEnvironmentPresent = $rootEnvironmentPresent
            RequireCredentialMatch = $true
        }
        [Console]::Out.WriteLine("status=dry-run scope=valid users=$($scope.inspection.user_count_before)")
        exit 0
    }
    if ($TestMode) {
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
    $finalCredentialPath = Join-Path $secureRoot 'credentials.dpapi'
    $journalPath = Join-Path $secureRoot 'rotation-state.json.dpapi'
    $journalPreviousPath = Join-Path $secureRoot 'rotation-state.previous.json.dpapi'
    $recoveryDirectory = Join-Path $secureRoot 'recovery'
    $pendingDirectory = Join-Path $secureRoot 'pending'
    $quarantineDirectory = Join-Path $secureRoot 'quarantine'
    $quarantineEnvDirectory = Join-Path $quarantineDirectory 'environment'
    $hasVersionedRecovery = $false
    if (Test-Path -LiteralPath $recoveryDirectory -PathType Container) {
        $hasVersionedRecovery = @(
            Get-ChildItem -LiteralPath $recoveryDirectory -File -Force |
                Where-Object {
                    $_.Name -match '^aeroone-db-before-rotation\.[a-f0-9-]{36}\.dpapi$'
                }
        ).Count -gt 0
    }
    $resume = (
        (Test-Path -LiteralPath $journalPath -PathType Leaf) -or
        (Test-Path -LiteralPath $journalPreviousPath -PathType Leaf) -or
        $hasVersionedRecovery
    )
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

    $recoveryState = Initialize-RotationRecoveryState `
        -Stage ([ref]$CurrentStage) `
        -Transaction ([ref]$RotationTransaction) `
        -Context @{
            Resume = $resume
            TestMode = [bool]$TestMode
            PythonOverride = [string]$env:AEROONE_ROTATION_PYTHON
            Failpoint = $Failpoint
            Workspace = $workspace
            ProductRoot = $ProductRoot
            Retention = $Retention
            PhaseOrder = $PhaseOrder
            EnvironmentBindings = $environmentBindings
            RootEnvironmentPresent = $rootEnvironmentPresent
            RootEnvPath = $rootEnvPath
            BackendEnvPath = $backendEnvPath
            SecureRoot = $secureRoot
            RecoveryDirectory = $recoveryDirectory
            PendingDirectory = $pendingDirectory
            QuarantineDirectory = $quarantineDirectory
            QuarantineEnvDirectory = $quarantineEnvDirectory
            BootstrapMarkerPath = $bootstrapMarkerPath
            JournalPath = $journalPath
            JournalPreviousPath = $journalPreviousPath
            PendingCredentialPath = $pendingCredentialPath
            FinalCredentialPath = $finalCredentialPath
            PendingRootEnvPath = $pendingRootEnvPath
            PendingBackendEnvPath = $pendingBackendEnvPath
            QuarantineRootEnvPath = $quarantineRootEnvPath
            QuarantineBackendEnvPath = $quarantineBackendEnvPath
            QuarantineManifestPath = $quarantineManifestPath
        }
    $journal = $recoveryState.Journal
    $scope = $recoveryState.Scope
    $environmentBindings = $recoveryState.EnvironmentBindings
    $rootEnvironmentPresent = [bool]$recoveryState.RootEnvironmentPresent
    $databasePath = [string]$scope.database_path
    $databaseUrl = [string]$scope.database_url
    $recoveryPath = [string]$recoveryState.RecoveryPath

    $stateResult = Invoke-RotationStateMachine `
        -Stage ([ref]$CurrentStage) `
        -Transaction ([ref]$RotationTransaction) `
        -Context @{
            Journal = $journal
            EnvironmentBindings = $environmentBindings
            RootEnvironmentPresent = $rootEnvironmentPresent
            RestoreConfirmation = $RestoreConfirmation
            Retention = $Retention
            PhaseOrder = $PhaseOrder
            Workspace = $workspace
            ProductRoot = $ProductRoot
            TestMode = [bool]$TestMode
            PythonOverride = [string]$env:AEROONE_ROTATION_PYTHON
            Failpoint = $Failpoint
            InternalCrashpoint = $InternalCrashpoint
            InternalDatabaseBarrier = $InternalDatabaseBarrier
            DatabasePath = $databasePath
            DatabaseUrl = $databaseUrl
            RootEnvPath = $rootEnvPath
            BackendEnvPath = $backendEnvPath
            SecureRoot = $secureRoot
            HistoryRoot = $historyRoot
            RecoveryPath = $recoveryPath
            PendingCredentialPath = $pendingCredentialPath
            FinalCredentialPath = $finalCredentialPath
            PendingRootEnvPath = $pendingRootEnvPath
            PendingBackendEnvPath = $pendingBackendEnvPath
            QuarantineManifestPath = $quarantineManifestPath
            QuarantineRootEnvPath = $quarantineRootEnvPath
            QuarantineBackendEnvPath = $quarantineBackendEnvPath
            JournalPath = $journalPath
            JournalPreviousPath = $journalPreviousPath
        }
    if ($stateResult.Archived) {
        exit 0
    }
    [Console]::Out.WriteLine("status=complete scope=valid users=$($stateResult.Verified.user_count_after)")
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
