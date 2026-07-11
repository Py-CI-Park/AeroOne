#Requires -Version 5.1
<#
.SYNOPSIS
    Authors a single internal data bundle approval as raw UTF-8 JSON bytes
    with the exact field set, then round-trips it through the strict Python
    boundary parser (never ConvertFrom-Json alone) to prove it is acceptable
    before any signer is asked to sign it.

.PARAMETER RequestId / TicketId / Purpose / TargetEnvironmentId
    Free-form approval metadata (all required, non-empty).

.PARAMETER IssuedAt
    UTC issuance timestamp. Defaults to now.

.PARAMETER TtlHours
    Approval lifetime in hours; MUST be <= 24 (schema/policy enforced).

.PARAMETER RecipientThumbprint
    40-hex-char thumbprint of the recipient's Email Protection certificate.

.PARAMETER AllowedRoots
    Either a non-empty subset of {newsletter, civil_aircraft, document}
    (normal bundle) or exactly {nsa} (NSA bundle). Mixing is rejected by the
    strict parser round-trip below.

.PARAMETER InventoryPath
    Path to the inventory.json that will travel inside the bundle; its
    SHA-256 becomes source_inventory_sha256.

.PARAMETER OutputPath
    Destination for the raw approval bytes.

.PARAMETER PythonExecutable
    Path to the project's venv python.exe, used to run the strict boundary
    parser as the sole acceptance gate for the produced bytes.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RequestId,
    [Parameter(Mandatory = $true)][string]$TicketId,
    [Parameter(Mandatory = $true)][string]$Purpose,
    [Parameter(Mandatory = $true)][string]$TargetEnvironmentId,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$RecipientThumbprint,
    [Parameter(Mandatory = $true)][string[]]$AllowedRoots,
    [Parameter(Mandatory = $true)][string]$InventoryPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [DateTime]$IssuedAt = [DateTime]::UtcNow,
    [ValidateRange(1, 24)][int]$TtlHours = 24
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $InventoryPath -PathType Leaf)) {
    throw 'inventory-not-found'
}

$normalizedRoots = $AllowedRoots | Sort-Object -Unique
$includeNsa = ($normalizedRoots.Count -eq 1 -and $normalizedRoots[0] -eq 'nsa')
if (-not $includeNsa -and ($normalizedRoots -contains 'nsa')) {
    throw 'mixed-roots'
}

$inventoryBytes = [IO.File]::ReadAllBytes($InventoryPath)
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $inventoryDigest = [BitConverter]::ToString($sha.ComputeHash($inventoryBytes)).Replace('-', '').ToLowerInvariant()
} finally {
    $sha.Dispose()
}

$issuedAtUtc = $IssuedAt.ToUniversalTime()
$expiresAtUtc = $issuedAtUtc.AddHours($TtlHours)

# Field order matches packaging/internal-data-approval.schema.json exactly.
$approval = [Ordered]@{
    schema_version           = '1.0'
    request_id               = $RequestId
    ticket_id                = $TicketId
    purpose                  = $Purpose
    issued_at                = $issuedAtUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
    expires_at                = $expiresAtUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
    target_environment_id    = $TargetEnvironmentId
    recipient_thumbprint     = $RecipientThumbprint.ToUpperInvariant()
    allowed_roots            = @($normalizedRoots)
    source_inventory_sha256  = $inventoryDigest
    include_nsa              = $includeNsa
}

$json = $approval | ConvertTo-Json -Compress -Depth 6
$rawBytes = (New-Object Text.UTF8Encoding($false)).GetBytes($json)

# Strict boundary round-trip: ConvertFrom-Json is never the sole gate. The
# authored bytes must pass the duplicate-key-rejecting, additionalProperties
# =false Python parser before this script will emit them.
$startInfo = New-Object Diagnostics.ProcessStartInfo
$startInfo.FileName = $PythonExecutable
$startInfo.Arguments = '-m app.operations.internal_data_bundle_contracts'
$startInfo.WorkingDirectory = Join-Path $WorkspaceRoot 'backend'
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.EnvironmentVariables['PYTHONPATH'] = $startInfo.WorkingDirectory
$process = New-Object Diagnostics.Process
$process.StartInfo = $startInfo
if (-not $process.Start()) {
    throw 'python-boundary-parser-start-failed'
}
$process.StandardInput.BaseStream.Write($rawBytes, 0, $rawBytes.Length)
$process.StandardInput.BaseStream.Close()
$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()
if ($process.ExitCode -ne 0) {
    throw "approval-boundary-rejected:$($stderr.Trim())"
}
$null = $stdout | ConvertFrom-Json  # sanity parse of the already-approved canonical output

$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory) -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
[IO.File]::WriteAllBytes($OutputPath, $rawBytes)

Write-Output ([PSCustomObject]@{
    output_path              = $OutputPath
    request_id               = $RequestId
    include_nsa               = $includeNsa
    source_inventory_sha256  = $inventoryDigest
})
exit 0
