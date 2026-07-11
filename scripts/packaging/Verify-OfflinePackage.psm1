Set-StrictMode -Version Latest

# OS-layer helpers for the public offline-package fail-closed verifier
# (Task 5, AeroOne v1.13.0). This module owns only what Python cannot do on
# Windows: Authenticode signature checks and on-disk file existence. Policy,
# manifest, allow-list, and hash logic all live in
# backend\app\operations\package_policy_verifier.py, invoked here via
# packaging\verify_offline_package.py.
function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Value
    )
    $encoding = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($Path, $Value, $encoding)
}


function Get-AuthenticodeSignatureInfo {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [PSCustomObject]@{
            status     = 'FileNotFound'
            thumbprint = ''
            subject    = ''
        }
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    $thumbprint = ''
    $subject = ''
    if ($null -ne $signature.SignerCertificate) {
        $thumbprint = [string]$signature.SignerCertificate.Thumbprint
        $subject = [string]$signature.SignerCertificate.Subject
        if ($subject -match 'CN=([^,]+)') {
            $subject = $Matches[1]
        }
    }

    return [PSCustomObject]@{
        status     = [string]$signature.Status
        thumbprint = $thumbprint
        subject    = $subject
    }
}

function Get-RequiredInstallerSignatureMap {
    <#
      .SYNOPSIS
      Locates each required installer under a staging tree by filename and
      returns a hashtable of filename -> Authenticode signature info, ready
      to be serialized as the --signatures JSON for the Python verifier.
      Fails closed (throws) if any required installer file cannot be found.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$PolicyPath,

        [Parameter(Mandatory = $true)]
        [string]$StageRoot
    )

    $policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json
    $map = @{}

    foreach ($installer in $policy.required_installers) {
        $filename = [string]$installer.filename
        $matches = Get-ChildItem -LiteralPath $StageRoot -Recurse -File -Filter $filename -ErrorAction SilentlyContinue
        if (@($matches).Count -eq 0) {
            throw "installer-missing"
        }
        $candidate = $matches | Select-Object -First 1
        $map[$filename] = Get-AuthenticodeSignatureInfo -Path $candidate.FullName
    }

    return $map
}

function Invoke-OfflinePackagePreStageVerification {
    <#
      .SYNOPSIS
      OS-layer entry point: gathers Authenticode signatures for required
      installers, then delegates policy/manifest/hash verification to the
      Python CLI. Returns $true on pass; throws a redacted category-code
      exception on fail-closed rejection.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string]$StageRoot,
        [Parameter(Mandatory = $true)] [string]$ManifestPath,
        [Parameter(Mandatory = $true)] [string]$PolicyPath,
        [Parameter(Mandatory = $true)] [string]$Origin,
        [Parameter(Mandatory = $true)] [string]$Tag,
        [Parameter(Mandatory = $true)] [string]$Commit,
        [Parameter(Mandatory = $true)] [string]$PolicyLabel,
        [Parameter(Mandatory = $true)] [string]$DigestsOutPath,
        [string]$PythonExecutable = 'python'
    )

    $signatureMap = Get-RequiredInstallerSignatureMap -PolicyPath $PolicyPath -StageRoot $StageRoot
    $signaturesPath = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName() + '.json')
    try {
        Write-Utf8NoBom -Path $signaturesPath -Value ($signatureMap | ConvertTo-Json -Depth 4)

        $scriptPath = Join-Path $PSScriptRoot '..\..\packaging\verify_offline_package.py'
        $output = & $PythonExecutable $scriptPath pre-stage `
            --stage-root $StageRoot `
            --manifest $ManifestPath `
            --policy $PolicyPath `
            --origin $Origin `
            --tag $Tag `
            --commit $Commit `
            --policy-label $PolicyLabel `
            --signatures $signaturesPath `
            --digests-out $DigestsOutPath
        $exitCode = $LASTEXITCODE

        $result = $output | ConvertFrom-Json
        if ($exitCode -ne 0 -or -not $result.ok) {
            throw "package-policy-violation:$($result.code)"
        }
        return $true
    }
    finally {
        if (Test-Path -LiteralPath $signaturesPath) {
            Remove-Item -LiteralPath $signaturesPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-OfflinePackagePostZipVerification {
    <#
      .SYNOPSIS
      Post-ZIP entry point. Does not extract the archive: delegates to the
      Python CLI, which streams each entry's SHA-256 and compares it to the
      digest already Authenticode-verified at the pre-stage.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string]$ZipPath,
        [Parameter(Mandatory = $true)] [string]$ManifestPath,
        [Parameter(Mandatory = $true)] [string]$DigestsPath,
        [string]$PythonExecutable = 'python'
    )

    $scriptPath = Join-Path $PSScriptRoot '..\..\packaging\verify_offline_package.py'
    $output = & $PythonExecutable $scriptPath post-zip `
        --zip $ZipPath `
        --manifest $ManifestPath `
        --digests $DigestsPath
    $exitCode = $LASTEXITCODE

    $result = $output | ConvertFrom-Json
    if ($exitCode -ne 0 -or -not $result.ok) {
        throw "package-policy-violation:$($result.code)"
    }
    return $true
}

Export-ModuleMember -Function @(
    'Get-AuthenticodeSignatureInfo',
    'Get-RequiredInstallerSignatureMap',
    'Invoke-OfflinePackagePreStageVerification',
    'Invoke-OfflinePackagePostZipVerification'
)
