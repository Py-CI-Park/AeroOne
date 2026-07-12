Set-StrictMode -Version Latest

function New-RotationTransactionProcess {
    param([string]$PythonPath, [string]$WorkingDirectory)

    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonPath
    $startInfo.Arguments = '-m app.commands.credential_rotation_transaction'
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['PYTHONPATH'] = $WorkingDirectory
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'python-start-failed'
    }
    return $process
}

function Write-RotationTransactionFrame {
    param([Parameter(Mandatory = $true)]$Process, [Parameter(Mandatory = $true)]$Frame)

    $json = $Frame | ConvertTo-Json -Compress
    $Process.StandardInput.WriteLine($json)
    $Process.StandardInput.Flush()
}

function Start-RotationDatabaseTransaction {
    param(
        [string]$PythonPath,
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][hashtable]$Request
    )

    $process = New-RotationTransactionProcess -PythonPath $PythonPath -WorkingDirectory $WorkingDirectory
    Write-RotationTransactionFrame -Process $process -Frame $Request
    $line = $process.StandardOutput.ReadLine()
    if ([string]::IsNullOrWhiteSpace($line)) {
        $process.StandardInput.Close()
        $process.WaitForExit()
        $process.Dispose()
        throw 'python-transaction-failed'
    }
    $ready = $line | ConvertFrom-Json
    if ($ready.status -eq 'already_committed') {
        $process.StandardInput.Close()
        $null = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $exitCode = $process.ExitCode
        $process.Dispose()
        if ($exitCode -ne 0) {
            throw 'python-transaction-failed'
        }
        return [PSCustomObject]@{
            process = $null
            ready = $ready
            already_committed = $true
            committed = $ready
        }
    }
    if ($ready.status -ne 'ready') {
        $process.StandardInput.Close()
        $process.WaitForExit()
        $code = if ($ready.status -eq 'error' -and $ready.code -match '^[a-z-]+$') {
            "python-$($ready.code)"
        } else {
            'python-transaction-failed'
        }
        $process.Dispose()
        throw $code
    }
    return [PSCustomObject]@{
        process = $process
        ready = $ready
        already_committed = $false
        committed = $null
    }
}

function Complete-RotationDatabaseTransaction {
    param([Parameter(Mandatory = $true)]$Transaction)

    $process = $Transaction.process
    if ($null -eq $process) {
        return $Transaction.committed
    }
    Write-RotationTransactionFrame -Process $process -Frame @{ action = 'commit' }
    $process.StandardInput.Close()
    $line = $process.StandardOutput.ReadLine()
    $null = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $response = if ([string]::IsNullOrWhiteSpace($line)) { $null } else { $line | ConvertFrom-Json }
    $exitCode = $process.ExitCode
    $process.Dispose()
    if ($exitCode -ne 0) {
        if ($null -ne $response -and $response.status -eq 'error' -and $response.code -match '^[a-z-]+$') {
            throw "python-$($response.code)"
        }
        throw 'python-transaction-failed'
    }
    if ($null -eq $response -or $response.status -ne 'ok') {
        throw 'python-transaction-rejected'
    }
    return $response
}

function Stop-RotationDatabaseTransaction {
    param($Transaction)

    if ($null -eq $Transaction -or $null -eq $Transaction.process) {
        return
    }
    $process = $Transaction.process
    if (-not $process.HasExited) {
        $process.StandardInput.Close()
        if (-not $process.WaitForExit(5000)) {
            $process.Kill()
            $process.WaitForExit()
        }
    }
    $process.Dispose()
}

function Start-RotationRestoreGuard {
    param(
        [string]$PythonPath,
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][hashtable]$Request
    )

    $process = New-RotationTransactionProcess -PythonPath $PythonPath -WorkingDirectory $WorkingDirectory
    Write-RotationTransactionFrame -Process $process -Frame $Request
    $line = $process.StandardOutput.ReadLine()
    if ([string]::IsNullOrWhiteSpace($line)) {
        $process.StandardInput.Close()
        $process.WaitForExit()
        $process.Dispose()
        throw 'python-restore-guard-failed'
    }
    $ready = $line | ConvertFrom-Json
    if ($ready.status -ne 'restore_guard_ready') {
        $process.StandardInput.Close()
        $process.WaitForExit()
        $code = if ($ready.status -eq 'error' -and $ready.code -match '^[a-z-]+$') {
            "python-$($ready.code)"
        } else {
            'python-restore-guard-failed'
        }
        $process.Dispose()
        throw $code
    }
    return [PSCustomObject]@{ process = $process }
}

function Complete-RotationRestoreGuard {
    param([Parameter(Mandatory = $true)]$Guard)

    $process = $Guard.process
    Write-RotationTransactionFrame -Process $process -Frame @{ action = 'archive_complete' }
    $process.StandardInput.Close()
    $line = $process.StandardOutput.ReadLine()
    $null = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $response = if ([string]::IsNullOrWhiteSpace($line)) { $null } else { $line | ConvertFrom-Json }
    $exitCode = $process.ExitCode
    $process.Dispose()
    $Guard.process = $null
    if ($exitCode -ne 0) {
        if ($null -ne $response -and $response.status -eq 'error' -and $response.code -match '^[a-z-]+$') {
            throw "python-$($response.code)"
        }
        throw 'python-restore-guard-failed'
    }
    if ($null -eq $response -or $response.status -ne 'archive_complete') {
        throw 'python-restore-guard-rejected'
    }
}

function Stop-RotationRestoreGuard {
    param($Guard)

    if ($null -eq $Guard) {
        return
    }
    Stop-RotationDatabaseTransaction -Transaction $Guard
}

Export-ModuleMember -Function @(
    'Start-RotationDatabaseTransaction',
    'Complete-RotationDatabaseTransaction',
    'Stop-RotationDatabaseTransaction',
    'Start-RotationRestoreGuard',
    'Complete-RotationRestoreGuard',
    'Stop-RotationRestoreGuard'
)
