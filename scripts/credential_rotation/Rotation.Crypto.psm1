Set-StrictMode -Version Latest

function Get-PurposeEntropy {
    param([Parameter(Mandatory = $true)][string]$Purpose)

    $bytes = [Text.Encoding]::ASCII.GetBytes('AeroOne.CredentialRotation.v1:' + $Purpose)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ,$sha.ComputeHash($bytes)
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        $sha.Dispose()
    }
}

function Protect-ForCurrentUser {
    param([byte[]]$Bytes, [string]$Purpose)

    $entropy = Get-PurposeEntropy -Purpose $Purpose
    try {
        return ,[Security.Cryptography.ProtectedData]::Protect(
            $Bytes,
            $entropy,
            [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
    } finally {
        [Array]::Clear($entropy, 0, $entropy.Length)
    }
}

function Unprotect-ForCurrentUser {
    param([byte[]]$Bytes, [string]$Purpose)

    $entropy = Get-PurposeEntropy -Purpose $Purpose
    try {
        return ,[Security.Cryptography.ProtectedData]::Unprotect(
            $Bytes,
            $entropy,
            [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
    } finally {
        [Array]::Clear($entropy, 0, $entropy.Length)
    }
}

function Write-ProtectedBytes {
    param(
        [byte[]]$Bytes,
        [string]$Path,
        [string]$Purpose,
        [string]$BackupPath = ''
    )

    $protected = Protect-ForCurrentUser -Bytes $Bytes -Purpose $Purpose
    try {
        Publish-RotationSecureBytes -Bytes $protected -DestinationPath $Path -BackupPath $BackupPath
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
    }
}

function Write-ProtectedJson {
    param($Value, [string]$Path, [string]$Purpose, [string]$BackupPath = '')

    $json = $Value | ConvertTo-Json -Compress -Depth 8
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($json)
    try {
        Write-ProtectedBytes -Bytes $bytes -Path $Path -Purpose $Purpose -BackupPath $BackupPath
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Read-ProtectedJson {
    param([string]$Path, [string]$Purpose)

    Assert-SecureAcl -Path $Path
    $protected = [IO.File]::ReadAllBytes($Path)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected -Purpose $Purpose
    try {
        return (New-Object Text.UTF8Encoding($false)).GetString($plaintext) | ConvertFrom-Json
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
    }
}

function Assert-ProtectedBytesReadable {
    param([string]$Path, [string]$Purpose)

    Assert-SecureAcl -Path $Path
    $protected = [IO.File]::ReadAllBytes($Path)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected -Purpose $Purpose
    try {
        if ($plaintext.Length -eq 0) {
            throw 'protected-payload-empty'
        }
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
    }
}

function Get-ByteSha256 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($Bytes)
        try {
            return [BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
        } finally {
            [Array]::Clear($digest, 0, $digest.Length)
        }
    } finally {
        $sha.Dispose()
    }
}

function Get-ProtectedPayloadSha256 {
    param([string]$Path, [string]$Purpose)

    Assert-SecureAcl -Path $Path
    $protected = [IO.File]::ReadAllBytes($Path)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected -Purpose $Purpose
    try {
        return Get-ByteSha256 -Bytes $plaintext
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
    }
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-FileSha256 {
    param([string]$Path, [string]$Expected)

    if ((Get-FileSha256 -Path $Path) -cne $Expected) {
        throw 'artifact-digest-mismatch'
    }
}

Export-ModuleMember -Function @(
    'Protect-ForCurrentUser',
    'Unprotect-ForCurrentUser',
    'Write-ProtectedBytes',
    'Write-ProtectedJson',
    'Read-ProtectedJson',
    'Assert-ProtectedBytesReadable',
    'Get-ProtectedPayloadSha256',
    'Get-FileSha256',
    'Assert-FileSha256'
)
