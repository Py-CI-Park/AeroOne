#Requires -Version 5.1
<#
.SYNOPSIS
    Registers an already-authored internal data bundle trust policy: verifies
    every signer/recipient thumbprint it references already exists as an
    installed certificate, deploys the policy file with an exact 3-ACE ACL,
    and pins its SHA-256 digest in the registry.

.DESCRIPTION
    This script NEVER generates a certificate, private key, or CSR. It only
    verifies that certificates the policy references are already present in
    the target certificate stores (signers in CurrentUser\My with Document
    Signing EKU; recipients in LocalMachine\My with Email Protection EKU and
    a private key) and then locks the policy file down:
      - Owner: Administrators (or an injected equivalent for isolated tests).
      - Inheritance: disabled.
      - Exactly 3 ACEs: SYSTEM (Read), Administrators (Read), one authorized
        operator SID (Read). No broader ACL is written.
      - SHA-256 of the deployed policy bytes is written verbatim to the
        pinned registry value so tampering with the file on disk without
        updating the registry pin is detected as a mismatch (fail-closed).

.PARAMETER TrustPolicyPath
    Path to the trust policy JSON authored out-of-band (schema:
    packaging/internal-data-trust.schema.json).

.PARAMETER TrustPolicyDestination
    Where to deploy the policy. Production default is
    C:\ProgramData\AeroOne\trust\internal-data-trust.json. Tests MUST
    override this to an isolated path.

.PARAMETER RegistryKeyPath
    Registry key holding the pinned digest value. Production default is
    HKLM:\SOFTWARE\AeroOne\InternalData. Tests MUST override this to an
    isolated HKCU test path -- HKLM is never written by tests.

.PARAMETER AuthorizedOperatorSid
    The single additional (non-SYSTEM, non-Administrators) SID granted
    Read-only access to the deployed policy file.

.PARAMETER SignerCertStoreLocation / SignerCertStoreName
.PARAMETER RecipientCertStoreLocation / RecipientCertStoreName
    Adapter parameters so isolated tests never touch
    Cert:\CurrentUser\My / Cert:\LocalMachine\My.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TrustPolicyPath,
    [string]$TrustPolicyDestination = 'C:\ProgramData\AeroOne\trust\internal-data-trust.json',
    [string]$RegistryKeyPath = 'HKLM:\SOFTWARE\AeroOne\InternalData',
    [Parameter(Mandatory = $true)][string]$AuthorizedOperatorSid,
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$SignerCertStoreLocation = 'CurrentUser',
    [string]$SignerCertStoreName = 'My',
    [ValidateSet('CurrentUser', 'LocalMachine')][string]$RecipientCertStoreLocation = 'LocalMachine',
    [string]$RecipientCertStoreName = 'My',
    [string]$AdministratorsSid = 'S-1-5-32-544',
    [string]$SystemSid = 'S-1-5-18'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:DocumentSigningEkuOid = '1.3.6.1.4.1.311.10.3.12'
$script:EmailProtectionEkuOid = '1.3.6.1.5.5.7.3.4'

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
            throw 'certificate-not-installed'
        }
        return $matches[0]
    } finally {
        $store.Close()
    }
}

function Test-EkuPresent {
    param([Security.Cryptography.X509Certificates.X509Certificate2]$Certificate, [string]$ExpectedOid)

    $ekuExtension = $Certificate.Extensions |
        Where-Object { $_.Oid.Value -eq '2.5.29.37' } |
        Select-Object -First 1
    if ($null -eq $ekuExtension) {
        return $false
    }
    $eku = [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ekuExtension
    return (($eku.EnhancedKeyUsages | ForEach-Object { $_.Value }) -contains $ExpectedOid)
}

if (-not (Test-Path -LiteralPath $TrustPolicyPath -PathType Leaf)) {
    throw 'trust-policy-not-found'
}

$policyBytes = [IO.File]::ReadAllBytes($TrustPolicyPath)
$policyText = (New-Object Text.UTF8Encoding($false)).GetString($policyBytes)
$policy = $policyText | ConvertFrom-Json

foreach ($signer in $policy.signers) {
    $cert = Get-AeroOneCertFromStore -Location $SignerCertStoreLocation -StoreName $SignerCertStoreName -Thumbprint $signer.thumbprint
    if (-not (Test-EkuPresent -Certificate $cert -ExpectedOid $script:DocumentSigningEkuOid)) {
        throw "signer-eku-mismatch:$($signer.role)"
    }
    $now = [DateTime]::UtcNow
    if ($now -lt $cert.NotBefore.ToUniversalTime() -or $now -gt $cert.NotAfter.ToUniversalTime()) {
        throw "signer-cert-validity:$($signer.role)"
    }
}

foreach ($recipient in $policy.recipients) {
    $cert = Get-AeroOneCertFromStore -Location $RecipientCertStoreLocation -StoreName $RecipientCertStoreName -Thumbprint $recipient.thumbprint
    if (-not (Test-EkuPresent -Certificate $cert -ExpectedOid $script:EmailProtectionEkuOid)) {
        throw "recipient-eku-mismatch:$($recipient.target_environment_id)"
    }
    if (-not $cert.HasPrivateKey) {
        throw "recipient-private-key-missing:$($recipient.target_environment_id)"
    }
    $now = [DateTime]::UtcNow
    if ($now -lt $cert.NotBefore.ToUniversalTime() -or $now -gt $cert.NotAfter.ToUniversalTime()) {
        throw "recipient-cert-validity:$($recipient.target_environment_id)"
    }
}

$destinationDirectory = Split-Path -Parent $TrustPolicyDestination
if (-not (Test-Path -LiteralPath $destinationDirectory)) {
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
}
[IO.File]::WriteAllBytes($TrustPolicyDestination, $policyBytes)

# Lock down to exactly 3 read-only ACEs with inheritance disabled.
$acl = Get-Acl -LiteralPath $TrustPolicyDestination
$acl.SetAccessRuleProtection($true, $false)
foreach ($existingRule in @($acl.Access)) {
    $acl.RemoveAccessRule($existingRule) | Out-Null
}
$readRight = [Security.AccessControl.FileSystemRights]::Read
$allow = [Security.AccessControl.AccessControlType]::Allow
foreach ($sid in @($SystemSid, $AdministratorsSid, $AuthorizedOperatorSid)) {
    $identity = New-Object Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, $readRight, $allow)
    $acl.AddAccessRule($rule)
}
$acl.SetOwner((New-Object Security.Principal.SecurityIdentifier($AdministratorsSid)))
Set-Acl -LiteralPath $TrustPolicyDestination -AclObject $acl

$digest = (Get-FileHash -LiteralPath $TrustPolicyDestination -Algorithm SHA256).Hash.ToLowerInvariant()

if (-not (Test-Path -LiteralPath $RegistryKeyPath)) {
    New-Item -Path $RegistryKeyPath -Force | Out-Null
}
New-ItemProperty -Path $RegistryKeyPath -Name 'TrustPolicySha256' -Value $digest -PropertyType String -Force | Out-Null

Write-Output ([PSCustomObject]@{
    policy_id            = $policy.policy_id
    destination          = $TrustPolicyDestination
    trust_policy_sha256  = $digest
    registry_key_path    = $RegistryKeyPath
})
exit 0
