Set-StrictMode -Version Latest

function Get-RotationCurrentUserSid {
    return [Security.Principal.WindowsIdentity]::GetCurrent().User
}

function New-RotationSecureFileAcl {
    $currentSid = Get-RotationCurrentUserSid
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($currentSid, 'FullControl', $allow)))
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($systemSid, 'FullControl', $allow)))
    return $acl
}

function New-RotationSecureDirectoryAcl {
    $currentSid = Get-RotationCurrentUserSid
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $propagation = [Security.AccessControl.PropagationFlags]::None
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $currentSid,
        'FullControl',
        $inheritance,
        $propagation,
        $allow
    )))
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $systemSid,
        'FullControl',
        $inheritance,
        $propagation,
        $allow
    )))
    return $acl
}

function New-RotationSecureDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (Test-Path -LiteralPath $Path) {
        throw 'secure-root-already-exists'
    }
    $null = [IO.Directory]::CreateDirectory($Path, (New-RotationSecureDirectoryAcl))
}

function Convert-RotationIdentityToSid {
    param([Parameter(Mandatory = $true)][string]$Identity)

    if ($Identity.StartsWith('S-', [StringComparison]::OrdinalIgnoreCase)) {
        return (New-Object Security.Principal.SecurityIdentifier($Identity)).Value
    }
    return (New-Object Security.Principal.NTAccount($Identity)).Translate(
        [Security.Principal.SecurityIdentifier]
    ).Value
}

function Assert-RotationSecureFileAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $acl = Get-Acl -LiteralPath $Path
    $currentSid = (Get-RotationCurrentUserSid).Value
    if (-not $acl.AreAccessRulesProtected -or
        (Convert-RotationIdentityToSid -Identity $acl.Owner) -ne $currentSid) {
        throw 'insecure-acl'
    }
    $rules = @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))
    $expectedSids = @($currentSid, 'S-1-5-18') | Sort-Object
    $actualSids = @($rules | ForEach-Object { $_.IdentityReference.Value }) | Sort-Object
    if ($rules.Count -ne 2 -or @(Compare-Object $actualSids $expectedSids).Count -ne 0) {
        throw 'insecure-acl'
    }
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $rule.InheritanceFlags -ne [Security.AccessControl.InheritanceFlags]::None -or
            $rule.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne
                [Security.AccessControl.FileSystemRights]::FullControl) {
            throw 'insecure-acl'
        }
    }
}

function Assert-RotationBytesEqual {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Expected,
        [Parameter(Mandatory = $true)][byte[]]$Actual
    )

    if ($Expected.Length -ne $Actual.Length) {
        throw 'secure-write-verification-failed'
    }
    $difference = 0
    for ($index = 0; $index -lt $Expected.Length; $index += 1) {
        $difference = $difference -bor ($Expected[$index] -bxor $Actual[$index])
    }
    if ($difference -ne 0) {
        throw 'secure-write-verification-failed'
    }
}

function Write-AndVerifyRotationBytes {
    param(
        [Parameter(Mandatory = $true)][IO.FileStream]$Stream,
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [switch]$CrashAfterPartialWrite
    )

    if ($CrashAfterPartialWrite) {
        $partialLength = [Math]::Max(1, [Math]::Floor($Bytes.Length / 2))
        $Stream.Write($Bytes, 0, $partialLength)
        $Stream.Flush($true)
        [Diagnostics.Process]::GetCurrentProcess().Kill()
        [Environment]::Exit(96)
    }
    $Stream.Write($Bytes, 0, $Bytes.Length)
    $Stream.Flush($true)
    $Stream.Position = 0
    $readback = New-Object byte[] $Bytes.Length
    try {
        $offset = 0
        while ($offset -lt $readback.Length) {
            $read = $Stream.Read($readback, $offset, $readback.Length - $offset)
            if ($read -eq 0) {
                throw 'secure-write-verification-failed'
            }
            $offset += $read
        }
        Assert-RotationBytesEqual -Expected $Bytes -Actual $readback
    } finally {
        [Array]::Clear($readback, 0, $readback.Length)
    }
}

function Complete-RotationSecurePublish {
    param([string]$TemporaryPath, [string]$DestinationPath, [string]$BackupPath)

    $null = Assert-SinglePhysicalFile -Path $TemporaryPath
    Assert-RotationSecureFileAcl -Path $TemporaryPath
    if (Test-Path -LiteralPath $DestinationPath) {
        $null = Assert-SinglePhysicalFile -Path $DestinationPath
        Assert-RotationSecureFileAcl -Path $DestinationPath
        if (-not [string]::IsNullOrWhiteSpace($BackupPath)) {
            if (Test-Path -LiteralPath $BackupPath) {
                $null = Assert-SinglePhysicalFile -Path $BackupPath
                Assert-RotationSecureFileAcl -Path $BackupPath
            }
            [IO.File]::Replace($TemporaryPath, $DestinationPath, $BackupPath)
            $null = Assert-SinglePhysicalFile -Path $BackupPath
            Assert-RotationSecureFileAcl -Path $BackupPath
        } else {
            [IO.File]::Replace($TemporaryPath, $DestinationPath, $null)
        }
    } else {
        [IO.File]::Move($TemporaryPath, $DestinationPath)
    }
    $null = Assert-SinglePhysicalFile -Path $DestinationPath
    Assert-RotationSecureFileAcl -Path $DestinationPath
}

function Publish-RotationSecureBytes {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [string]$BackupPath = '',
        [switch]$CrashAfterPartialWrite
    )

    $parent = Split-Path -Parent $DestinationPath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw 'secure-output-parent-missing'
    }
    $temporary = Join-Path $parent ('.aeroone-rotation-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $created = $false
    $stream = $null
    try {
        $stream = [IO.FileStream]::new(
            $temporary,
            [IO.FileMode]::CreateNew,
            [Security.AccessControl.FileSystemRights]::FullControl,
            [IO.FileShare]::None,
            4096,
            [IO.FileOptions]::WriteThrough,
            (New-RotationSecureFileAcl)
        )
        $created = $true
        Write-AndVerifyRotationBytes -Stream $stream -Bytes $Bytes -CrashAfterPartialWrite:$CrashAfterPartialWrite
        $stream.Dispose()
        $stream = $null
        Complete-RotationSecurePublish -TemporaryPath $temporary -DestinationPath $DestinationPath -BackupPath $BackupPath
        $created = $false
    } finally {
        if ($null -ne $stream) {
            $stream.Dispose()
        }
        if ($created -and (Test-Path -LiteralPath $temporary -PathType Leaf)) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Remove-RotationOrphanTemps {
    param([Parameter(Mandatory = $true)][string[]]$Directories)

    foreach ($directory in $Directories) {
        foreach ($candidate in @(Get-ChildItem -LiteralPath $directory -File -Force)) {
            if ($candidate.Name -notmatch '^\.aeroone-rotation-[a-f0-9]{32}\.tmp$') {
                continue
            }
            $null = Assert-SinglePhysicalFile -Path $candidate.FullName
            Assert-RotationSecureFileAcl -Path $candidate.FullName
            Remove-Item -LiteralPath $candidate.FullName -Force
        }
    }
}

Export-ModuleMember -Function @(
    'Assert-RotationSecureFileAcl',
    'New-RotationSecureDirectory',
    'Publish-RotationSecureBytes',
    'Remove-RotationOrphanTemps'
)
