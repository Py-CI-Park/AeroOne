Set-StrictMode -Version Latest

$script:Runtime = @{}
$script:InternalCrashpoints = @(
    'crash_after_secure_root_init',
    'crash_after_recovery_publish',
    'crash_after_database_commit',
    'crash_during_root_quarantine_copy',
    'crash_after_root_quarantine_finalize',
    'crash_after_root_env_publish',
    'crash_after_backend_env_publish',
    'crash_during_root_env_temp_write',
    'crash_after_credentials_move'
)

function Initialize-RotationRuntime {
    param([Parameter(Mandatory = $true)][hashtable]$Configuration)

    $script:Runtime = $Configuration.Clone()
}

function Stop-Rotation {
    param([string]$Code)

    if ($Code -notmatch '^[a-z0-9_-]+$') {
        $Code = 'operation-failed'
    }
    [Console]::Error.WriteLine("status=error code=$Code")
    exit 1
}

function Get-WorkspaceRoot {
    if ($script:Runtime.TestMode) {
        $candidate = [IO.Path]::GetFullPath([string]$script:Runtime.TestWorkspaceRoot)
        $leaf = Split-Path -Leaf $candidate
        if ($leaf -notmatch '^aeroone-rotation-test-([a-f0-9]{32})$') {
            throw 'unknown-test-root'
        }
        $nonce = $Matches[1]
        $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not ($candidate + '\').StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'unknown-test-root'
        }
        $markerPath = Join-Path $candidate '.aeroone-rotation-test-root'
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
            throw 'unknown-test-root'
        }
        $null = Assert-SinglePhysicalFile -Path $markerPath
        if ([IO.File]::ReadAllText($markerPath) -cne "aeroone-rotation-test-v1:$nonce") {
            throw 'unknown-test-root'
        }
        $production = [IO.Path]::GetFullPath([string]$script:Runtime.ProductionWorkspace)
        if ($candidate.Equals($production.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
            throw 'unknown-test-root'
        }
        return $candidate.TrimEnd('\')
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$script:Runtime.TestWorkspaceRoot)) {
        throw 'test-root-forbidden'
    }
    $candidate = [IO.Path]::GetFullPath([string]$script:Runtime.ProductionWorkspace)
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw 'production-root-missing'
    }
    Assert-ProductionProvenance `
        -WorkspaceRoot $candidate `
        -ProductRoot $script:Runtime.ProductRoot `
        -ScriptPath $script:Runtime.ScriptPath `
        -ExpectedEntryPoint $script:Runtime.ExpectedEntryPoint
    return $candidate.TrimEnd('\')
}

function Get-RotationInternalCrashpoint {
    param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

    $raw = [string]$env:AEROONE_ROTATION_INTERNAL_CRASH
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return ''
    }
    if (-not $script:Runtime.TestMode) {
        throw 'internal-crashpoint-forbidden'
    }
    $leaf = Split-Path -Leaf $WorkspaceRoot
    if ($leaf -notmatch '^aeroone-rotation-test-([a-f0-9]{32})$') {
        throw 'internal-crashpoint-forbidden'
    }
    $parts = @($raw.Split([char]':'))
    if ($parts.Count -ne 2 -or $parts[0] -cne $Matches[1] -or
        $parts[1] -notin $script:InternalCrashpoints) {
        throw 'internal-crashpoint-forbidden'
    }
    return $parts[1]
}

function Get-RotationInternalDatabaseBarrier {
    param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

    $raw = [string]$env:AEROONE_ROTATION_INTERNAL_DB_BARRIER
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return ''
    }
    if (-not $script:Runtime.TestMode) {
        throw 'internal-db-barrier-forbidden'
    }
    $leaf = Split-Path -Leaf $WorkspaceRoot
    if ($leaf -notmatch '^aeroone-rotation-test-([a-f0-9]{32})$') {
        throw 'internal-db-barrier-forbidden'
    }
    $parts = @($raw.Split([char]':'))
    if ($parts.Count -ne 2 -or $parts[0] -cne $Matches[1] -or
        $parts[1] -notin @('hold_after_recovery', 'hold_after_restore_confirmation')) {
        throw 'internal-db-barrier-forbidden'
    }
    return $parts[1]
}

function Read-ExactEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet('root', 'backend')][string]$Profile
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'env-missing'
    }
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) {
            continue
        }
        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            throw 'env-malformed'
        }
        $key = $line.Substring(0, $separator).Trim()
        if ($values.ContainsKey($key)) {
            throw 'env-duplicate-key'
        }
        $values[$key] = $line.Substring($separator + 1)
    }
    $profileContract = $script:Runtime.EnvironmentProfiles[$Profile]
    foreach ($required in $profileContract.RequiredKeys) {
        if (-not $values.ContainsKey($required) -or [string]::IsNullOrWhiteSpace($values[$required])) {
            throw 'env-required-key-missing'
        }
    }
    foreach ($key in $values.Keys) {
        if ($key -notin $profileContract.AllowedKeys) {
            throw 'unknown-env-key'
        }
    }
    return $values
}

function Get-LiveEnvironmentBindings {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][string]$RootEnvironmentPath,
        [Parameter(Mandatory = $true)][string]$BackendEnvironmentPath,
        [switch]$AllowMissing
    )

    $workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    if (-not $workspaceIdentity.IsDirectory) {
        throw 'workspace-invalid'
    }
    Assert-NoReparseComponents -Path (Split-Path -Parent $RootEnvironmentPath)
    Assert-NoReparseComponents -Path (Split-Path -Parent $BackendEnvironmentPath)
    $rootIdentity = $null
    if (Test-Path -LiteralPath $RootEnvironmentPath -PathType Leaf) {
        $rootIdentity = Assert-SinglePhysicalFile -Path $RootEnvironmentPath
        Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $rootIdentity
    } elseif (-not $AllowMissing) {
        throw 'env-missing'
    }
    $backendIdentity = $null
    if (Test-Path -LiteralPath $BackendEnvironmentPath -PathType Leaf) {
        $backendIdentity = Assert-SinglePhysicalFile -Path $BackendEnvironmentPath
        Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $backendIdentity
    } elseif (-not $AllowMissing) {
        throw 'env-missing'
    }
    if ($null -ne $rootIdentity -and $null -ne $backendIdentity -and
        (Test-SamePhysicalObject -Left $rootIdentity -Right $backendIdentity)) {
        throw 'env-physical-alias'
    }
    return [PSCustomObject]@{
        workspace = $workspaceIdentity
        root = $rootIdentity
        backend = $backendIdentity
    }
}

function Assert-LiveEnvironmentBindings {
    param(
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)][string]$RootEnvironmentPath,
        [Parameter(Mandatory = $true)][string]$BackendEnvironmentPath
    )

    $current = Get-LiveEnvironmentBindings `
        -WorkspaceRoot $Expected.workspace.FinalPath `
        -RootEnvironmentPath $RootEnvironmentPath `
        -BackendEnvironmentPath $BackendEnvironmentPath `
        -AllowMissing
    if (-not (Test-SamePhysicalObject -Left $Expected.workspace -Right $current.workspace) -or
        (($null -eq $Expected.root) -ne ($null -eq $current.root)) -or
        (($null -eq $Expected.backend) -ne ($null -eq $current.backend)) -or
        ($null -ne $Expected.root -and
            -not (Test-SamePhysicalObject -Left $Expected.root -Right $current.root)) -or
        ($null -ne $Expected.backend -and
            -not (Test-SamePhysicalObject -Left $Expected.backend -Right $current.backend))) {
        throw 'env-physical-identity-changed'
    }
    return $current
}

function Resolve-CanonicalDatabase {
    param([string]$DatabaseUrl, [string]$WorkspaceRoot)

    if (-not $DatabaseUrl.StartsWith('sqlite:///', [StringComparison]::Ordinal)) {
        throw 'database-provider-forbidden'
    }
    $rawPath = $DatabaseUrl.Substring('sqlite:///'.Length).Replace('/', '\')
    $resolved = if ([IO.Path]::IsPathRooted($rawPath)) {
        [IO.Path]::GetFullPath($rawPath)
    } else {
        [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $rawPath))
    }
    $expected = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot 'backend\data\aeroone.db'))
    if (-not $resolved.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-path-forbidden'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw 'database-missing'
    }
    $workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $databaseIdentity = Assert-SinglePhysicalFile -Path $resolved
    Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $databaseIdentity
    return $resolved
}

Export-ModuleMember -Function @(
    'Initialize-RotationRuntime',
    'Stop-Rotation',
    'Get-WorkspaceRoot',
    'Get-RotationInternalCrashpoint',
    'Get-RotationInternalDatabaseBarrier',
    'Get-LiveEnvironmentBindings',
    'Assert-LiveEnvironmentBindings',
    'Read-ExactEnv',
    'Resolve-CanonicalDatabase'
)
