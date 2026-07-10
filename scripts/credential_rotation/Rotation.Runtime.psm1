Set-StrictMode -Version Latest

$script:Runtime = @{}

function Initialize-RotationRuntime {
    param([Parameter(Mandatory = $true)][hashtable]$Configuration)

    $script:Runtime = $Configuration.Clone()
}

function Get-WorkspaceRoot {
    if ($script:Runtime.TestMode) {
        $candidate = [IO.Path]::GetFullPath([string]$script:Runtime.TestWorkspaceRoot)
        $leaf = Split-Path -Leaf $candidate
        if ($leaf -notmatch '^aeroone-rotation-test-([a-f0-9]{32})$') {
            throw 'unknown-test-root'
        }
        $nonce = $Matches[1]
        $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not ($candidate + '\').StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'unknown-test-root'
        }
        $markerPath = Join-Path $candidate '.aeroone-rotation-test-root'
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
            throw 'unknown-test-root'
        }
        $null = Assert-SinglePhysicalFile -Path $markerPath
        if ([IO.File]::ReadAllText($markerPath) -cne "aeroone-rotation-test-v1:$nonce") {
            throw 'unknown-test-root'
        }
        $production = [IO.Path]::GetFullPath([string]$script:Runtime.ProductionWorkspace)
        if ($candidate.Equals($production.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
            throw 'unknown-test-root'
        }
        return $candidate.TrimEnd('\')
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$script:Runtime.TestWorkspaceRoot)) {
        throw 'test-root-forbidden'
    }
    $candidate = [IO.Path]::GetFullPath([string]$script:Runtime.ProductionWorkspace)
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw 'production-root-missing'
    }
    Assert-ProductionProvenance -WorkspaceRoot $candidate -ProductRoot $script:Runtime.ProductRoot -ScriptPath $script:Runtime.ScriptPath
    return $candidate.TrimEnd('\')
}

function Read-ExactEnv {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'env-missing'
    }
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) {
            continue
        }
        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            throw 'env-malformed'
        }
        $key = $line.Substring(0, $separator).Trim()
        if ($values.ContainsKey($key)) {
            throw 'env-duplicate-key'
        }
        $values[$key] = $line.Substring($separator + 1)
    }
    foreach ($required in $script:Runtime.RequiredKeys) {
        if (-not $values.ContainsKey($required) -or [string]::IsNullOrWhiteSpace($values[$required])) {
            throw 'env-required-key-missing'
        }
    }
    foreach ($key in $values.Keys) {
        if ($key -notin $script:Runtime.AllowedEnvironmentKeys) {
            throw 'unknown-env-key'
        }
    }
    return $values
}

function Resolve-CanonicalDatabase {
    param([string]$DatabaseUrl, [string]$WorkspaceRoot)

    if (-not $DatabaseUrl.StartsWith('sqlite:///', [StringComparison]::Ordinal)) {
        throw 'database-provider-forbidden'
    }
    $rawPath = $DatabaseUrl.Substring('sqlite:///'.Length).Replace('/', '\')
    $resolved = if ([IO.Path]::IsPathRooted($rawPath)) {
        [IO.Path]::GetFullPath($rawPath)
    } else {
        [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $rawPath))
    }
    $expected = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot 'backend\data\aeroone.db'))
    if (-not $resolved.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-path-forbidden'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw 'database-missing'
    }
    $workspaceIdentity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $databaseIdentity = Assert-SinglePhysicalFile -Path $resolved
    Assert-PhysicalContainment -RootIdentity $workspaceIdentity -ChildIdentity $databaseIdentity
    return $resolved
}

function Invoke-RotationPython {
    param([hashtable]$Request, [string]$WorkspaceRoot)

    $python = Join-Path $WorkspaceRoot 'backend\.venv\Scripts\python.exe'
    if ($script:Runtime.TestMode -and -not [string]::IsNullOrWhiteSpace($script:Runtime.PythonOverride)) {
        $python = [IO.Path]::GetFullPath([string]$script:Runtime.PythonOverride)
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'python-runtime-missing'
    }
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = '-m app.commands.rotate_credentials'
    $startInfo.WorkingDirectory = Join-Path $script:Runtime.ProductRoot 'backend'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['PYTHONPATH'] = $startInfo.WorkingDirectory
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'python-start-failed'
    }
    $requestBytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Request | ConvertTo-Json -Compress))
    $process.StandardInput.BaseStream.Write($requestBytes, 0, $requestBytes.Length)
    $process.StandardInput.BaseStream.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $null = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $response = if ([string]::IsNullOrWhiteSpace($stdout)) { $null } else { $stdout | ConvertFrom-Json }
    if ($process.ExitCode -ne 0) {
        if ($null -ne $response -and $response.status -eq 'error' -and $response.code -match '^[a-z-]+$') {
            throw "python-$($response.code)"
        }
        throw 'python-command-failed'
    }
    if ($null -eq $response -or $response.status -ne 'ok') {
        throw 'python-command-rejected'
    }
    return $response
}

Export-ModuleMember -Function @(
    'Initialize-RotationRuntime',
    'Get-WorkspaceRoot',
    'Read-ExactEnv',
    'Resolve-CanonicalDatabase',
    'Invoke-RotationPython'
)
