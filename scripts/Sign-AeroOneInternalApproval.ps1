#Requires -Version 5.1
<#
.SYNOPSIS
    Produces one detached SignedCms (.p7s) signature over the raw bytes of an
    AeroOne internal data bundle approval, for a single signer role.

.DESCRIPTION
    Run once per required role by the operator holding that role's already
    issued Document Signing certificate. Two independent operators (distinct
    physical signers) run this script separately -- once for
    'data_owner'/'nsa_data_owner' and once for 'security_officer' -- to
    produce the two .p7s files a bundle requires. This script never combines
    two roles into one signature and never persists a private key; it only
    invokes the already-provisioned certificate's signing operation via
    System.Security.Cryptography.Pkcs.SignedCms.

    Certificate requirements (fail closed, enforced here):
      - Located in -CertStoreLocation/-CertStoreName by -Thumbprint.
      - Enhanced Key Usage contains Document Signing (1.3.6.1.4.1.311.10.3.12).
      - Currently within its validity window.
      - Chain builds with RevocationMode=NoCheck, X509VerificationFlags=NoFlag,
        rooted in -TrustedRootThumbprints (isolated test roots for tests;
        organizational roots in production).

.PARAMETER ApprovalPath
    Path to the raw approval JSON bytes to sign (exact bytes, unmodified).

.PARAMETER Role
    One of: data_owner, nsa_data_owner, security_officer.

.PARAMETER Thumbprint
    Thumbprint (40 hex chars) of the already-issued signer certificate.

.PARAMETER OutputPath
    Destination for the detached SignedCms (.p7s) bytes.

.PARAMETER CertStoreLocation
    'CurrentUser' (production default) or overridable for isolated tests.

.PARAMETER CertStoreName
    Store name to open. Production default is 'My'. Tests MUST use an
    isolated, non-default store name (e.g. 'AeroOneInternalDataTest') so the
    real Cert:\CurrentUser\My store is never touched.

.PARAMETER TrustedRootThumbprints
    Thumbprints of CA certificates trusted as chain roots for this signer.
    Required so chain validation does not silently rely on the machine's
    ambient trust store.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ApprovalPath,
    [Parameter(Mandatory = $true)][ValidateSet('data_owner', 'nsa_data_owner', 'security_officer')][string]$Role,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$Thumbprint,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$CertStoreLocation = 'CurrentUser',
    [string]$CertStoreName = 'My',
    [Parameter(Mandatory = $true)][string[]]$TrustedRootThumbprints
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Security

$script:DocumentSigningEkuOid = '1.3.6.1.4.1.311.10.3.12'

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
            throw 'signer-certificate-not-found'
        }
        return $matches[0]
    } finally {
        $store.Close()
    }
}

function Assert-DocumentSigningEku {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    $ekuExtension = $Certificate.Extensions |
        Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
        Select-Object -First 1
    if ($null -eq $ekuExtension) {
        throw 'eku-mismatch'
    }
    $eku = [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ekuExtension
    $oids = $eku.EnhancedKeyUsages | ForEach-Object { $_.Value }
    if ($oids -notcontains $script:DocumentSigningEkuOid) {
        throw 'eku-mismatch'
    }
}

function Assert-CertificateValidityWindow {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate)

    $now = [DateTime]::UtcNow
    if ($now -lt $Certificate.NotBefore.ToUniversalTime()) {
        throw 'cert-not-yet-valid'
    }
    if ($now -gt $Certificate.NotAfter.ToUniversalTime()) {
        throw 'cert-expired'
    }
}

function Assert-CertificateChain {
    param(
        [Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,
        [string[]]$TrustedRootThumbprints
    )

    $chain = New-Object Security.Cryptography.X509Certificates.X509Chain
    $chain.ChainPolicy.RevocationMode = [Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
    $chain.ChainPolicy.VerificationFlags = [Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
    foreach ($rootThumbprint in $TrustedRootThumbprints) {
        # Isolated/organizational roots are supplied explicitly; the chain
        # engine still validates the cryptographic path to one of them.
        $chain.ChainPolicy.ExtraStore.Add((Get-AeroOneCertFromStore -Location 'CurrentUser' -StoreName 'Root' -Thumbprint $rootThumbprint)) | Out-Null
    }
    $built = $chain.Build($Certificate)
    if (-not $built) {
        throw 'chain-invalid'
    }
    $rootInChain = $chain.ChainElements | ForEach-Object { $_.Certificate.Thumbprint }
    $intersection = $TrustedRootThumbprints | Where-Object { $rootInChain -contains $_.ToUpperInvariant() }
    if (@($intersection).Count -eq 0) {
        throw 'chain-invalid'
    }
}

if (-not (Test-Path -LiteralPath $ApprovalPath -PathType Leaf)) {
    throw 'approval-not-found'
}

$rawBytes = [IO.File]::ReadAllBytes($ApprovalPath)
if ($rawBytes.Length -eq 0) {
    throw 'approval-empty'
}

$certificate = Get-AeroOneCertFromStore -Location $CertStoreLocation -StoreName $CertStoreName -Thumbprint $Thumbprint
Assert-DocumentSigningEku -Certificate $certificate
Assert-CertificateValidityWindow -Certificate $certificate
Assert-CertificateChain -Certificate $certificate -TrustedRootThumbprints $TrustedRootThumbprints
if (-not $certificate.HasPrivateKey) {
    throw 'signer-private-key-missing'
}

$contentInfo = New-Object Security.Cryptography.Pkcs.ContentInfo(, $rawBytes)
$signedCms = New-Object Security.Cryptography.Pkcs.SignedCms($contentInfo, $true)
$signer = New-Object Security.Cryptography.Pkcs.CmsSigner($certificate)
$signer.DigestAlgorithm = New-Object Security.Cryptography.Oid('2.16.840.1.101.3.4.2.1')  # SHA-256
$signer.IncludeOption = [Security.Cryptography.X509Certificates.X509IncludeOption]::EndCertOnly
$signedCms.ComputeSignature($signer, $false)

$signatureBytes = $signedCms.Encode()
$outputDirectory = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory) -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
[IO.File]::WriteAllBytes($OutputPath, $signatureBytes)

Write-Output ([PSCustomObject]@{
    role        = $Role
    thumbprint  = $certificate.Thumbprint
    subject     = $certificate.Subject
    output_path = $OutputPath
})
exit 0
