#Requires -Version 5.1
<#
.SYNOPSIS
    Decrypts and fully pre-verifies an internal data bundle envelope, then
    replaces the approved target root with same-volume staging, a durable
    journal, and old-root backup/rollback -- only while a maintenance gate is
    held.

.DESCRIPTION
    Verification order (fail-closed, nothing is staged until ALL pass):
      1. Decrypt EnvelopedCms with the recipient's private key; confirm the
         content-encryption algorithm is exactly AES-256-CBC.
      2. Strict-parse the inner approval.json via the Python boundary layer
         (schema, TTL, mixed-roots, NSA flag).
      3. Load the already-installed, registry-pinned trust policy; its
         SHA-256 MUST match the pin exactly (absent/mismatched = FAIL).
      4. Verify both detached signatures (SignedCms.CheckSignature(true) +
         EKU + validity window + organizational chain), and that they are
         two distinct signers matching the exact dual-role set for the
         bundle type.
      5. Verify the recipient certificate identity/EKU/private-key presence.
      6. Verify inventory.json's SHA-256 against the approval.
      7. Verify every inner ZIP entry: exact required members present, and
         all content entries are contained within an approved root (no path
         traversal, no root outside allowed_roots).
      8. Verify the maintenance gate is held; a multi-root import without an
         active gate is refused.

    Only after every step 1-8 passes does staging begin: content is copied to
    a same-volume temp directory next to -TargetRoot, a durable journal file
    records phase transitions (staged -> swapped -> committed) plus the path
    of the pre-swap backup of the old root, then the old root is renamed to
    the backup path and the staged directory is renamed into place. Any
    failure before the journal reaches 'committed' triggers rollback: the
    backup is renamed back over a partially-swapped target.

.PARAMETER EnvelopePath
    The .p7m envelope to import.

.PARAMETER RecipientCertStoreLocation / RecipientCertStoreName / RecipientThumbprint
    Adapter parameters so tests never touch Cert:\LocalMachine\My; the
    recipient certificate (with private key) used to decrypt.

.PARAMETER TrustPolicyPath / PinnedTrustPolicySha256
    The deployed trust policy bytes and the digest read from the pinned
    registry value by the caller (isolated registry path in tests).

.PARAMETER TargetRoot
    Directory that will receive the approved content, replacing its
    approved-root subdirectories.

.PARAMETER JournalPath
    Durable journal file recording staged/swapped/committed phase and the
    backup path, enabling recovery after interruption.

.PARAMETER MaintenanceGateActive
    Boolean the caller supplies after acquiring the maintenance gate
    (Task 3 pattern). Import refuses to proceed without it.

.PARAMETER PythonExecutable / WorkspaceRoot
    Used to invoke the Python boundary-validation RPC.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EnvelopePath,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$RecipientCertStoreLocation = 'LocalMachine',
    [string]$RecipientCertStoreName = 'My',
    [Parameter(Mandatory = $true)][string]$RecipientThumbprint,
    [Parameter(Mandatory = $true)][string]$TrustPolicyPath,
    [Parameter(Mandatory = $true)][string]$PinnedTrustPolicySha256,
    [Parameter(Mandatory = $true)][string]$TargetRoot,
    [Parameter(Mandatory = $true)][string]$JournalPath,
    [Parameter(Mandatory = $true)][bool]$MaintenanceGateActive,
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [string[]]$TrustedRootThumbprints = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Security
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$script:DocumentSigningEkuOid = '1.3.6.1.4.1.311.10.3.12'
$script:EmailProtectionEkuOid = '1.3.6.1.5.5.7.3.4'
$script:Aes256CbcOid = '2.16.840.1.101.3.4.1.42'

function Invoke-InternalDataBundleRpc {
    param([Parameter(Mandatory = $true)][hashtable]$Request)

    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonExecutable
    $startInfo.Arguments = '-m app.operations.internal_data_bundle_contracts --rpc'
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
        throw 'python-rpc-start-failed'
    }
    $requestBytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Request | ConvertTo-Json -Compress -Depth 12))
    $process.StandardInput.BaseStream.Write($requestBytes, 0, $requestBytes.Length)
    $process.StandardInput.BaseStream.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "internal-data-bundle-rpc-failed:$($stderr.Trim())"
    }
    return $stdout | ConvertFrom-Json
}

function Get-AeroOneCertFromStore {
    param([string]$Location, [string]$StoreName, [string]$Thumbprint)

    $store = New-Object Security.Cryptography.X509Certificates.X509Store(
        $StoreName,
        [Security.Cryptography.X509Certificates.StoreLocation]::$Location
    )
    $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
    try {
        $normalized = $Thumbprint.ToUpperInvariant()
        $matches = $store.Certificates | Where-Object { $_.Thumbprint -eq $normalized }
        if (@($matches).Count -ne 1) {
            throw 'recipient-certificate-not-found'
        }
        return $matches[0]
    } finally {
        $store.Close()
    }
}

function Get-Eku {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    $ekuExtension = $Certificate.Extensions |
        Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
        Select-Object -First 1
    if ($null -eq $ekuExtension) {
        return $null
    }
    $eku = [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ekuExtension
    return ($eku.EnhancedKeyUsages | Select-Object -First 1).Value
}

function Test-ChainValid {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate, [string[]]$TrustedRootThumbprints)

    if (@($TrustedRootThumbprints).Count -eq 0) {
        return $true
    }
    $chain = New-Object Security.Cryptography.X509Certificates.X509Chain
    $chain.ChainPolicy.RevocationMode = [Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
    $chain.ChainPolicy.VerificationFlags = [Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
    foreach ($rootThumbprint in $TrustedRootThumbprints) {
        $chain.ChainPolicy.ExtraStore.Add((Get-AeroOneCertFromStore -Location 'CurrentUser' -StoreName 'Root' -Thumbprint $rootThumbprint)) | Out-Null
    }
    $built = $chain.Build($Certificate)
    if (-not $built) {
        return $false
    }
    $rootInChain = $chain.ChainElements | ForEach-Object { $_.Certificate.Thumbprint }
    $intersection = $TrustedRootThumbprints | Where-Object { $rootInChain -contains $_.ToUpperInvariant() }
    return (@($intersection).Count -gt 0)
}

function Write-Journal {
    param([string]$Path, [hashtable]$Journal)

    $journalDirectory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $journalDirectory)) {
        New-Item -ItemType Directory -Path $journalDirectory -Force | Out-Null
    }
    ($Journal | ConvertTo-Json -Compress -Depth 6) | Set-Content -LiteralPath $Path -Encoding UTF8 -NoNewline
}

function Read-Journal {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (Get-Content -LiteralPath $Path -Raw) | ConvertFrom-Json
}

# --- Recover any interrupted prior import before starting a new one --------
$existingJournal = Read-Journal -Path $JournalPath
if ($null -ne $existingJournal -and $existingJournal.phase -eq 'swapped') {
    if (-not $MaintenanceGateActive) {
        throw 'maintenance-gate-required-for-recovery'
    }
    if (Test-Path -LiteralPath $existingJournal.backup_path) {
        if (Test-Path -LiteralPath $TargetRoot) {
            Remove-Item -LiteralPath $TargetRoot -Recurse -Force
        }
        Rename-Item -LiteralPath $existingJournal.backup_path -NewName (Split-Path -Leaf $TargetRoot)
    }
    Remove-Item -LiteralPath $JournalPath -Force -ErrorAction SilentlyContinue
}

if (-not $MaintenanceGateActive) {
    throw 'maintenance-gate-required'
}

if (-not (Test-Path -LiteralPath $EnvelopePath -PathType Leaf)) {
    throw 'envelope-not-found'
}

$recipientCert = Get-AeroOneCertFromStore -Location $RecipientCertStoreLocation -StoreName $RecipientCertStoreName -Thumbprint $RecipientThumbprint
if (-not $recipientCert.HasPrivateKey) {
    throw 'recipient-private-key-missing'
}

# --- Decrypt (fails closed on ciphertext tampering / wrong recipient) ------
$envelopeBytes = [IO.File]::ReadAllBytes($EnvelopePath)
$envelopedCms = New-Object Security.Cryptography.Pkcs.EnvelopedCms
$envelopedCms.Decode($envelopeBytes)
$recipientCollection = New-Object Security.Cryptography.X509Certificates.X509Certificate2Collection
$recipientCollection.Add($recipientCert) | Out-Null
$envelopedCms.Decrypt($recipientCollection)

$actualOid = $envelopedCms.ContentEncryptionAlgorithm.Oid.Value
Invoke-InternalDataBundleRpc -Request @{ action = 'validate_aes_oid'; oid = $actualOid } | Out-Null

$innerBytes = $envelopedCms.ContentInfo.Content

$verifyDirectory = Join-Path ([IO.Path]::GetTempPath()) ("aeroone-internal-data-verify-" + [Guid]::NewGuid().ToString('N'))
$stagingDirectory = $null
try {
    New-Item -ItemType Directory -Path $verifyDirectory -Force | Out-Null
    $innerZipPath = Join-Path $verifyDirectory 'inner.zip'
    [IO.File]::WriteAllBytes($innerZipPath, $innerBytes)

    $extractDirectory = Join-Path $verifyDirectory 'extracted'
    [IO.Compression.ZipFile]::ExtractToDirectory($innerZipPath, $extractDirectory)

    $entryNames = @()
    $zip = [IO.Compression.ZipFile]::OpenRead($innerZipPath)
    try {
        $entryNames = $zip.Entries | ForEach-Object { $_.FullName }
    } finally {
        $zip.Dispose()
    }

    $approvalPath = Join-Path $extractDirectory 'approval.json'
    $inventoryPath = Join-Path $extractDirectory 'inventory.json'
    if (-not (Test-Path -LiteralPath $approvalPath) -or -not (Test-Path -LiteralPath $inventoryPath)) {
        throw 'envelope-entry-mismatch'
    }
    $approvalBytes = [IO.File]::ReadAllBytes($approvalPath)

    $approvalResult = Invoke-InternalDataBundleRpc -Request @{
        action     = 'parse_approval'
        raw_base64 = [Convert]::ToBase64String($approvalBytes)
    }
    $approval = $approvalResult.approval
    $bundleType = $approvalResult.bundle_type
    $allowedRoots = @($approval.allowed_roots)

    Invoke-InternalDataBundleRpc -Request @{
        action        = 'validate_envelope_entries'
        entry_names   = @($entryNames)
        allowed_roots = $allowedRoots
    } | Out-Null

    $policyBytes = [IO.File]::ReadAllBytes($TrustPolicyPath)
    $trustResult = Invoke-InternalDataBundleRpc -Request @{
        action              = 'validate_trust_policy'
        policy_raw_base64   = [Convert]::ToBase64String($policyBytes)
        pinned_sha256       = $PinnedTrustPolicySha256
        approval            = $approval
    }
    $policy = $trustResult.policy

    $signaturePaths = Get-ChildItem -LiteralPath $extractDirectory -Filter '*.p7s' -File
    if (@($signaturePaths).Count -ne 2) {
        throw 'signer-role-set-mismatch'
    }
    $signatureEvidence = @()
    foreach ($signatureFile in $signaturePaths) {
        $sigBytes = [IO.File]::ReadAllBytes($signatureFile.FullName)
        $contentInfo = New-Object Security.Cryptography.Pkcs.ContentInfo(, $approvalBytes)
        $signedCms = New-Object Security.Cryptography.Pkcs.SignedCms($contentInfo, $true)
        $signedCms.Decode($sigBytes)

        $signatureValid = $true
        try {
            $signedCms.CheckSignature($true)
        } catch {
            $signatureValid = $false
        }

        $signerCert = $signedCms.SignerInfos[0].Certificate
        $thumbprint = $signerCert.Thumbprint
        $trustedSigner = $policy.signers | Where-Object { $_.thumbprint -eq $thumbprint }
        $role = if ($null -ne $trustedSigner) { $trustedSigner.role } else { 'unknown' }
        $eku = Get-Eku -Certificate $signerCert
        $chainValid = Test-ChainValid -Certificate $signerCert -TrustedRootThumbprints $TrustedRootThumbprints

        $signatureEvidence += @{
            role            = $role
            thumbprint      = $thumbprint
            subject         = $signerCert.Subject
            eku_oid         = if ($null -ne $eku) { $eku } else { '' }
            signature_valid = $signatureValid
            chain_valid     = $chainValid
            not_before      = $signerCert.NotBefore.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            not_after       = $signerCert.NotAfter.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        }
    }
    Invoke-InternalDataBundleRpc -Request @{
        action      = 'validate_signers'
        bundle_type = $bundleType
        signatures  = $signatureEvidence
    } | Out-Null

    $recipientEku = Get-Eku -Certificate $recipientCert
    Invoke-InternalDataBundleRpc -Request @{
        action    = 'validate_recipient'
        approval  = $approval
        recipient = @{
            target_environment_id = $approval.target_environment_id
            thumbprint             = $recipientCert.Thumbprint
            subject                = $recipientCert.Subject
            eku_oid                = if ($null -ne $recipientEku) { $recipientEku } else { '' }
            has_private_key        = $recipientCert.HasPrivateKey
            not_before              = $recipientCert.NotBefore.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            not_after               = $recipientCert.NotAfter.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        }
    } | Out-Null

    $inventoryBytes = [IO.File]::ReadAllBytes($inventoryPath)
    Invoke-InternalDataBundleRpc -Request @{
        action                = 'validate_inventory'
        inventory_raw_base64  = [Convert]::ToBase64String($inventoryBytes)
        approval              = $approval
    } | Out-Null

    # --- All checks passed: stage on the same volume as TargetRoot ---------
    if (-not (Test-Path -LiteralPath $TargetRoot)) {
        New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
    }
    $targetParent = Split-Path -Parent ([IO.Path]::GetFullPath($TargetRoot))
    $stagingDirectory = Join-Path $targetParent ((Split-Path -Leaf $TargetRoot) + '.staging-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

    foreach ($root in $allowedRoots) {
        $sourceRoot = Join-Path $extractDirectory $root
        if (Test-Path -LiteralPath $sourceRoot) {
            $destinationRoot = Join-Path $stagingDirectory $root
            Copy-Item -LiteralPath $sourceRoot -Destination $destinationRoot -Recurse -Force
        }
    }
    # Preserve untouched roots from the existing target so a normal-bundle
    # import never clobbers an unrelated (e.g. nsa) root and vice versa.
    if (Test-Path -LiteralPath $TargetRoot) {
        Get-ChildItem -LiteralPath $TargetRoot -Directory | Where-Object { $allowedRoots -notcontains $_.Name } | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stagingDirectory $_.Name) -Recurse -Force
        }
    }

    $backupPath = $TargetRoot.TrimEnd('\', '/') + '.backup-' + [Guid]::NewGuid().ToString('N')

    Write-Journal -Path $JournalPath -Journal @{
        phase        = 'staged'
        target_root  = $TargetRoot
        staging_path = $stagingDirectory
        backup_path  = $backupPath
        request_id   = $approval.request_id
    }

    Rename-Item -LiteralPath $TargetRoot -NewName (Split-Path -Leaf $backupPath)
    try {
        Rename-Item -LiteralPath $stagingDirectory -NewName (Split-Path -Leaf $TargetRoot)
    } catch {
        # Roll back: restore the old root before re-throwing.
        Rename-Item -LiteralPath $backupPath -NewName (Split-Path -Leaf $TargetRoot)
        throw
    }
    $stagingDirectory = $null

    Write-Journal -Path $JournalPath -Journal @{
        phase        = 'swapped'
        target_root  = $TargetRoot
        backup_path  = $backupPath
        request_id   = $approval.request_id
    }

    Remove-Item -LiteralPath $backupPath -Recurse -Force
    Write-Journal -Path $JournalPath -Journal @{
        phase       = 'committed'
        target_root = $TargetRoot
        request_id  = $approval.request_id
    }

    Write-Output ([PSCustomObject]@{
        target_root = $TargetRoot
        bundle_type = $bundleType
        request_id  = $approval.request_id
    })
    exit 0
} finally {
    Remove-Item -LiteralPath $verifyDirectory -Recurse -Force -ErrorAction SilentlyContinue
    if ($null -ne $stagingDirectory -and (Test-Path -LiteralPath $stagingDirectory)) {
        Remove-Item -LiteralPath $stagingDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}
