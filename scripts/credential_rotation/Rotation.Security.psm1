Set-StrictMode -Version Latest

function Get-CurrentUserSid {
    return [Security.Principal.WindowsIdentity]::GetCurrent().User
}

function Set-SecureFileAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $currentSid = Get-CurrentUserSid
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($currentSid, 'FullControl', $allow)))
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($systemSid, 'FullControl', $allow)))
    (Get-Item -LiteralPath $Path -Force).SetAccessControl($acl)
}

function Convert-IdentityToSid {
    param([Parameter(Mandatory = $true)][string]$Identity)

    if ($Identity.StartsWith('S-', [StringComparison]::OrdinalIgnoreCase)) {
        return (New-Object Security.Principal.SecurityIdentifier($Identity)).Value
    }
    return (New-Object Security.Principal.NTAccount($Identity)).Translate(
        [Security.Principal.SecurityIdentifier]
    ).Value
}

function Assert-SecureAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw 'secure-output-missing'
    }
    $item = Get-Item -LiteralPath $Path -Force
    $acl = Get-Acl -LiteralPath $Path
    $currentSid = (Get-CurrentUserSid).Value
    if (-not $acl.AreAccessRulesProtected -or
        (Convert-IdentityToSid -Identity $acl.Owner) -ne $currentSid) {
        throw 'insecure-acl'
    }
    $rules = @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))
    $expectedSids = @($currentSid, 'S-1-5-18') | Sort-Object
    $actualSids = @($rules | ForEach-Object { $_.IdentityReference.Value }) | Sort-Object
    if ($rules.Count -ne 2 -or @(Compare-Object $actualSids $expectedSids).Count -ne 0) {
        throw 'insecure-acl'
    }
    $expectedInheritance = if ($item.PSIsContainer) {
        [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    } else {
        [Security.AccessControl.InheritanceFlags]::None
    }
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $rule.InheritanceFlags -ne $expectedInheritance -or
            $rule.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne
                [Security.AccessControl.FileSystemRights]::FullControl) {
            throw 'insecure-acl'
        }
    }
}

function Initialize-SecureDirectory {
    param([string]$Path, [bool]$Resume)

    if (Test-Path -LiteralPath $Path) {
        if (-not $Resume) {
            throw 'secure-root-already-exists'
        }
        $identity = Get-PhysicalPathIdentity -Path $Path
        if (-not $identity.IsDirectory) {
            throw 'secure-directory-invalid'
        }
        Assert-SecureAcl -Path $Path
        return
    }
    New-RotationSecureDirectory -Path $Path
    Assert-SecureAcl -Path $Path
}

function Assert-SecureDirectoryInventory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$AllowedNames
    )

    foreach ($item in @(Get-ChildItem -LiteralPath $Path -Force)) {
        if ($item.Name -notin $AllowedNames) {
            throw 'unexpected-secure-output'
        }
        $identity = Get-PhysicalPathIdentity -Path $item.FullName
        if ($item.PSIsContainer -and -not $identity.IsDirectory) {
            throw 'secure-directory-invalid'
        }
        if (-not $item.PSIsContainer) {
            $null = Assert-SinglePhysicalFile -Path $item.FullName
        }
        Assert-SecureAcl -Path $item.FullName
    }
}

Export-ModuleMember -Function @(
    'Get-CurrentUserSid',
    'Set-SecureFileAcl',
    'Assert-SecureAcl',
    'Initialize-SecureDirectory',
    'Assert-SecureDirectoryInventory'
)
