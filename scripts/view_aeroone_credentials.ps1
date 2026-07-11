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
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Configuration.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Runtime.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.PythonCommand.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.Clipboard.psm1') -Force -DisableNameChecking
Import-Module (Join-Path $PSScriptRoot 'credential_rotation\Rotation.CredentialViewer.psm1') -Force -DisableNameChecking

try {
    $configuration = New-RotationConfiguration `
        -ScriptDirectory $PSScriptRoot `
        -ScriptPath $PSCommandPath `
        -ExpectedEntryPoint 'scripts\view_aeroone_credentials.ps1' `
        -TestMode ([bool]$TestMode) `
        -TestWorkspaceRoot $TestWorkspaceRoot `
        -PythonOverride ''
    Initialize-RotationRuntime -Configuration $configuration.Runtime
    Initialize-RotationPythonCommand -Configuration $configuration.Runtime
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
