param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [Parameter(Mandatory = $true)]
    [int]$BackendPort,

    [Parameter(Mandatory = $true)]
    [int]$FrontendPort,

    [int]$BackendTimeoutSeconds = 20,
    [int]$FrontendTimeoutSeconds = 60,
    [string]$TargetHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$ConnectTimeoutMs = 1000
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($ConnectTimeoutMs, $false)) {
            return $false
        }

        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-PortReady {
    param(
        [string]$Label,
        [string]$TargetHost,
        [int]$Port,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -TargetHost $TargetHost -Port $Port) {
            Write-Host "[READY] $Label port $Port is accepting TCP connections."
            return $true
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "[ERROR] $Label port $Port did not become ready within $TimeoutSeconds seconds."
    return $false
}

if (-not (Wait-PortReady -Label "Backend" -TargetHost $TargetHost -Port $BackendPort -TimeoutSeconds $BackendTimeoutSeconds)) {
    exit 1
}

if (-not (Wait-PortReady -Label "Frontend" -TargetHost $TargetHost -Port $FrontendPort -TimeoutSeconds $FrontendTimeoutSeconds)) {
    exit 1
}

Start-Process $Url | Out-Null
Write-Host "[READY] Opened browser: $Url"
exit 0
