#Requires -Version 5.1
<#
.SYNOPSIS
    Builds one internal data bundle envelope (.p7m): verifies two
    already-produced detached signatures over an approval, assembles the
    inner ZIP (approval + signatures + inventory + approved content), and
    encrypts it for the recipient with EnvelopedCms AES-256-CBC.

.DESCRIPTION
    This builder NEVER signs anything itself and NEVER touches a private
    signing key -- it only verifies the two .p7s files produced independently
    by Sign-AeroOneInternalApproval.ps1 (dual role: distinct signers, roles
    matching the bundle type). It never sets a public-data flag and never
    writes to a repo/dist/GitHub output path; -OutputPath MUST point at an
    internal distribution location supplied by the caller.

    All business-rule boundary decisions (approval schema/TTL/roots,
    dual-role signer separation, recipient/environment match, trust-policy
    digest pin, envelope entry containment) are delegated to the Python
    boundary layer via --rpc so the decision logic stays covered by
    backend/tests/unit/test_internal_data_bundle.py.

.PARAMETER ApprovalPath
    Raw approval bytes (exact bytes that were signed).

.PARAMETER SignaturePaths
    Exactly two .p7s files produced by Sign-AeroOneInternalApproval.ps1.

.PARAMETER InventoryPath
    inventory.json whose SHA-256 must equal approval.source_inventory_sha256.

.PARAMETER ContentRoot
    Directory containing one subdirectory per approved root (e.g.
    civil_aircraft/, document/) with the approved content to bundle. Only
    entries whose top-level directory is in the approval's allowed_roots are
    included; anything else aborts the build.

.PARAMETER TrustPolicyPath / PinnedTrustPolicySha256
    The already-installed, registry-pinned trust policy and its pinned
    digest (as read from the registry by the caller), used to map signer
    thumbprints to roles and to look up the recipient's expected EKU/subject.

.PARAMETER RecipientCertStoreLocation / RecipientCertStoreName
    Adapter parameters so tests never touch Cert:\LocalMachine\My. The
    recipient's certificate is looked up by thumbprint (public key only is
    used here for encryption; the private key is not required to build).

.PARAMETER OutputPath
    Destination .p7m path -- an internal distribution location, never a
    repo/dist/GitHub output path.

.PARAMETER PythonExecutable / WorkspaceRoot
    Used to invoke the Python boundary-validation RPC.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ApprovalPath,
    [Parameter(Mandatory = $true)][ValidateCount(2, 2)][string[]]$SignaturePaths,
    [Parameter(Mandatory = $true)][string]$InventoryPath,
    [Parameter(Mandatory = $true)][string]$ContentRoot,
    [Parameter(Mandatory = $true)][string]$TrustPolicyPath,
    [Parameter(Mandatory = $true)][string]$PinnedTrustPolicySha256,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$RecipientCertStoreLocation = 'LocalMachine',
    [string]$RecipientCertStoreName = 'My',
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [string[]]$TrustedRootThumbprints = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Security

$script:DocumentSigningEkuOid = '1.3.6.1.4.1.311.10.3.12'
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
            throw 'certificate-not-found'
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
        return $true  # organizational ambient trust; provisioning is out of scope here
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

# --- Load and RPC-validate the approval -------------------------------------
$approvalBytes = [IO.File]::ReadAllBytes($ApprovalPath)
$approvalRequest = @{
    action      = 'parse_approval'
    raw_base64  = [Convert]::ToBase64String($approvalBytes)
}
$approvalResult = Invoke-InternalDataBundleRpc -Request $approvalRequest
$approval = $approvalResult.approval
$bundleType = $approvalResult.bundle_type

# --- Trust policy: registry-pinned digest must match before it is trusted ---
$policyBytes = [IO.File]::ReadAllBytes($TrustPolicyPath)
$trustResult = Invoke-InternalDataBundleRpc -Request @{
    action              = 'validate_trust_policy'
    policy_raw_base64   = [Convert]::ToBase64String($policyBytes)
    pinned_sha256       = $PinnedTrustPolicySha256
    approval            = $approval
}
$policy = $trustResult.policy

# --- Verify both signatures (never sign here) -------------------------------
$signatureEvidence = @()
foreach ($signaturePath in $SignaturePaths) {
    $sigBytes = [IO.File]::ReadAllBytes($signaturePath)
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

# --- Recipient certificate (public key only needed to encrypt) --------------
$recipientCert = Get-AeroOneCertFromStore -Location $RecipientCertStoreLocation -StoreName $RecipientCertStoreName -Thumbprint $approval.recipient_thumbprint
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

# --- Inventory integrity ------------------------------------------------------
$inventoryBytes = [IO.File]::ReadAllBytes($InventoryPath)
Invoke-InternalDataBundleRpc -Request @{
    action                 = 'validate_inventory'
    inventory_raw_base64   = [Convert]::ToBase64String($inventoryBytes)
    approval                = $approval
} | Out-Null

# --- Assemble inner ZIP: approval + 2 signatures + inventory + content ------
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$stagingDirectory = Join-Path ([IO.Path]::GetTempPath()) ("aeroone-internal-data-build-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null
try {
    $innerZipPath = Join-Path $stagingDirectory 'inner.zip'
    if (Test-Path -LiteralPath $innerZipPath) {
        Remove-Item -LiteralPath $innerZipPath -Force
    }
    $zip = [IO.Compression.ZipFile]::Open($innerZipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $ApprovalPath, 'approval.json') | Out-Null
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $InventoryPath, 'inventory.json') | Out-Null
        foreach ($signaturePath in $SignaturePaths) {
            $signatureName = [IO.Path]::GetFileName($signaturePath)
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $signaturePath, $signatureName) | Out-Null
        }

        $allowedRoots = @($approval.allowed_roots)
        $contentFiles = Get-ChildItem -LiteralPath $ContentRoot -Recurse -File
        foreach ($file in $contentFiles) {
            $relative = $file.FullName.Substring($ContentRoot.TrimEnd('\', '/').Length + 1).Replace('\', '/')
            $topLevel = $relative.Split('/')[0]
            if ($allowedRoots -notcontains $topLevel) {
                throw "content-outside-allowed-roots:$relative"
            }
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $relative) | Out-Null
        }
    } finally {
        $zip.Dispose()
    }

    $entryNames = @()
    $verifyZip = [IO.Compression.ZipFile]::OpenRead($innerZipPath)
    try {
        $entryNames = $verifyZip.Entries | ForEach-Object { $_.FullName }
    } finally {
        $verifyZip.Dispose()
    }
    Invoke-InternalDataBundleRpc -Request @{
        action        = 'validate_envelope_entries'
        entry_names   = @($entryNames)
        allowed_roots = $allowedRoots
    } | Out-Null

    # --- Encrypt inner ZIP for the recipient (EnvelopedCms, AES-256-CBC) ----
    $innerBytes = [IO.File]::ReadAllBytes($innerZipPath)
    $envelopeContentInfo = New-Object Security.Cryptography.Pkcs.ContentInfo(, $innerBytes)
    $envelopedCms = New-Object Security.Cryptography.Pkcs.EnvelopedCms(
        $envelopeContentInfo,
        (New-Object Security.Cryptography.Pkcs.AlgorithmIdentifier((New-Object Security.Cryptography.Oid($script:Aes256CbcOid))))
    )
    $recipientInfo = New-Object Security.Cryptography.Pkcs.CmsRecipient(
        [Security.Cryptography.Pkcs.SubjectIdentifierType]::IssuerAndSerialNumber,
        $recipientCert
    )
    $envelopedCms.Encrypt($recipientInfo)
    Invoke-InternalDataBundleRpc -Request @{
        action = 'validate_aes_oid'
        oid    = $script:Aes256CbcOid
    } | Out-Null

    $envelopeBytes = $envelopedCms.Encode()
    $outputDirectory = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory) -and -not (Test-Path -LiteralPath $outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }
    [IO.File]::WriteAllBytes($OutputPath, $envelopeBytes)
} finally {
    Remove-Item -LiteralPath $stagingDirectory -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output ([PSCustomObject]@{
    output_path  = $OutputPath
    bundle_type  = $bundleType
    request_id   = $approval.request_id
})
exit 0
