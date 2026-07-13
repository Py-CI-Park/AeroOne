Set-StrictMode -Version Latest

function Get-ValidatedRotationScope {
    param([Parameter(Mandatory = $true)][hashtable]$Context)

    $backendEnvironment = Read-ExactEnv -Path $Context.BackendEnvironmentPath -Profile 'backend'
    if ($Context.RootEnvironmentPresent) {
        $rootEnvironment = Read-ExactEnv -Path $Context.RootEnvironmentPath -Profile 'root'
        $matchingKeys = @('APP_ENV', 'DATABASE_URL', 'ADMIN_USERNAME')
        if ($Context.RequireCredentialMatch) {
            $matchingKeys += @('JWT_SECRET_KEY', 'ADMIN_PASSWORD')
        }
        foreach ($key in $matchingKeys) {
            if ($rootEnvironment[$key] -cne $backendEnvironment[$key]) {
                throw 'env-scope-mismatch'
            }
        }
    } else {
        if (Test-Path -LiteralPath $Context.RootEnvironmentPath) {
            throw 'env-topology-changed'
        }
        $rootEnvironment = $backendEnvironment
    }
    $databasePath = Resolve-CanonicalDatabase `
        -DatabaseUrl $rootEnvironment['DATABASE_URL'] `
        -WorkspaceRoot $Context.Workspace
    $backendDatabasePath = Resolve-CanonicalDatabase `
        -DatabaseUrl $backendEnvironment['DATABASE_URL'] `
        -WorkspaceRoot $Context.Workspace
    if (-not $databasePath.Equals($backendDatabasePath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'database-scope-mismatch'
    }
    $databaseUrl = 'sqlite:///' + $databasePath.Replace('\', '/')
    $inspection = Invoke-RotationPython -WorkspaceRoot $Context.Workspace -Request @{
        action = 'inspect'
        database_url = $databaseUrl
        admin_username = $rootEnvironment['ADMIN_USERNAME']
    }
    return [PSCustomObject]@{
        root_environment = $rootEnvironment
        backend_environment = $backendEnvironment
        database_path = $databasePath
        database_url = $databaseUrl
        inspection = $inspection
        root_environment_present = [bool]$Context.RootEnvironmentPresent
    }
}

Export-ModuleMember -Function 'Get-ValidatedRotationScope'
