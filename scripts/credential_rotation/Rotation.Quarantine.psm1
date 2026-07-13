Set-StrictMode -Version Latest

$script:Retention = ''
$script:InternalCrashpoint = ''

function Initialize-RotationQuarantine {
    param([string]$Retention, [string]$InternalCrashpoint)

    $script:Retention = $Retention
    $script:InternalCrashpoint = $InternalCrashpoint
}

function Assert-QuarantineManifestProperties {
    param($Value, [Parameter(Mandatory = $true)][string[]]$Expected)

    $actual = @($Value.PSObject.Properties.Name | Sort-Object)
    $required = @($Expected | Sort-Object)
    if (@(Compare-Object $required $actual -CaseSensitive).Count -ne 0) {
        throw 'quarantine-manifest-mismatch'
    }
}

function Get-QuarantineManifestPayload {
    param([Parameter(Mandatory = $true)]$Manifest)

    $entries = @(
        foreach ($entry in @($Manifest.entries)) {
            [PSCustomObject][ordered]@{
                source = [string]$entry.source
                category = [string]$entry.category
                size = [long]$entry.size
                sha256 = [string]$entry.sha256
                moved_at = [string]$entry.moved_at
                retention = [string]$entry.retention
            }
        }
    )
    return [PSCustomObject][ordered]@{
        schema_version = [int]$Manifest.schema_version
        rotation_id = [string]$Manifest.rotation_id
        database_id = [string]$Manifest.database_id
        retention = [string]$Manifest.retention
        entries = $entries
    }
}

function Get-QuarantineManifestChecksum {
    param([Parameter(Mandatory = $true)]$Manifest)

    $json = (Get-QuarantineManifestPayload -Manifest $Manifest) | ConvertTo-Json -Compress -Depth 8
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($json)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($bytes)
        try {
            return [BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
        } finally {
            [Array]::Clear($digest, 0, $digest.Length)
        }
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        $sha.Dispose()
    }
}

function Assert-QuarantineManifestEntry {
    param(
        $Entry,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][Collections.Generic.HashSet[string]]$Sources
    )

    Assert-QuarantineManifestProperties -Value $Entry -Expected @(
        'source', 'category', 'size', 'sha256', 'moved_at', 'retention'
    )
    $movedAt = [DateTimeOffset]::MinValue
    if ($Entry.source -notin @('.env', 'backend/.env') -or
        -not $Sources.Add([string]$Entry.source) -or
        [string]$Entry.category -cne 'environment' -or
        (($Entry.size -isnot [int]) -and ($Entry.size -isnot [long])) -or
        [long]$Entry.size -lt 1 -or
        [string]$Entry.sha256 -notmatch '^[a-f0-9]{64}$' -or
        $Entry.moved_at -isnot [string] -or
        -not [DateTimeOffset]::TryParseExact(
            [string]$Entry.moved_at,
            'o',
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind,
            [ref]$movedAt
        ) -or
        [string]$Entry.retention -cne $script:Retention) {
        throw 'quarantine-manifest-mismatch'
    }
}

function Assert-QuarantineManifest {
    param($Manifest, [string]$RotationId, [string]$DatabaseId)

    Assert-QuarantineManifestProperties -Value $Manifest -Expected @(
        'schema_version', 'rotation_id', 'database_id', 'retention', 'entries', 'checksum_sha256'
    )
    if (($Manifest.schema_version -isnot [int]) -or [int]$Manifest.schema_version -ne 1 -or
        [string]$Manifest.retention -cne $script:Retention -or
        [string]$Manifest.checksum_sha256 -notmatch '^[a-f0-9]{64}$') {
        throw 'quarantine-manifest-mismatch'
    }
    $sources = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $entries = @($Manifest.entries)
    if ($entries.Count -gt 2) {
        throw 'quarantine-manifest-mismatch'
    }
    foreach ($entry in $entries) {
        Assert-QuarantineManifestEntry -Entry $entry -Sources $sources
    }
    if ((Get-QuarantineManifestChecksum -Manifest $Manifest) -cne [string]$Manifest.checksum_sha256) {
        throw 'quarantine-manifest-mismatch'
    }
    $manifestRotation = [Guid]::Empty
    $manifestDatabase = [Guid]::Empty
    if (-not [Guid]::TryParse([string]$Manifest.rotation_id, [ref]$manifestRotation) -or
        -not [Guid]::TryParse([string]$Manifest.database_id, [ref]$manifestDatabase) -or
        $manifestRotation -ne [Guid]$RotationId -or $manifestDatabase -ne [Guid]$DatabaseId) {
        throw 'quarantine-manifest-binding-mismatch'
    }
}

function Read-QuarantineManifest {
    param([string]$Path, [string]$RotationId, [string]$DatabaseId)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [PSCustomObject]@{
            schema_version = 1
            rotation_id = $RotationId
            database_id = $DatabaseId
            retention = $script:Retention
            entries = @()
            checksum_sha256 = ''
        }
    }
    Assert-SecureAcl -Path $Path
    $manifest = [IO.File]::ReadAllText($Path) | ConvertFrom-Json
    Assert-QuarantineManifest -Manifest $manifest -RotationId $RotationId -DatabaseId $DatabaseId
    return $manifest
}

function Write-QuarantineManifest {
    param($Manifest, [string]$Path, [string]$RotationId, [string]$DatabaseId)

    $Manifest.checksum_sha256 = Get-QuarantineManifestChecksum -Manifest $Manifest
    Assert-QuarantineManifest -Manifest $Manifest -RotationId $RotationId -DatabaseId $DatabaseId
    $json = $Manifest | ConvertTo-Json -Depth 8
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($json)
    try {
        Publish-RotationSecureBytes -Bytes $bytes -DestinationPath $Path -BackupPath "$Path.previous"
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Publish-QuarantineSource {
    param([string]$SourcePath, [string]$SourceLabel, [string]$DestinationPath)

    $null = Assert-SinglePhysicalFile -Path $SourcePath
    $source = Get-Item -LiteralPath $SourcePath
    $digest = Get-FileSha256 -Path $SourcePath
    if (-not (Test-Path -LiteralPath $DestinationPath)) {
        $sourceBytes = [IO.File]::ReadAllBytes($SourcePath)
        try {
            $crashDuringCopy = (
                $SourceLabel -ceq '.env' -and
                $script:InternalCrashpoint -ceq 'crash_during_root_quarantine_copy'
            )
            Publish-RotationSecureBytes -Bytes $sourceBytes -DestinationPath $DestinationPath -CrashAfterPartialWrite:$crashDuringCopy
        } finally {
            [Array]::Clear($sourceBytes, 0, $sourceBytes.Length)
        }
    }
    $null = Assert-SinglePhysicalFile -Path $DestinationPath
    Assert-SecureAcl -Path $DestinationPath
    $destination = Get-Item -LiteralPath $DestinationPath
    if ($destination.Length -ne $source.Length -or
        (Get-FileSha256 -Path $DestinationPath) -cne $digest) {
        throw 'quarantine-copy-mismatch'
    }
    if ($SourceLabel -ceq '.env' -and
        $script:InternalCrashpoint -ceq 'crash_after_root_quarantine_finalize') {
        [Diagnostics.Process]::GetCurrentProcess().Kill()
        [Environment]::Exit(95)
    }
    Remove-Item -LiteralPath $SourcePath -Force
    return [PSCustomObject]@{ size = $source.Length; sha256 = $digest }
}

function New-QuarantineEntry {
    param([string]$SourceLabel, [long]$Size, [string]$Sha256)

    return [PSCustomObject]@{
        source = $SourceLabel
        category = 'environment'
        size = $Size
        sha256 = $Sha256
        moved_at = [DateTimeOffset]::Now.ToString('o')
        retention = $script:Retention
    }
}

function Copy-EnvironmentToQuarantine {
    param(
        [string]$SourcePath,
        [string]$SourceLabel,
        [string]$DestinationPath,
        [string]$ManifestPath,
        [string]$RotationId,
        [string]$DatabaseId
    )

    $manifest = Read-QuarantineManifest -Path $ManifestPath -RotationId $RotationId -DatabaseId $DatabaseId
    $existing = @($manifest.entries | Where-Object { $_.source -ceq $SourceLabel })
    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
        if ($existing.Count -eq 1) {
            $source = Get-Item -LiteralPath $SourcePath
            if ([long]$existing[0].size -ne $source.Length -or
                [string]$existing[0].sha256 -cne (Get-FileSha256 -Path $SourcePath)) {
                throw 'quarantine-manifest-mismatch'
            }
        }
        $published = Publish-QuarantineSource -SourcePath $SourcePath -SourceLabel $SourceLabel -DestinationPath $DestinationPath
        if ($existing.Count -eq 0) {
            $entry = New-QuarantineEntry -SourceLabel $SourceLabel -Size $published.size -Sha256 $published.sha256
            $manifest.entries = @($manifest.entries) + @($entry)
            Write-QuarantineManifest -Manifest $manifest -Path $ManifestPath -RotationId $RotationId -DatabaseId $DatabaseId
        }
    } elseif ((Test-Path -LiteralPath $DestinationPath -PathType Leaf) -and $existing.Count -eq 0) {
        Assert-SecureAcl -Path $DestinationPath
        $destination = Get-Item -LiteralPath $DestinationPath
        $entry = New-QuarantineEntry -SourceLabel $SourceLabel -Size $destination.Length -Sha256 (Get-FileSha256 -Path $DestinationPath)
        $manifest.entries = @($manifest.entries) + @($entry)
        Write-QuarantineManifest -Manifest $manifest -Path $ManifestPath -RotationId $RotationId -DatabaseId $DatabaseId
    } elseif (-not (Test-Path -LiteralPath $DestinationPath -PathType Leaf)) {
        throw 'env-source-missing'
    }
    if (@($manifest.entries | Where-Object { $_.source -ceq $SourceLabel }).Count -ne 1) {
        throw 'quarantine-manifest-mismatch'
    }
}

function Read-ValidatedQuarantineManifest {
    param([string]$Path, [string]$RotationId, [string]$DatabaseId)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'quarantine-manifest-mismatch'
    }
    return Read-QuarantineManifest -Path $Path -RotationId $RotationId -DatabaseId $DatabaseId
}

Export-ModuleMember -Function @(
    'Initialize-RotationQuarantine',
    'Copy-EnvironmentToQuarantine',
    'Read-ValidatedQuarantineManifest'
)
