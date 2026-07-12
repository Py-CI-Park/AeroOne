param(
    [string]$Repository = "Py-CI-Park/AeroOne",
    [string]$ContainedArchivePath = "dist/AeroOne-offline-1.12.2-20260708-081654.zip"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Net.Http

$script:RangeRequestCount = 0
$script:RangeBytesRead = [int64]0
$script:LocalRangeRequestCount = 0
$script:LocalRangeBytesRead = [int64]0
$script:Utf8 = [System.Text.UTF8Encoding]::new($false, $true)
$script:Cp437 = [System.Text.Encoding]::GetEncoding(437)

function Read-UInt16LE {
    param([byte[]]$Bytes, [int]$Offset)
    return [System.BitConverter]::ToUInt16($Bytes, $Offset)
}

function Read-UInt32LE {
    param([byte[]]$Bytes, [int]$Offset)
    return [System.BitConverter]::ToUInt32($Bytes, $Offset)
}

function Read-UInt64LE {
    param([byte[]]$Bytes, [int]$Offset)
    return [System.BitConverter]::ToUInt64($Bytes, $Offset)
}

function Get-RangeBytes {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [int64]$Start,
        [int64]$End
    )

    if ($Start -lt 0 -or $End -lt $Start) {
        throw "invalid byte range"
    }

    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::Get,
        $Url
    )
    $null = $request.Headers.TryAddWithoutValidation("Range", "bytes=$Start-$End")
    $response = $null

    try {
        $response = $Client.SendAsync(
            $request,
            [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
        ).GetAwaiter().GetResult()

        if ([int]$response.StatusCode -ne 206) {
            throw "range request rejected with HTTP $([int]$response.StatusCode)"
        }

        $contentRange = $response.Content.Headers.ContentRange
        if ($null -eq $contentRange -or
            -not $contentRange.HasRange -or
            [int64]$contentRange.From -ne $Start -or
            [int64]$contentRange.To -ne $End) {
            throw "invalid Content-Range response"
        }

        [byte[]]$bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $expectedLength = $End - $Start + 1
        if ($bytes.LongLength -ne $expectedLength) {
            throw "range response length mismatch"
        }

        $script:RangeRequestCount += 1
        $script:RangeBytesRead += $bytes.LongLength
        return $bytes
    }
    finally {
        if ($null -ne $response) {
            $response.Dispose()
        }
        $request.Dispose()
    }
}

function Get-LocalRangeBytes {
    param(
        [string]$Path,
        [int64]$Start,
        [int64]$End
    )

    if ($Start -lt 0 -or $End -lt $Start) {
        throw "invalid local byte range"
    }

    $length = $End - $Start + 1
    if ($length -gt [int]::MaxValue) {
        throw "local byte range exceeds supported size"
    }

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read
    )
    try {
        if ($End -ge $stream.Length) {
            throw "local byte range exceeds archive size"
        }
        $null = $stream.Seek($Start, [System.IO.SeekOrigin]::Begin)
        [byte[]]$bytes = [byte[]]::new([int]$length)
        $offset = 0
        while ($offset -lt $bytes.Length) {
            $read = $stream.Read($bytes, $offset, $bytes.Length - $offset)
            if ($read -eq 0) {
                throw "unexpected EOF in local range"
            }
            $offset += $read
        }
        $script:LocalRangeRequestCount += 1
        $script:LocalRangeBytesRead += $bytes.LongLength
        return $bytes
    }
    finally {
        $stream.Dispose()
    }
}

function Get-ArchiveRangeBytes {
    param(
        [AllowNull()][System.Net.Http.HttpClient]$Client,
        [AllowNull()][string]$Url,
        [AllowNull()][string]$LocalPath,
        [int64]$Start,
        [int64]$End
    )

    if ($null -ne $LocalPath -and $LocalPath -ne "") {
        return Get-LocalRangeBytes $LocalPath $Start $End
    }
    if ($null -eq $Client -or [string]::IsNullOrWhiteSpace($Url)) {
        throw "HTTP range source is incomplete"
    }
    return Get-RangeBytes $Client $Url $Start $End
}

function Get-CategoryCounts {
    param(
        [byte[]]$CentralDirectory,
        [uint64]$ExpectedEntries
    )

    $counts = [ordered]@{
        env = 0
        database = 0
        storage = 0
        backup = 0
        "agent-state" = 0
        "dev-artifact" = 0
    }
    $position = 0
    [uint64]$entryCount = 0

    while ($entryCount -lt $ExpectedEntries) {
        if ($position + 46 -gt $CentralDirectory.Length) {
            throw "truncated central-directory header"
        }
        if ((Read-UInt32LE $CentralDirectory $position) -ne 0x02014b50) {
            throw "invalid central-directory signature"
        }

        $flags = Read-UInt16LE $CentralDirectory ($position + 8)
        $nameLength = Read-UInt16LE $CentralDirectory ($position + 28)
        $extraLength = Read-UInt16LE $CentralDirectory ($position + 30)
        $commentLength = Read-UInt16LE $CentralDirectory ($position + 32)
        $recordLength = 46 + $nameLength + $extraLength + $commentLength

        if ($position + $recordLength -gt $CentralDirectory.Length) {
            throw "truncated central-directory record"
        }

        $encoding = if (($flags -band 0x0800) -ne 0) { $script:Utf8 } else { $script:Cp437 }
        $entryName = $encoding.GetString($CentralDirectory, $position + 46, $nameLength)
        $normalized = $entryName.Replace("\", "/").ToLowerInvariant()
        while ($normalized.StartsWith("./", [System.StringComparison]::Ordinal)) {
            $normalized = $normalized.Substring(2)
        }
        $normalized = $normalized.TrimStart([char]"/")
        $segments = @($normalized.Split("/") | Where-Object { $_ -ne "" })
        $baseName = if ($segments.Count -gt 0) { $segments[-1] } else { "" }

        if ($baseName.StartsWith(".env") -and $baseName -ne ".env.example") {
            $counts.env += 1
        }
        if ($segments -contains "_database" -or
            $normalized -match "(^|/)backend/data(/|$)" -or
            $baseName -match "\.(db|sqlite|sqlite3)(-(wal|shm))?$") {
            $counts.database += 1
        }
        if ($segments -contains "storage") {
            $counts.storage += 1
        }
        $isBackendData = $normalized -match "(^|/)backend/data(/|$)"
        $isBackupPath = $segments -contains "backup" -or $segments -contains "backups"
        $isBackendDataBackup = $isBackendData -and (
            $baseName -match "(^|[._-])backup([._-]|$)" -or $baseName -match "\.bak$"
        )
        if ($isBackupPath -or $isBackendDataBackup) {
            $counts.backup += 1
        }

        $agentSegments = @(".git", ".omc", ".omo", ".worktrees", ".codex", ".claude", ".agents")
        if (@($segments | Where-Object { $agentSegments -contains $_ }).Count -gt 0) {
            $counts["agent-state"] += 1
        }

        $devSegments = @(".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".turbo", ".cache")
        $hasDevSegment = @($segments | Where-Object { $devSegments -contains $_ }).Count -gt 0
        $hasNextCache = $normalized -match "(^|/)\.next/cache(/|$)"
        if ($hasDevSegment -or $hasNextCache -or $baseName -in @(".coverage", ".ds_store")) {
            $counts["dev-artifact"] += 1
        }

        $position += $recordLength
        $entryCount += 1
    }

    if ($position -lt $CentralDirectory.Length) {
        if ($position + 6 -gt $CentralDirectory.Length -or
            (Read-UInt32LE $CentralDirectory $position) -ne 0x05054b50) {
            throw "unexpected central-directory trailing bytes"
        }
        $signatureLength = Read-UInt16LE $CentralDirectory ($position + 4)
        if ($position + 6 + $signatureLength -ne $CentralDirectory.Length) {
            throw "invalid central-directory digital signature"
        }
    }

    return [pscustomobject]$counts
}

function Read-ZipCentralDirectory {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [int64]$ArchiveSize,
        [AllowNull()][string]$LocalPath = $null
    )

    $tailLength = [Math]::Min([int64]131072, $ArchiveSize)
    if ($tailLength -eq $ArchiveSize) {
        throw "archive is too small for central-directory-only policy"
    }

    $tailStart = $ArchiveSize - $tailLength
    [byte[]]$tail = Get-ArchiveRangeBytes $Client $Url $LocalPath $tailStart ($ArchiveSize - 1)
    $eocdIndex = -1

    for ($index = $tail.Length - 22; $index -ge 0; $index -= 1) {
        if ((Read-UInt32LE $tail $index) -ne 0x06054b50) {
            continue
        }
        $commentLength = Read-UInt16LE $tail ($index + 20)
        if ($index + 22 + $commentLength -eq $tail.Length) {
            $eocdIndex = $index
            break
        }
    }

    if ($eocdIndex -lt 0) {
        throw "EOCD not found"
    }

    $diskNumber = Read-UInt16LE $tail ($eocdIndex + 4)
    $directoryDisk = Read-UInt16LE $tail ($eocdIndex + 6)
    $entriesOnDisk16 = Read-UInt16LE $tail ($eocdIndex + 8)
    $totalEntries16 = Read-UInt16LE $tail ($eocdIndex + 10)
    $directorySize32 = Read-UInt32LE $tail ($eocdIndex + 12)
    $directoryOffset32 = Read-UInt32LE $tail ($eocdIndex + 16)

    if ($diskNumber -ne 0 -or $directoryDisk -ne 0) {
        throw "multi-disk ZIP is unsupported"
    }

    $usesZip64 = $entriesOnDisk16 -eq 0xffff -or
        $totalEntries16 -eq 0xffff -or
        $directorySize32 -eq 0xffffffff -or
        $directoryOffset32 -eq 0xffffffff

    [uint64]$totalEntries = $totalEntries16
    [uint64]$directorySize = $directorySize32
    [uint64]$directoryOffset = $directoryOffset32

    if ($usesZip64) {
        $locatorIndex = $eocdIndex - 20
        if ($locatorIndex -lt 0 -or (Read-UInt32LE $tail $locatorIndex) -ne 0x07064b50) {
            throw "ZIP64 locator not found"
        }
        $zip64Offset = Read-UInt64LE $tail ($locatorIndex + 8)
        if ($zip64Offset -gt [uint64]([int64]::MaxValue - 55)) {
            throw "ZIP64 EOCD offset exceeds supported range"
        }
        [byte[]]$zip64 = Get-ArchiveRangeBytes $Client $Url $LocalPath ([int64]$zip64Offset) ([int64]$zip64Offset + 55)
        if ((Read-UInt32LE $zip64 0) -ne 0x06064b50) {
            throw "ZIP64 EOCD signature mismatch"
        }
        if ((Read-UInt32LE $zip64 16) -ne 0 -or (Read-UInt32LE $zip64 20) -ne 0) {
            throw "multi-disk ZIP64 is unsupported"
        }
        $entriesOnDisk64 = Read-UInt64LE $zip64 24
        $totalEntries = Read-UInt64LE $zip64 32
        $directorySize = Read-UInt64LE $zip64 40
        $directoryOffset = Read-UInt64LE $zip64 48
        if ($entriesOnDisk64 -ne $totalEntries) {
            throw "ZIP64 split central directory is unsupported"
        }
    }
    elseif ($entriesOnDisk16 -ne $totalEntries16) {
        throw "split central directory is unsupported"
    }

    if ($directorySize -eq 0 -or $directorySize -gt 67108864) {
        throw "central-directory size is outside the 1..64 MiB safety bound"
    }
    if ($directoryOffset -gt [uint64]([int64]::MaxValue) -or
        $directorySize -gt [uint64]([int64]::MaxValue) -or
        $directoryOffset + $directorySize -gt [uint64]$ArchiveSize) {
        throw "central-directory range is outside archive bounds"
    }

    $directoryEnd = [int64]($directoryOffset + $directorySize - 1)
    [byte[]]$centralDirectory = Get-ArchiveRangeBytes $Client $Url $LocalPath ([int64]$directoryOffset) $directoryEnd
    $counts = Get-CategoryCounts $centralDirectory $totalEntries

    return [pscustomobject]@{
        entries = $totalEntries
        directory_bytes = $directorySize
        zip64 = $usesZip64
        category_counts = $counts
    }
}

$expected = @{
    "468959744" = @{ tag = "1.12.1"; sha = 468959745; verdict = "env/database/storage/agent-state/dev-artifact" }
    "467598771" = @{ tag = "1.12.0"; sha = 467598772; verdict = "env/database/storage/agent-state/dev-artifact" }
    "467141283" = @{ tag = "1.11.0"; sha = 467141282; verdict = "env/database/storage/agent-state/dev-artifact" }
    "466204038" = @{ tag = "1.10.0"; sha = 466204039; verdict = "env/database/storage/agent-state/dev-artifact" }
    "465087963" = @{ tag = "1.8.0"; sha = 465087964; verdict = "env/database/storage/agent-state/dev-artifact" }
    "463971385" = @{ tag = "1.7.1"; sha = 463971384; verdict = "env/database/storage/agent-state/dev-artifact" }
    "460314227" = @{ tag = "1.7.0"; sha = 460314229; verdict = "storage/agent-state/dev-artifact" }
    "460314230" = @{ tag = "1.7.0"; sha = 460314228; verdict = "storage/dev-artifact" }
    "451005119" = @{ tag = "1.6.2"; sha = 451005118; verdict = "storage/dev-artifact" }
    "449183210" = @{ tag = "1.6.1"; sha = 449183209; verdict = "env/database/storage/agent-state/dev-artifact" }
    "448898337" = @{ tag = "1.6.0"; sha = 448898338; verdict = "env/database/storage/agent-state/dev-artifact" }
    "448050524" = @{ tag = "1.5.0"; sha = 448050525; verdict = "storage/agent-state/dev-artifact" }
    "448050213" = @{ tag = "1.5.0"; sha = 448050212; verdict = "env/database/storage/agent-state/dev-artifact" }
    "445483030" = @{ tag = "1.4.4"; sha = 445483029; verdict = "storage/dev-artifact" }
}

$releaseJson = (& gh api --paginate "repos/$Repository/releases?per_page=100" | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw "gh release enumeration failed"
}
$parsedReleases = $releaseJson | ConvertFrom-Json
$releases = [System.Collections.Generic.List[object]]::new()
foreach ($parsedRelease in $parsedReleases) {
    $releases.Add($parsedRelease)
}

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $true
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(90)
$client.DefaultRequestHeaders.UserAgent.ParseAdd("AeroOne-central-directory-audit/1.0")

$records = [System.Collections.Generic.List[object]]::new()
$errors = [System.Collections.Generic.List[object]]::new()
$categoryOrder = @("env", "database", "storage", "backup", "agent-state", "dev-artifact")

try {
    foreach ($release in $releases) {
        $zipAssets = @($release.assets | Where-Object { $_.name.EndsWith(".zip", [System.StringComparison]::OrdinalIgnoreCase) })
        foreach ($asset in $zipAssets) {
            try {
                $audit = Read-ZipCentralDirectory $client $asset.browser_download_url ([int64]$asset.size) $null
                $presentCategories = @($categoryOrder | Where-Object { $audit.category_counts.$_ -gt 0 })
                $verdict = $presentCategories -join "/"
                $paired = @($release.assets | Where-Object { $_.name -eq "$($asset.name).sha256" })
                if ($paired.Count -ne 1) {
                    throw "paired SHA asset count is not one"
                }

                $records.Add([pscustomobject]@{
                    tag = $release.tag_name
                    zip_asset_id = [int64]$asset.id
                    sha_asset_id = [int64]$paired[0].id
                    zip_digest = $asset.digest
                    sha_digest = $paired[0].digest
                    verdict = $verdict
                    category_counts = $audit.category_counts
                    central_directory_entries = $audit.entries
                    central_directory_bytes = $audit.directory_bytes
                    zip64 = $audit.zip64
                })
            }
            catch {
                $errors.Add([pscustomobject]@{
                    tag = $release.tag_name
                    zip_asset_id = [int64]$asset.id
                    error_type = $_.Exception.GetType().FullName
                    error_message = $_.Exception.Message
                })
            }
        }
    }
}
finally {
    $client.Dispose()
    $handler.Dispose()
}

$mismatches = [System.Collections.Generic.List[string]]::new()
if ($releases.Count -ne 46) {
    $mismatches.Add("release_count")
}
if ($records.Count -ne 14) {
    $mismatches.Add("audited_zip_count")
}
if ($errors.Count -ne 0) {
    $mismatches.Add("audit_errors")
}

$actualIds = @($records | ForEach-Object { [string]$_.zip_asset_id } | Sort-Object)
$expectedIds = @($expected.Keys | Sort-Object)
if (($actualIds -join ",") -ne ($expectedIds -join ",")) {
    $mismatches.Add("unsafe_asset_id_set")
}

foreach ($record in $records) {
    $key = [string]$record.zip_asset_id
    if (-not $expected.ContainsKey($key)) {
        continue
    }
    $contract = $expected[$key]
    if ($record.tag -ne $contract.tag) {
        $mismatches.Add("tag:$key")
    }
    if ($record.sha_asset_id -ne $contract.sha) {
        $mismatches.Add("sha_pair:$key")
    }
    if ($record.verdict -ne $contract.verdict) {
        $mismatches.Add("verdict:$key")
    }
    if ($record.zip_digest -notmatch "^sha256:[0-9a-f]{64}$" -or
        $record.sha_digest -notmatch "^sha256:[0-9a-f]{64}$") {
        $mismatches.Add("digest:$key")
    }
}

$containedRelease = & gh api "repos/$Repository/releases/350620445" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "contained release verification failed"
}
$containedIds = @($containedRelease.assets | ForEach-Object { [int64]$_.id })
$containedPairAbsent = -not ($containedIds -contains 469662394) -and -not ($containedIds -contains 469662393)
if (-not $containedPairAbsent) {
    $mismatches.Add("task1_contained_pair")
}

$containedFile = Get-Item -LiteralPath $ContainedArchivePath
if ($containedFile.Length -ne 245667420) {
    $mismatches.Add("task1_local_size")
}
$containedAudit = Read-ZipCentralDirectory $null $null ([int64]$containedFile.Length) $containedFile.FullName
$containedCategories = @($categoryOrder | Where-Object { $containedAudit.category_counts.$_ -gt 0 })
$containedVerdict = $containedCategories -join "/"
if ($containedVerdict -ne "env/database/storage/agent-state/dev-artifact") {
    $mismatches.Add("task1_contained_verdict")
}
$containedRecord = [pscustomobject]@{
    tag = "1.12.2"
    zip_asset_id = 469662394
    sha_asset_id = 469662393
    zip_digest = "sha256:b67f595f0b33896015dfe1651f74d1f883de157094bf347bdf81f1d7d0c2e4cd"
    verdict = $containedVerdict
    category_counts = $containedAudit.category_counts
    central_directory_entries = $containedAudit.entries
    central_directory_bytes = $containedAudit.directory_bytes
    zip64 = $containedAudit.zip64
    source = "pre-existing local archive matched in Task 1"
}

$result = [ordered]@{
    release_count = $releases.Count
    remote_zip_asset_count = $records.Count + $errors.Count
    audited_zip_count = $records.Count
    audit_error_count = $errors.Count
    unsafe_remote_count = @($records | Where-Object { $_.verdict -ne "" }).Count
    safe_remote_count = @($records | Where-Object { $_.verdict -eq "" }).Count
    task1_contained_pair_absent = $containedPairAbsent
    planning_table_total_explained = $records.Count + $(if ($containedPairAbsent) { 1 } else { 0 })
    range_request_count = $script:RangeRequestCount
    range_bytes_read = $script:RangeBytesRead
    local_range_request_count = $script:LocalRangeRequestCount
    local_range_bytes_read = $script:LocalRangeBytesRead
    full_archive_download_count = 0
    entry_stream_read_count = 0
    raw_entry_name_output_count = 0
    mismatch_count = $mismatches.Count
    mismatches = @($mismatches)
    contained_record = $containedRecord
    records = @($records | Sort-Object tag, zip_asset_id)
    errors = @($errors)
}

$result | ConvertTo-Json -Depth 8 -Compress
if ($mismatches.Count -ne 0) {
    exit 2
}
