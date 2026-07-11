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
            return 'Global\AeroOne.CredentialRotation.' + (
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

function New-RotationMutexSecurity {
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $security = New-Object Security.AccessControl.MutexSecurity
    $security.SetOwner($currentSid)
    $security.SetAccessRuleProtection($true, $false)
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $fullControl = [Security.AccessControl.MutexRights]::FullControl
    $security.AddAccessRule((New-Object Security.AccessControl.MutexAccessRule(
        $currentSid,
        $fullControl,
        $allow
    )))
    $security.AddAccessRule((New-Object Security.AccessControl.MutexAccessRule(
        $systemSid,
        $fullControl,
        $allow
    )))
    return $security
}

function Assert-RotationMutexSecurity {
    param([Parameter(Mandatory = $true)][Threading.Mutex]$Mutex)

    try {
        $security = $Mutex.GetAccessControl()
        $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $ownerSid = $security.GetOwner([Security.Principal.SecurityIdentifier]).Value
        $rules = @($security.GetAccessRules(
            $true,
            $false,
            [Security.Principal.SecurityIdentifier]
        ))
    } catch [UnauthorizedAccessException] {
        throw 'mutex-security-invalid'
    }
    $expectedSids = @($currentSid, 'S-1-5-18') | Sort-Object
    $actualSids = @($rules | ForEach-Object { $_.IdentityReference.Value }) | Sort-Object
    if (-not $security.AreAccessRulesProtected -or $ownerSid -ne $currentSid -or
        $rules.Count -ne 2 -or @(Compare-Object $actualSids $expectedSids).Count -ne 0) {
        throw 'mutex-security-invalid'
    }
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            ($rule.MutexRights -band [Security.AccessControl.MutexRights]::FullControl) -ne
                [Security.AccessControl.MutexRights]::FullControl) {
            throw 'mutex-security-invalid'
        }
    }
}

function Enter-RotationMutex {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [ValidateRange(0, 600000)][int]$WaitMilliseconds = 0
    )

    $name = Get-RotationMutexName -WorkspaceRoot $WorkspaceRoot
    $createdNew = $false
    try {
        $mutex = [Threading.Mutex]::new(
            $false,
            $name,
            [ref]$createdNew,
            (New-RotationMutexSecurity)
        )
    } catch [UnauthorizedAccessException] {
        throw 'mutex-create-denied'
    }
    try {
        Assert-RotationMutexSecurity -Mutex $mutex
        if (-not $mutex.WaitOne($WaitMilliseconds)) {
            $mutex.Dispose()
            return $null
        }
    } catch [Threading.AbandonedMutexException] {
        return $mutex
    } catch {
        $mutex.Dispose()
        throw
    }
    return $mutex
}

function Enter-AeroOneMaintenanceGate {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [ValidateRange(0, 600000)][int]$WaitMilliseconds = 0
    )

    return Enter-RotationMutex `
        -WorkspaceRoot $WorkspaceRoot `
        -WaitMilliseconds $WaitMilliseconds
}

Export-ModuleMember -Function @(
    'Get-RotationMutexName',
    'Assert-RotationMutexSecurity',
    'Enter-RotationMutex',
    'Enter-AeroOneMaintenanceGate'
)
