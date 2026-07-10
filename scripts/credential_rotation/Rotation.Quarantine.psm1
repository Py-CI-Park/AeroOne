Set-StrictMode -Version Latest

$script:Retention = ''
$script:Failpoint = ''

function Initialize-RotationQuarantine {
    param([string]$Retention, [string]$Failpoint)

    $script:Retention = $Retention
    $script:Failpoint = $Failpoint
}

function Read-QuarantineManifest {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [PSCustomObject]@{
            version = 1
            retention = $script:Retention
            entries = @()
        }
    }
    Assert-SecureAcl -Path $Path
    return [IO.File]::ReadAllText($Path) | ConvertFrom-Json
}

function Write-QuarantineManifest {
    param($Manifest, [Parameter(Mandatory = $true)][string]$Path)

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
                $script:Failpoint -ceq 'crash_during_root_quarantine_copy'
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
        $script:Failpoint -ceq 'crash_after_root_quarantine_finalize') {
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
        [string]$ManifestPath
    )

    $manifest = Read-QuarantineManifest -Path $ManifestPath
    $existing = @($manifest.entries | Where-Object { $_.source -ceq $SourceLabel })
    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
        $published = Publish-QuarantineSource -SourcePath $SourcePath -SourceLabel $SourceLabel -DestinationPath $DestinationPath
        if ($existing.Count -ne 0) {
            throw 'quarantine-manifest-mismatch'
        }
        $entry = New-QuarantineEntry -SourceLabel $SourceLabel -Size $published.size -Sha256 $published.sha256
        $manifest.entries = @($manifest.entries) + @($entry)
        Write-QuarantineManifest -Manifest $manifest -Path $ManifestPath
    } elseif ((Test-Path -LiteralPath $DestinationPath -PathType Leaf) -and $existing.Count -eq 0) {
        Assert-SecureAcl -Path $DestinationPath
        $destination = Get-Item -LiteralPath $DestinationPath
        $entry = New-QuarantineEntry -SourceLabel $SourceLabel -Size $destination.Length -Sha256 (Get-FileSha256 -Path $DestinationPath)
        $manifest.entries = @($manifest.entries) + @($entry)
        Write-QuarantineManifest -Manifest $manifest -Path $ManifestPath
    } elseif (-not (Test-Path -LiteralPath $DestinationPath -PathType Leaf)) {
        throw 'env-source-missing'
    }
    if (@($manifest.entries | Where-Object { $_.source -ceq $SourceLabel }).Count -ne 1) {
        throw 'quarantine-manifest-mismatch'
    }
}

Export-ModuleMember -Function @(
    'Initialize-RotationQuarantine',
    'Copy-EnvironmentToQuarantine'
)
