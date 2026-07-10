Set-StrictMode -Version Latest

function Get-RotationMutexName {
    param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

    $identity = Get-PhysicalPathIdentity -Path $WorkspaceRoot
    $raw = [Text.Encoding]::UTF8.GetBytes((
        '{0}:{1}' -f $identity.VolumeSerialNumber, $identity.FileId
    ))
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($raw)
        try {
            return 'Local\AeroOne.CredentialRotation.' + (
                [BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
            )
        } finally {
            [Array]::Clear($digest, 0, $digest.Length)
        }
    } finally {
        [Array]::Clear($raw, 0, $raw.Length)
        $sha.Dispose()
    }
}

function Enter-RotationMutex {
    param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

    $name = Get-RotationMutexName -WorkspaceRoot $WorkspaceRoot
    $mutex = New-Object Threading.Mutex($false, $name)
    try {
        if (-not $mutex.WaitOne(0)) {
            $mutex.Dispose()
            return $null
        }
    } catch [Threading.AbandonedMutexException] {
        return $mutex
    }
    return $mutex
}

Export-ModuleMember -Function @(
    'Get-RotationMutexName',
    'Enter-RotationMutex'
)
