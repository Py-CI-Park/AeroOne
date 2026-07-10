Set-StrictMode -Version Latest

function Write-RotationBootstrapMarker {
    param([string]$Path, [string]$WorkspaceRoot)

    $identity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $marker = [PSCustomObject]@{
        schema_version = 1
        workspace_volume = [string]$identity.VolumeSerialNumber
        workspace_file_id = [string]$identity.FileId
        nonce = [Guid]::NewGuid().ToString('N')
    }
    Write-ProtectedJson -Value $marker -Path $Path -Purpose 'rotation-bootstrap-marker'
}

function Assert-RotationBootstrapMarker {
    param([string]$Path, [string]$WorkspaceRoot)

    Assert-SecureAcl -Path $Path
    $null = Assert-SinglePhysicalFile -Path $Path
    $marker = Read-ProtectedJson -Path $Path -Purpose 'rotation-bootstrap-marker'
    $expectedProperties = @('nonce', 'schema_version', 'workspace_file_id', 'workspace_volume')
    $actualProperties = @($marker.PSObject.Properties.Name | Sort-Object)
    if (@(Compare-Object $actualProperties $expectedProperties).Count -ne 0 -or
        [int]$marker.schema_version -ne 1 -or
        [string]$marker.nonce -notmatch '^[a-f0-9]{32}$') {
        throw 'bootstrap-marker-invalid'
    }
    $identity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    if ([string]$marker.workspace_volume -cne [string]$identity.VolumeSerialNumber -or
        [string]$marker.workspace_file_id -cne [string]$identity.FileId) {
        throw 'bootstrap-marker-binding-mismatch'
    }
}

function New-BootstrapScopes {
    param([Parameter(Mandatory = $true)][string]$SecureRoot)

    $recovery = Join-Path $SecureRoot 'recovery'
    $pending = Join-Path $SecureRoot 'pending'
    $quarantine = Join-Path $SecureRoot 'quarantine'
    $environment = Join-Path $quarantine 'environment'
    return @(
        [PSCustomObject]@{
            path = $SecureRoot
            files = @((Join-Path $SecureRoot 'bootstrap-marker.json.dpapi'))
            directories = @($recovery, $pending, $quarantine)
        },
        [PSCustomObject]@{
            path = $recovery
            files = @((Join-Path $recovery 'aeroone-db-before-rotation.dpapi'))
            directories = @()
        },
        [PSCustomObject]@{
            path = $pending
            files = @(
                (Join-Path $pending 'credentials.dpapi'),
                (Join-Path $pending 'root-env.dpapi'),
                (Join-Path $pending 'backend-env.dpapi')
            )
            directories = @()
        },
        [PSCustomObject]@{ path = $quarantine; files = @(); directories = @($environment) },
        [PSCustomObject]@{ path = $environment; files = @(); directories = @() }
    )
}

function Get-BootstrapOwnedFiles {
    param([Parameter(Mandatory = $true)][object[]]$Scopes)

    $files = @()
    foreach ($scope in $Scopes) {
        if (-not (Test-Path -LiteralPath $scope.path -PathType Container)) {
            continue
        }
        foreach ($item in @(Get-ChildItem -LiteralPath $scope.path -Force)) {
            $fullPath = [IO.Path]::GetFullPath($item.FullName)
            if ($item.PSIsContainer) {
                if ($fullPath -notin $scope.directories) {
                    throw 'unexpected-secure-output'
                }
                $identity = Get-PhysicalPathIdentity -Path $fullPath
                if (-not $identity.IsDirectory) {
                    throw 'secure-directory-invalid'
                }
                Assert-SecureAcl -Path $fullPath
                continue
            }
            $isOwnedTemp = $item.Name -match '^\.aeroone-rotation-[a-f0-9]{32}\.tmp$'
            if ($fullPath -notin $scope.files -and -not $isOwnedTemp) {
                throw 'unexpected-secure-output'
            }
            $null = Assert-SinglePhysicalFile -Path $fullPath
            Assert-SecureAcl -Path $fullPath
            $files += $fullPath
        }
    }
    return $files
}

function Remove-BootstrapTree {
    param([string]$SecureRoot, [string[]]$Files)

    foreach ($file in $Files) {
        Remove-Item -LiteralPath $file -Force
    }
    $directories = @(
        (Join-Path $SecureRoot 'quarantine\environment'),
        (Join-Path $SecureRoot 'quarantine'),
        (Join-Path $SecureRoot 'pending'),
        (Join-Path $SecureRoot 'recovery')
    )
    foreach ($directory in $directories) {
        if (Test-Path -LiteralPath $directory -PathType Container) {
            if (@(Get-ChildItem -LiteralPath $directory -Force).Count -ne 0) {
                throw 'bootstrap-cleanup-not-empty'
            }
            Remove-Item -LiteralPath $directory -Force
        }
    }
    if (@(Get-ChildItem -LiteralPath $SecureRoot -Force).Count -ne 0) {
        throw 'bootstrap-cleanup-not-empty'
    }
    Remove-Item -LiteralPath $SecureRoot -Force
}

function Reset-AbandonedBootstrapRoot {
    param([string]$SecureRoot, [string]$WorkspaceRoot)

    $rootIdentity = Get-PhysicalPathIdentity -Path $SecureRoot
    if (-not $rootIdentity.IsDirectory) {
        throw 'secure-directory-invalid'
    }
    Assert-SecureAcl -Path $SecureRoot
    $markerPath = Join-Path $SecureRoot 'bootstrap-marker.json.dpapi'
    $files = @(Get-BootstrapOwnedFiles -Scopes (New-BootstrapScopes -SecureRoot $SecureRoot))
    if (Test-Path -LiteralPath $markerPath -PathType Leaf) {
        Assert-RotationBootstrapMarker -Path $markerPath -WorkspaceRoot $WorkspaceRoot
    } elseif ($files.Count -ne 0) {
        throw 'bootstrap-marker-missing'
    }
    Remove-BootstrapTree -SecureRoot $SecureRoot -Files $files
}

Export-ModuleMember -Function @(
    'Write-RotationBootstrapMarker',
    'Assert-RotationBootstrapMarker',
    'Reset-AbandonedBootstrapRoot'
)
