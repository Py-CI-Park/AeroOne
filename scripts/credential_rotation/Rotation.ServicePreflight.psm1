Set-StrictMode -Version Latest

$script:KnownServiceNames = @('AeroOne', 'AeroOneBackend', 'AeroOneFrontend')

function ConvertTo-RotationPort {
    param([Parameter(Mandatory = $true)][string]$Value)

    $port = 0
    $valid = [int]::TryParse(
        $Value,
        [Globalization.NumberStyles]::None,
        [Globalization.CultureInfo]::InvariantCulture,
        [ref]$port
    )
    if (-not $valid -or $port -lt 1 -or $port -gt 65535) {
        throw 'env-service-port-invalid'
    }
    return $port
}

function Get-RotationServicePorts {
    param(
        [Parameter(Mandatory = $true)][hashtable]$RootEnvironment,
        [Parameter(Mandatory = $true)][hashtable]$BackendEnvironment
    )

    $ports = @()
    foreach ($definition in @(@('BACKEND_PORT', '18437'), @('FRONTEND_PORT', '29501'))) {
        $key = $definition[0]
        $fallback = $definition[1]
        $rootValue = if ($RootEnvironment.ContainsKey($key)) { $RootEnvironment[$key] } else { $fallback }
        $backendValue = if ($BackendEnvironment.ContainsKey($key)) { $BackendEnvironment[$key] } else { $fallback }
        $rootPort = ConvertTo-RotationPort -Value ([string]$rootValue)
        $backendPort = ConvertTo-RotationPort -Value ([string]$backendValue)
        if ($rootPort -ne $backendPort) {
            throw 'env-service-port-mismatch'
        }
        $ports += $rootPort
    }
    if ($ports[0] -eq $ports[1]) {
        throw 'env-service-port-collision'
    }
    return $ports
}

function Assert-AeroOneServicesStopped {
    param(
        [Parameter(Mandatory = $true)][hashtable]$RootEnvironment,
        [Parameter(Mandatory = $true)][hashtable]$BackendEnvironment,
        [switch]$CheckWindowsServices
    )

    if ($CheckWindowsServices) {
        $running = @(
            Get-Service -Name $script:KnownServiceNames -ErrorAction SilentlyContinue |
                Where-Object { [string]$_.Status -ceq 'Running' }
        )
        if ($running.Count -gt 0) {
            throw 'aeroone-service-running'
        }
    }
    $ports = @(Get-RotationServicePorts -RootEnvironment $RootEnvironment -BackendEnvironment $BackendEnvironment)
    $listeners = @([Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners())
    if (@($listeners | Where-Object { $_.Port -in $ports }).Count -gt 0) {
        throw 'aeroone-listener-running'
    }
}

Export-ModuleMember -Function 'Assert-AeroOneServicesStopped'
