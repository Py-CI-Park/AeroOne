Set-StrictMode -Version Latest

$script:Failpoint = ''
$script:Crashpoint = ''

function Initialize-RotationTestSeams {
    param(
        [AllowEmptyString()][string]$Failpoint,
        [AllowEmptyString()][string]$Crashpoint
    )

    $script:Failpoint = $Failpoint
    $script:Crashpoint = $Crashpoint
}

function Invoke-TestFailpoint {
    param([Parameter(Mandatory = $true)][string]$Expected)

    if ($script:Failpoint -ceq $Expected) {
        throw "injected_$Expected"
    }
}

function Invoke-TestCrashpoint {
    param([Parameter(Mandatory = $true)][string]$Expected)

    if ($script:Crashpoint -ceq $Expected) {
        [Diagnostics.Process]::GetCurrentProcess().Kill()
        [Environment]::Exit(97)
    }
}

function Invoke-TestDatabaseBarrier {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Barrier
    )

    if ([string]::IsNullOrWhiteSpace($Barrier)) {
        return
    }
    $readyPath = Join-Path $WorkspaceRoot '.aeroone-rotation-db-barrier-ready'
    $releasePath = Join-Path $WorkspaceRoot '.aeroone-rotation-db-barrier-release'
    if ((Test-Path -LiteralPath $readyPath) -or (Test-Path -LiteralPath $releasePath)) {
        throw 'internal-db-barrier-stale'
    }
    $encoding = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($readyPath, 'ready', $encoding)
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    try {
        while (-not (Test-Path -LiteralPath $releasePath -PathType Leaf)) {
            if ([DateTime]::UtcNow -ge $deadline) {
                throw 'internal-db-barrier-timeout'
            }
            Start-Sleep -Milliseconds 50
        }
        if ([IO.File]::ReadAllText($releasePath, $encoding) -cne 'release') {
            throw 'internal-db-barrier-invalid-release'
        }
    } finally {
        Remove-Item -LiteralPath $readyPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $releasePath -Force -ErrorAction SilentlyContinue
    }
}

Export-ModuleMember -Function @(
    'Initialize-RotationTestSeams',
    'Invoke-TestFailpoint',
    'Invoke-TestCrashpoint',
    'Invoke-TestDatabaseBarrier'
)
