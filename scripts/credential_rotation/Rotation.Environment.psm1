Set-StrictMode -Version Latest

function New-UpdatedEnvText {
    param([string]$Path, [string]$JwtSecret, [string]$AdminPassword)

    $jwtCount = 0
    $passwordCount = 0
    $updated = New-Object Collections.Generic.List[string]
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        if ($line.StartsWith('JWT_SECRET_KEY=', [StringComparison]::Ordinal)) {
            $updated.Add("JWT_SECRET_KEY=$JwtSecret")
            $jwtCount += 1
        } elseif ($line.StartsWith('ADMIN_PASSWORD=', [StringComparison]::Ordinal)) {
            $updated.Add("ADMIN_PASSWORD=$AdminPassword")
            $passwordCount += 1
        } else {
            $updated.Add($line)
        }
    }
    if ($jwtCount -ne 1 -or $passwordCount -ne 1) {
        throw 'env-rotation-key-mismatch'
    }
    return [string]::Join([Environment]::NewLine, $updated) + [Environment]::NewLine
}

function Write-PendingEnvironment {
    param(
        [string]$SourcePath,
        [string]$PendingPath,
        [string]$JwtSecret,
        [string]$AdminPassword,
        [string]$Purpose
    )

    $text = New-UpdatedEnvText -Path $SourcePath -JwtSecret $JwtSecret -AdminPassword $AdminPassword
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($text)
    try {
        Write-ProtectedBytes -Bytes $bytes -Path $PendingPath -Purpose $Purpose
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        $text = $null
    }
}

function Read-CredentialBundle {
    param([Parameter(Mandatory = $true)][string]$Path)

    return Read-ProtectedJson -Path $Path -Purpose 'credential-bundle'
}

function Get-AdminCredential {
    param([Parameter(Mandatory = $true)]$Bundle)

    $matches = @($Bundle.users | Where-Object { $_.username -ceq $Bundle.admin_username })
    if ($matches.Count -ne 1) {
        throw 'admin-credential-mismatch'
    }
    return $matches[0]
}

function Promote-ProtectedEnvironment {
    param([string]$PendingPath, [string]$DestinationPath, [string]$Purpose)

    Assert-SecureAcl -Path $PendingPath
    $protected = [IO.File]::ReadAllBytes($PendingPath)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected -Purpose $Purpose
    try {
        Publish-RotationSecureBytes -Bytes $plaintext -DestinationPath $DestinationPath
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
    }
}

Export-ModuleMember -Function @(
    'Write-PendingEnvironment',
    'Read-CredentialBundle',
    'Get-AdminCredential',
    'Promote-ProtectedEnvironment'
)
