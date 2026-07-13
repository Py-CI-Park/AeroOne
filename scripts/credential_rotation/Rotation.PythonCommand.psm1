Set-StrictMode -Version Latest

$script:PythonCommandRuntime = @{}
$script:PythonCommandTimeoutMilliseconds = 60000
$script:PythonTerminationTimeoutMilliseconds = 5000

function Initialize-RotationPythonCommand {
    param([Parameter(Mandatory = $true)][hashtable]$Configuration)

    $script:PythonCommandRuntime = $Configuration.Clone()
}

function Stop-RotationPythonProcess {
    param([Parameter(Mandatory = $true)][Diagnostics.Process]$Process)

    if ($Process.HasExited) {
        return
    }
    $Process.Kill()
    if (-not $Process.WaitForExit($script:PythonTerminationTimeoutMilliseconds)) {
        throw 'python-command-termination-timeout'
    }
}

function Invoke-RotationPython {
    param([hashtable]$Request, [string]$WorkspaceRoot)

    $python = Join-Path $WorkspaceRoot 'backend\.venv\Scripts\python.exe'
    if ($script:PythonCommandRuntime.TestMode -and
        -not [string]::IsNullOrWhiteSpace($script:PythonCommandRuntime.PythonOverride)) {
        $python = [IO.Path]::GetFullPath([string]$script:PythonCommandRuntime.PythonOverride)
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'python-runtime-missing'
    }
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = '-m app.commands.rotate_credentials'
    $startInfo.WorkingDirectory = Join-Path $script:PythonCommandRuntime.ProductRoot 'backend'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['PYTHONPATH'] = $startInfo.WorkingDirectory
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw 'python-start-failed'
        }
        $requestBytes = (New-Object Text.UTF8Encoding($false)).GetBytes(
            ($Request | ConvertTo-Json -Compress)
        )
        try {
            $process.StandardInput.BaseStream.Write($requestBytes, 0, $requestBytes.Length)
        } finally {
            [Array]::Clear($requestBytes, 0, $requestBytes.Length)
            $process.StandardInput.BaseStream.Close()
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($script:PythonCommandTimeoutMilliseconds)) {
            Stop-RotationPythonProcess -Process $process
            throw 'python-command-timeout'
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $null = $stderrTask.GetAwaiter().GetResult()
        $response = if ([string]::IsNullOrWhiteSpace($stdout)) {
            $null
        } else {
            $stdout | ConvertFrom-Json
        }
        if ($process.ExitCode -ne 0) {
            if ($null -ne $response -and
                $response.status -eq 'error' -and
                $response.code -match '^[a-z-]+$') {
                throw "python-$($response.code)"
            }
            throw 'python-command-failed'
        }
        if ($null -eq $response -or $response.status -ne 'ok') {
            throw 'python-command-rejected'
        }
        return $response
    } finally {
        Stop-RotationPythonProcess -Process $process
        $process.Dispose()
    }
}

Export-ModuleMember -Function @('Initialize-RotationPythonCommand', 'Invoke-RotationPython')
