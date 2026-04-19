param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [Parameter(Mandatory = $true)]
    [int]$BackendPort,

    [Parameter(Mandatory = $true)]
    [int]$FrontendPort,

    [int]$BackendTimeoutSeconds = 20,
    [int]$FrontendTimeoutSeconds = 60,
    [string[]]$TargetHosts = @("127.0.0.1", "::1", "localhost")
)

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param(
        [string]$TargetHost,
        [int]$Port,
        [int]$ConnectTimeoutMs = 1000
    )

    $addressFamilies =
        if ($TargetHost -eq "::1") {
            @([System.Net.Sockets.AddressFamily]::InterNetworkV6)
        } elseif ($TargetHost -eq "localhost") {
            @(
                [System.Net.Sockets.AddressFamily]::InterNetwork,
                [System.Net.Sockets.AddressFamily]::InterNetworkV6
            )
        } else {
            @([System.Net.Sockets.AddressFamily]::InterNetwork)
        }

    foreach ($addressFamily in $addressFamilies) {
        $client = New-Object System.Net.Sockets.TcpClient($addressFamily)
        try {
            $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
            if (-not $async.AsyncWaitHandle.WaitOne($ConnectTimeoutMs, $false)) {
                continue
            }

            $client.EndConnect($async)
            return $true
        } catch {
            continue
        } finally {
            $client.Close()
        }
    }

    return $false
}

function Wait-PortReady {
    param(
        [string]$Label,
        [string[]]$TargetHosts,
        [int]$Port,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        foreach ($targetHost in $TargetHosts) {
            if (Test-TcpPort -TargetHost $targetHost -Port $Port) {
                Write-Host "[READY] $Label port $Port is accepting TCP connections on $targetHost."
                return $true
            }
        }

        Start-Sleep -Seconds 1
    }

    Write-Host "[ERROR] $Label port $Port did not become ready within $TimeoutSeconds seconds."
    return $false
}

if (-not (Wait-PortReady -Label "Backend" -TargetHosts $TargetHosts -Port $BackendPort -TimeoutSeconds $BackendTimeoutSeconds)) {
    exit 1
}

if (-not (Wait-PortReady -Label "Frontend" -TargetHosts $TargetHosts -Port $FrontendPort -TimeoutSeconds $FrontendTimeoutSeconds)) {
    exit 1
}

Start-Process $Url | Out-Null
Write-Host "[READY] Opened browser: $Url"
exit 0
