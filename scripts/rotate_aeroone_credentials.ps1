[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$TestMode,
    [string]$TestWorkspaceRoot,
    [ValidateSet('', 'before_db_commit', 'after_db_commit', 'after_root_env_promote', 'before_credentials_promote')]
    [string]$Failpoint = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Security

$ProductionWorkspace = 'D:\Chanil_Park\Project\Programming\AeroOne'
$ProductRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$AllowedCredentialKeys = @('JWT_SECRET_KEY', 'ADMIN_PASSWORD')
$RequiredKeys = @('DATABASE_URL', 'JWT_SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD')
$Retention = '2027-07-10T00:00:00+09:00'
$PhaseOrder = @{
    prepared = 0
    db_committed = 1
    root_env_promoted = 2
    backend_env_promoted = 3
    credentials_promoted = 4
    complete = 5
}
$CurrentStage = 'validate'

function Stop-Rotation {
    param([string]$Code)

    if ($Code -notmatch '^[a-z0-9_-]+$') {
        $Code = 'operation-failed'
    }
    [Console]::Error.WriteLine("status=error code=$Code")
    exit 1
}

function Get-WorkspaceRoot {
    if ($TestMode) {
        if ([string]::IsNullOrWhiteSpace($TestWorkspaceRoot)) {
            throw 'test-root-required'
        }
        $candidate = [IO.Path]::GetFullPath($TestWorkspaceRoot)
        if (-not (Test-Path -LiteralPath (Join-Path $candidate '.aeroone-rotation-test-root') -PathType Leaf)) {
            throw 'unknown-test-root'
        }
        return $candidate.TrimEnd('\')
    }
    if (-not [string]::IsNullOrWhiteSpace($TestWorkspaceRoot)) {
        throw 'test-root-forbidden'
    }
    $candidate = [IO.Path]::GetFullPath($ProductionWorkspace)
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw 'production-root-missing'
    }
    return $candidate.TrimEnd('\')
}

function Read-ExactEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'env-missing'
    }
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if ($trimmed.Length -eq 0 -or $trimmed.StartsWith('#')) {
            continue
        }
        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            throw 'env-malformed'
        }
        $key = $line.Substring(0, $separator).Trim()
        if ($values.ContainsKey($key)) {
            throw 'env-duplicate-key'
        }
        $values[$key] = $line.Substring($separator + 1)
    }
    foreach ($required in $RequiredKeys) {
        if (-not $values.ContainsKey($required) -or [string]::IsNullOrWhiteSpace($values[$required])) {
            throw 'env-required-key-missing'
        }
    }
    foreach ($key in $values.Keys) {
        if ($key -match '(?i)(_SECRET_KEY|_PASSWORD|_TOKEN|_API_KEY|_PRIVATE_KEY|_ACCESS_KEY)$' -and $key -notin $AllowedCredentialKeys) {
            throw 'unknown-credential-key'
        }
    }
    return $values
}

function Resolve-CanonicalDatabase {
    param([string]$DatabaseUrl, [string]$WorkspaceRoot)

    if (-not $DatabaseUrl.StartsWith('sqlite:///', [StringComparison]::Ordinal)) {
        throw 'database-provider-forbidden'
    }
    $rawPath = $DatabaseUrl.Substring('sqlite:///'.Length).Replace('/', '\')
    if ([IO.Path]::IsPathRooted($rawPath)) {
        $resolved = [IO.Path]::GetFullPath($rawPath)
    } else {
        $resolved = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $rawPath))
    }
    $expected = [IO.Path]::GetFullPath((Join-Path $WorkspaceRoot 'backend\data\aeroone.db'))
    if (-not $resolved.Equals($expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-path-forbidden'
    }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw 'database-missing'
    }
    return $resolved
}

function Invoke-RotationPython {
    param([hashtable]$Request, [string]$WorkspaceRoot)

    $python = Join-Path $WorkspaceRoot 'backend\.venv\Scripts\python.exe'
    if ($TestMode -and -not [string]::IsNullOrWhiteSpace($env:AEROONE_ROTATION_PYTHON)) {
        $python = [IO.Path]::GetFullPath($env:AEROONE_ROTATION_PYTHON)
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'python-runtime-missing'
    }
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = '-m app.commands.rotate_credentials'
    $startInfo.WorkingDirectory = Join-Path $ProductRoot 'backend'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['PYTHONPATH'] = $startInfo.WorkingDirectory
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'python-start-failed'
    }
    $requestBytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Request | ConvertTo-Json -Compress))
    $process.StandardInput.BaseStream.Write($requestBytes, 0, $requestBytes.Length)
    $process.StandardInput.BaseStream.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $null = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $response = $null
    if (-not [string]::IsNullOrWhiteSpace($stdout)) {
        $response = $stdout | ConvertFrom-Json
    }
    if ($process.ExitCode -ne 0) {
        if ($null -ne $response -and $response.status -eq 'error' -and $response.code -match '^[a-z-]+$') {
            throw "python-$($response.code)"
        }
        throw 'python-command-failed'
    }
    if ($null -eq $response) {
        throw 'python-empty-response'
    }
    if ($response.status -ne 'ok') {
        throw 'python-command-rejected'
    }
    return $response
}

function Get-CurrentUserSid {
    return [Security.Principal.WindowsIdentity]::GetCurrent().User
}

function Set-SecureDirectoryAcl {
    param([string]$Path)

    $currentSid = Get-CurrentUserSid
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    $propagation = [Security.AccessControl.PropagationFlags]::None
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($currentSid, 'FullControl', $inheritance, $propagation, $allow)))
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($systemSid, 'FullControl', $inheritance, $propagation, $allow)))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Set-SecureFileAcl {
    param([string]$Path)

    $currentSid = Get-CurrentUserSid
    $systemSid = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($currentSid, 'FullControl', $allow)))
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($systemSid, 'FullControl', $allow)))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Convert-IdentityToSid {
    param([string]$Identity)

    if ($Identity.StartsWith('S-', [StringComparison]::OrdinalIgnoreCase)) {
        return (New-Object Security.Principal.SecurityIdentifier($Identity)).Value
    }
    return (New-Object Security.Principal.NTAccount($Identity)).Translate([Security.Principal.SecurityIdentifier]).Value
}

function Assert-SecureAcl {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw 'secure-output-missing'
    }
    $acl = Get-Acl -LiteralPath $Path
    $currentSid = (Get-CurrentUserSid).Value
    $allowedSids = @($currentSid, 'S-1-5-18')
    if (-not $acl.AreAccessRulesProtected -or (Convert-IdentityToSid -Identity $acl.Owner) -ne $currentSid) {
        throw 'insecure-acl'
    }
    $rules = @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2) {
        throw 'insecure-acl'
    }
    foreach ($rule in $rules) {
        if ($rule.IdentityReference.Value -notin $allowedSids) {
            throw 'insecure-acl'
        }
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) {
            throw 'insecure-acl'
        }
        if (($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne [Security.AccessControl.FileSystemRights]::FullControl) {
            throw 'insecure-acl'
        }
    }
}

function Initialize-SecureDirectory {
    param([string]$Path, [bool]$Resume)

    if (Test-Path -LiteralPath $Path) {
        if ($Resume) {
            Assert-SecureAcl -Path $Path
        } else {
            throw 'secure-root-already-exists'
        }
        return
    }
    $null = New-Item -ItemType Directory -Path $Path
    Set-SecureDirectoryAcl -Path $Path
    Assert-SecureAcl -Path $Path
}

function Protect-ForCurrentUser {
    param([byte[]]$Bytes)

    return ,[Security.Cryptography.ProtectedData]::Protect(
        $Bytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
}

function Unprotect-ForCurrentUser {
    param([byte[]]$Bytes)

    return ,[Security.Cryptography.ProtectedData]::Unprotect(
        $Bytes,
        $null,
        [Security.Cryptography.DataProtectionScope]::CurrentUser
    )
}

function Write-ProtectedBytes {
    param([byte[]]$Bytes, [string]$Path)

    $protected = Protect-ForCurrentUser -Bytes $Bytes
    [IO.File]::WriteAllBytes($Path, $protected)
    Set-SecureFileAcl -Path $Path
    Assert-SecureAcl -Path $Path
    [Array]::Clear($protected, 0, $protected.Length)
}

function Write-ProtectedJson {
    param($Value, [string]$Path)

    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Value | ConvertTo-Json -Compress -Depth 8))
    try {
        Write-ProtectedBytes -Bytes $bytes -Path $Path
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Read-ProtectedJson {
    param([string]$Path)

    Assert-SecureAcl -Path $Path
    $protected = [IO.File]::ReadAllBytes($Path)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected
    try {
        return (New-Object Text.UTF8Encoding($false)).GetString($plaintext) | ConvertFrom-Json
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
    }
}

function Write-DatabaseRecovery {
    param([string]$DatabasePath, [string]$RecoveryPath)

    $script:CurrentStage = 'recovery_open'
    $stream = [IO.File]::Open(
        $DatabasePath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::None
    )
    $memory = New-Object IO.MemoryStream
    try {
        $script:CurrentStage = 'recovery_read'
        $stream.CopyTo($memory)
        $bytes = $memory.ToArray()
        try {
            $script:CurrentStage = 'recovery_protect'
            Write-ProtectedBytes -Bytes $bytes -Path $RecoveryPath
        } finally {
            [Array]::Clear($bytes, 0, $bytes.Length)
        }
    } finally {
        $memory.Dispose()
        $stream.Dispose()
    }
}

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
        [string]$AdminPassword
    )

    $text = New-UpdatedEnvText -Path $SourcePath -JwtSecret $JwtSecret -AdminPassword $AdminPassword
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($text)
    try {
        Write-ProtectedBytes -Bytes $bytes -Path $PendingPath
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        $text = $null
    }
}

function Read-CredentialBundle {
    param([string]$Path)

    return Read-ProtectedJson -Path $Path
}

function Get-AdminCredential {
    param($Bundle)

    $matches = @($Bundle.users | Where-Object { $_.username -ceq $Bundle.admin_username })
    if ($matches.Count -ne 1) {
        throw 'admin-credential-mismatch'
    }
    return $matches[0]
}

function Write-QuarantineManifest {
    param($Manifest, [string]$Path)

    $temporary = "$Path.pending"
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($Manifest | ConvertTo-Json -Depth 8))
    try {
        $script:CurrentStage = 'manifest_temp_write'
        [IO.File]::WriteAllBytes($temporary, $bytes)
        Set-SecureFileAcl -Path $temporary
        if (Test-Path -LiteralPath $Path) {
            $script:CurrentStage = 'manifest_replace'
            $backup = "$Path.previous"
            if (Test-Path -LiteralPath $backup) {
                throw 'manifest-backup-exists'
            }
            [IO.File]::Replace($temporary, $Path, $backup)
            Set-SecureFileAcl -Path $backup
            Assert-SecureAcl -Path $backup
        } else {
            [IO.File]::Move($temporary, $Path)
        }
        $script:CurrentStage = 'manifest_acl'
        Set-SecureFileAcl -Path $Path
        Assert-SecureAcl -Path $Path
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Move-EnvironmentToQuarantine {
    param(
        [string]$SourcePath,
        [string]$SourceLabel,
        [string]$DestinationPath,
        [string]$ManifestPath
    )

    if (Test-Path -LiteralPath $ManifestPath) {
        $script:CurrentStage = 'quarantine_manifest_read'
        Assert-SecureAcl -Path $ManifestPath
        $manifest = [IO.File]::ReadAllText($ManifestPath) | ConvertFrom-Json
    } else {
        $manifest = [PSCustomObject]@{
            version = 1
            retention = $Retention
            entries = @()
        }
    }
    $manifestChanged = $false
    $existingEntry = @($manifest.entries | Where-Object { $_.source -ceq $SourceLabel })
    if (-not (Test-Path -LiteralPath $DestinationPath)) {
        $script:CurrentStage = 'quarantine_move'
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
            throw 'env-source-missing'
        }
        $source = Get-Item -LiteralPath $SourcePath
        $digest = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        Move-Item -LiteralPath $SourcePath -Destination $DestinationPath
        Set-SecureFileAcl -Path $DestinationPath
        $script:CurrentStage = 'quarantine_append'
        $entry = [PSCustomObject]@{
            source = $SourceLabel
            category = 'environment'
            size = $source.Length
            sha256 = $digest
            moved_at = [DateTimeOffset]::Now.ToString('o')
            retention = $Retention
        }
        $manifest.entries = @($manifest.entries) + @($entry)
        $manifestChanged = $true
    } elseif ($existingEntry.Count -eq 0) {
        Assert-SecureAcl -Path $DestinationPath
        $destination = Get-Item -LiteralPath $DestinationPath
        $entry = [PSCustomObject]@{
            source = $SourceLabel
            category = 'environment'
            size = $destination.Length
            sha256 = (Get-FileHash -LiteralPath $DestinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
            moved_at = [DateTimeOffset]::Now.ToString('o')
            retention = $Retention
        }
        $manifest.entries = @($manifest.entries) + @($entry)
        $manifestChanged = $true
    }
    if (@($manifest.entries | Where-Object { $_.source -ceq $SourceLabel }).Count -ne 1) {
        throw 'quarantine-manifest-mismatch'
    }
    if ($manifestChanged) {
        $script:CurrentStage = 'quarantine_manifest_write'
        Write-QuarantineManifest -Manifest $manifest -Path $ManifestPath
    }
}

function Promote-ProtectedEnvironment {
    param([string]$PendingPath, [string]$DestinationPath)

    Assert-SecureAcl -Path $PendingPath
    $protected = [IO.File]::ReadAllBytes($PendingPath)
    $plaintext = Unprotect-ForCurrentUser -Bytes $protected
    $temporary = "$DestinationPath.rotation-pending"
    try {
        [IO.File]::WriteAllBytes($temporary, $plaintext)
        Set-SecureFileAcl -Path $temporary
        if (Test-Path -LiteralPath $DestinationPath) {
            [IO.File]::Replace($temporary, $DestinationPath, $null)
        } else {
            [IO.File]::Move($temporary, $DestinationPath)
        }
        Set-SecureFileAcl -Path $DestinationPath
    } finally {
        [Array]::Clear($protected, 0, $protected.Length)
        [Array]::Clear($plaintext, 0, $plaintext.Length)
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Write-JournalPhase {
    param($Journal, [string]$Phase, [string]$JournalPath)

    if (-not $PhaseOrder.ContainsKey($Phase)) {
        throw 'journal-phase-invalid'
    }
    $Journal.phase = $Phase
    Write-ProtectedJson -Value $Journal -Path $JournalPath
}

function Invoke-TestFailpoint {
    param([string]$Expected)

    if ($Failpoint -ceq $Expected) {
        throw "injected_$Expected"
    }
}

try {
    if (-not $TestMode -and -not [string]::IsNullOrWhiteSpace($Failpoint)) {
        throw 'failpoint-forbidden'
    }
    $workspace = Get-WorkspaceRoot
    if ($TestMode) {
        $secureRoot = Join-Path $workspace '.rotation-secure'
        $finalCredentialPath = Join-Path $secureRoot '1.12.3-credentials.dpapi'
    } else {
        $secureBase = Join-Path $env:USERPROFILE 'AeroOne-secure'
        if (-not (Test-Path -LiteralPath $secureBase)) {
            $null = New-Item -ItemType Directory -Path $secureBase
            Set-SecureDirectoryAcl -Path $secureBase
        }
        $secureRoot = Join-Path $secureBase 'incident-20260710'
        $finalCredentialPath = Join-Path $secureBase '1.12.3-credentials.dpapi'
    }
    $journalPath = Join-Path $secureRoot 'rotation-state.json.dpapi'
    $resume = Test-Path -LiteralPath $journalPath -PathType Leaf
    $rootEnvPath = Join-Path $workspace '.env'
    $backendEnvPath = Join-Path $workspace 'backend\.env'
    $rootEnv = Read-ExactEnv -Path $rootEnvPath
    $backendEnv = Read-ExactEnv -Path $backendEnvPath
    $matchingKeys = @('DATABASE_URL', 'ADMIN_USERNAME')
    if (-not $resume) {
        $matchingKeys += @('JWT_SECRET_KEY', 'ADMIN_PASSWORD')
    }
    foreach ($key in $matchingKeys) {
        if ($rootEnv[$key] -cne $backendEnv[$key]) {
            throw 'env-scope-mismatch'
        }
    }
    $databasePath = Resolve-CanonicalDatabase -DatabaseUrl $rootEnv['DATABASE_URL'] -WorkspaceRoot $workspace
    $backendDatabasePath = Resolve-CanonicalDatabase -DatabaseUrl $backendEnv['DATABASE_URL'] -WorkspaceRoot $workspace
    if (-not $databasePath.Equals($backendDatabasePath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-scope-mismatch'
    }
    $databaseUrl = 'sqlite:///' + $databasePath.Replace('\', '/')
    $inspection = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
        action = 'inspect'
        database_url = $databaseUrl
        admin_username = $rootEnv['ADMIN_USERNAME']
    }
    if ($DryRun) {
        [Console]::Out.WriteLine("status=dry-run scope=valid users=$($inspection.user_count_before)")
        exit 0
    }

    $CurrentStage = 'secure_acl'
    Initialize-SecureDirectory -Path $secureRoot -Resume $resume
    $recoveryDirectory = Join-Path $secureRoot 'recovery'
    $pendingDirectory = Join-Path $secureRoot 'pending'
    $quarantineDirectory = Join-Path $secureRoot 'quarantine'
    $quarantineEnvDirectory = Join-Path $quarantineDirectory 'environment'
    foreach ($directory in @($recoveryDirectory, $pendingDirectory, $quarantineDirectory, $quarantineEnvDirectory)) {
        Initialize-SecureDirectory -Path $directory -Resume $resume
    }
    $recoveryPath = Join-Path $recoveryDirectory 'aeroone-db-before-rotation.dpapi'
    $pendingCredentialPath = Join-Path $pendingDirectory 'credentials.dpapi'
    $pendingRootEnvPath = Join-Path $pendingDirectory 'root-env.dpapi'
    $pendingBackendEnvPath = Join-Path $pendingDirectory 'backend-env.dpapi'
    $quarantineRootEnvPath = Join-Path $quarantineEnvDirectory 'root.env.before-rotation'
    $quarantineBackendEnvPath = Join-Path $quarantineEnvDirectory 'backend.env.before-rotation'
    $quarantineManifestPath = Join-Path $quarantineDirectory 'quarantine-manifest.json'

    if (-not $resume) {
        $CurrentStage = 'recovery'
        Write-DatabaseRecovery -DatabasePath $databasePath -RecoveryPath $recoveryPath
        $CurrentStage = 'prepare'
        $prepared = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'prepare'
            database_url = $databaseUrl
            admin_username = $rootEnv['ADMIN_USERNAME']
            bundle_path = $pendingCredentialPath
        }
        Set-SecureFileAcl -Path $pendingCredentialPath
        Assert-SecureAcl -Path $pendingCredentialPath
        $bundle = Read-CredentialBundle -Path $pendingCredentialPath
        $adminCredential = Get-AdminCredential -Bundle $bundle
        $CurrentStage = 'pending_env'
        Write-PendingEnvironment -SourcePath $rootEnvPath -PendingPath $pendingRootEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password
        Write-PendingEnvironment -SourcePath $backendEnvPath -PendingPath $pendingBackendEnvPath -JwtSecret $bundle.jwt_secret_key -AdminPassword $adminCredential.password
        $journal = [PSCustomObject]@{
            version = 1
            phase = 'prepared'
            user_count = [int]$prepared.user_count_before
            retention = $Retention
        }
        Write-ProtectedJson -Value $journal -Path $journalPath
        $bundle = $null
        $adminCredential = $null
    } else {
        foreach ($sensitivePath in @($journalPath, $recoveryPath)) {
            Assert-SecureAcl -Path $sensitivePath
        }
        $journal = Read-ProtectedJson -Path $journalPath
        if ($journal.version -ne 1 -or $journal.retention -cne $Retention -or -not $PhaseOrder.ContainsKey([string]$journal.phase)) {
            throw 'journal-invalid'
        }
        if ([int]$journal.user_count -ne [int]$inspection.user_count_before) {
            throw 'journal-user-count-mismatch'
        }
        $resumePhase = [string]$journal.phase
        if ($PhaseOrder[$resumePhase] -lt $PhaseOrder['credentials_promoted']) {
            Assert-SecureAcl -Path $pendingCredentialPath
        }
        if ($PhaseOrder[$resumePhase] -lt $PhaseOrder['root_env_promoted']) {
            Assert-SecureAcl -Path $pendingRootEnvPath
        }
        if ($PhaseOrder[$resumePhase] -lt $PhaseOrder['backend_env_promoted']) {
            Assert-SecureAcl -Path $pendingBackendEnvPath
        }
    }

    $phase = [string]$journal.phase
    if ($PhaseOrder[$phase] -lt $PhaseOrder['db_committed']) {
        $CurrentStage = 'db_commit'
        Assert-SecureAcl -Path $pendingCredentialPath
        $committed = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
            action = 'commit'
            database_url = $databaseUrl
            bundle_path = $pendingCredentialPath
            fail_before_commit = ($Failpoint -ceq 'before_db_commit')
        }
        if ([int]$committed.user_count_after -ne [int]$journal.user_count -or [int]$committed.password_count_changed -ne [int]$journal.user_count) {
            throw 'database-commit-count-mismatch'
        }
        Write-JournalPhase -Journal $journal -Phase 'db_committed' -JournalPath $journalPath
        $phase = 'db_committed'
    }
    Invoke-TestFailpoint -Expected 'after_db_commit'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['root_env_promoted']) {
        $CurrentStage = 'root_env_promote'
        Move-EnvironmentToQuarantine -SourcePath $rootEnvPath -SourceLabel '.env' -DestinationPath $quarantineRootEnvPath -ManifestPath $quarantineManifestPath
        Promote-ProtectedEnvironment -PendingPath $pendingRootEnvPath -DestinationPath $rootEnvPath
        Write-JournalPhase -Journal $journal -Phase 'root_env_promoted' -JournalPath $journalPath
        $phase = 'root_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'after_root_env_promote'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['backend_env_promoted']) {
        $CurrentStage = 'backend_env_quarantine'
        Move-EnvironmentToQuarantine -SourcePath $backendEnvPath -SourceLabel 'backend/.env' -DestinationPath $quarantineBackendEnvPath -ManifestPath $quarantineManifestPath
        $CurrentStage = 'backend_env_write'
        Promote-ProtectedEnvironment -PendingPath $pendingBackendEnvPath -DestinationPath $backendEnvPath
        $CurrentStage = 'backend_env_journal'
        Write-JournalPhase -Journal $journal -Phase 'backend_env_promoted' -JournalPath $journalPath
        $phase = 'backend_env_promoted'
    }
    Invoke-TestFailpoint -Expected 'before_credentials_promote'

    if ($PhaseOrder[$phase] -lt $PhaseOrder['credentials_promoted']) {
        $CurrentStage = 'credentials_promote'
        if (Test-Path -LiteralPath $finalCredentialPath) {
            throw 'credential-destination-exists'
        }
        Move-Item -LiteralPath $pendingCredentialPath -Destination $finalCredentialPath
        Set-SecureFileAcl -Path $finalCredentialPath
        Assert-SecureAcl -Path $finalCredentialPath
        Write-JournalPhase -Journal $journal -Phase 'credentials_promoted' -JournalPath $journalPath
        $phase = 'credentials_promoted'
    }

    $CurrentStage = 'verify'
    $finalBundle = Read-CredentialBundle -Path $finalCredentialPath
    $finalAdminCredential = Get-AdminCredential -Bundle $finalBundle
    $finalRootEnv = Read-ExactEnv -Path $rootEnvPath
    $finalBackendEnv = Read-ExactEnv -Path $backendEnvPath
    if ($finalRootEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key -or $finalBackendEnv['JWT_SECRET_KEY'] -cne $finalBundle.jwt_secret_key) {
        throw 'jwt-promotion-mismatch'
    }
    if ($finalRootEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password -or $finalBackendEnv['ADMIN_PASSWORD'] -cne $finalAdminCredential.password) {
        throw 'admin-promotion-mismatch'
    }
    $verified = Invoke-RotationPython -WorkspaceRoot $workspace -Request @{
        action = 'verify'
        database_url = $databaseUrl
        bundle_path = $finalCredentialPath
    }
    if ([int]$verified.password_count_changed -ne [int]$journal.user_count -or [int]$verified.session_count_after -ne 0) {
        throw 'database-verification-mismatch'
    }
    Assert-SecureAcl -Path $quarantineManifestPath
    $manifest = [IO.File]::ReadAllText($quarantineManifestPath) | ConvertFrom-Json
    if ($manifest.retention -cne $Retention -or @($manifest.entries).Count -ne 2) {
        throw 'quarantine-manifest-mismatch'
    }
    $finalBundle = $null
    $finalAdminCredential = $null
    if ($phase -ne 'complete') {
        Write-JournalPhase -Journal $journal -Phase 'complete' -JournalPath $journalPath
    }
    [Console]::Out.WriteLine("status=complete scope=valid users=$($verified.user_count_after)")
    exit 0
} catch {
    $failureCode = $_.Exception.Message
    if ($failureCode -notmatch '^[a-z0-9_-]+$') {
        $failureCode = "stage_$CurrentStage"
    }
    Stop-Rotation -Code $failureCode
}
