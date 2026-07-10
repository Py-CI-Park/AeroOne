[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$TestMode,
    [string]$TestWorkspaceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Security
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.PathSecurity.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Security.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Crypto.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Runtime.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.CredentialViewer.psm1') -Force -DisableNameChecking

$ProductRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

try {
    Initialize-RotationRuntime -Configuration @{
        TestMode = [bool]$TestMode
        TestWorkspaceRoot = $TestWorkspaceRoot
        ProductionWorkspace = 'D:\Chanil_Park\Project\Programming\AeroOne'
        ProductRoot = $ProductRoot
        ScriptPath = $PSCommandPath
    }
    $workspace = Get-WorkspaceRoot
    $credentialPath = Get-ExactCredentialViewerPath -WorkspaceRoot $workspace -TestMode ([bool]$TestMode)
    $bundle = Read-ValidatedCredentialViewerBundle -Path $credentialPath
    if ($ValidateOnly) {
        $bundle = $null
        return
    }
    if ([Threading.Thread]::CurrentThread.ApartmentState -ne [Threading.ApartmentState]::STA) {
        throw 'credential-viewer-sta-required'
    }
    Show-CredentialViewerWindow -Bundle $bundle
    $bundle = $null
} catch {
    $code = $_.Exception.Message
    if ($code -notmatch '^[a-z0-9_-]+$') {
        $code = 'credential-viewer-validation-failed'
    }
    [Console]::Error.WriteLine("status=error code=$code")
    exit 1
}
