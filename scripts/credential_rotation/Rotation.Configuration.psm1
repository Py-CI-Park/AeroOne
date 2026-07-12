Set-StrictMode -Version Latest

function New-RotationConfiguration {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptDirectory,
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [ValidateSet('scripts\rotate_aeroone_credentials.ps1', 'scripts\view_aeroone_credentials.ps1')]
        [string]$ExpectedEntryPoint,
        [Parameter(Mandatory = $true)][bool]$TestMode,
        [AllowEmptyString()][string]$TestWorkspaceRoot,
        [AllowEmptyString()][string]$PythonOverride
    )

    $productRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDirectory '..'))
    $productionWorkspace = $productRoot
    $rootAllowedEnvironmentKeys = @(
        'APP_ENV',
        'APP_NAME',
        'BACKEND_PORT',
        'FRONTEND_PORT',
        'DATABASE_URL',
        'JWT_SECRET_KEY',
        'ADMIN_SESSION_COOKIE_NAME',
        'ACCESS_TOKEN_TTL_MINUTES',
        'ADMIN_USERNAME',
        'ADMIN_PASSWORD',
        'CSRF_COOKIE_NAME',
        'NEWSLETTER_IMPORT_ROOT_HOST',
        'NEWSLETTER_IMPORT_ROOT_CONTAINER',
        'CIVIL_AIRCRAFT_ROOT_HOST',
        'CIVIL_AIRCRAFT_ROOT',
        'DOCUMENT_ROOT',
        'NSA_ROOT',
        'STORAGE_ROOT',
        'THUMBNAILS_DIR_NAME',
        'ATTACHMENTS_DIR_NAME',
        'MARKDOWN_DIR_NAME',
        'CORS_ORIGINS',
        'NEXT_PUBLIC_API_BASE_URL',
        'SERVER_API_BASE_URL',
        'AI_FEATURES_ENABLED',
        'OLLAMA_BASE_URL',
        'OLLAMA_DEFAULT_MODEL',
        'LAN_HOST'
    )
    $backendAllowedEnvironmentKeys = @(
        'APP_ENV',
        'APP_NAME',
        'BACKEND_PORT',
        'FRONTEND_PORT',
        'DATABASE_URL',
        'JWT_SECRET_KEY',
        'ADMIN_SESSION_COOKIE_NAME',
        'ACCESS_TOKEN_TTL_MINUTES',
        'ADMIN_USERNAME',
        'ADMIN_PASSWORD',
        'CSRF_COOKIE_NAME',
        'NEWSLETTER_IMPORT_ROOT_CONTAINER',
        'CIVIL_AIRCRAFT_ROOT',
        'DOCUMENT_ROOT',
        'NSA_ROOT',
        'STORAGE_ROOT',
        'THUMBNAILS_DIR_NAME',
        'ATTACHMENTS_DIR_NAME',
        'MARKDOWN_DIR_NAME',
        'CORS_ORIGINS',
        'NEXT_PUBLIC_API_BASE_URL',
        'SERVER_API_BASE_URL',
        'AI_FEATURES_ENABLED',
        'OLLAMA_BASE_URL',
        'OLLAMA_DEFAULT_MODEL',
        'LAN_HOST'
    )
    $requiredEnvironmentKeys = @(
        'APP_ENV', 'DATABASE_URL', 'JWT_SECRET_KEY', 'ADMIN_USERNAME', 'ADMIN_PASSWORD'
    )
    $phaseOrder = @{
        prepared = 0
        db_committed = 1
        root_env_promoted = 2
        backend_env_promoted = 3
        credentials_promoted = 4
        complete = 5
    }
    return [PSCustomObject]@{
        ProductionWorkspace = $productionWorkspace
        ProductRoot = $productRoot
        Retention = '2027-07-10T00:00:00+09:00'
        PhaseOrder = $phaseOrder
        Runtime = @{
            TestMode = $TestMode
            TestWorkspaceRoot = $TestWorkspaceRoot
            ProductionWorkspace = $productionWorkspace
            ProductRoot = $productRoot
            ScriptPath = $ScriptPath
            ExpectedEntryPoint = $ExpectedEntryPoint
            PythonOverride = $PythonOverride
            EnvironmentProfiles = @{
                root = @{
                    AllowedKeys = $rootAllowedEnvironmentKeys
                    RequiredKeys = $requiredEnvironmentKeys
                }
                backend = @{
                    AllowedKeys = $backendAllowedEnvironmentKeys
                    RequiredKeys = $requiredEnvironmentKeys
                }
            }
        }
    }
}

Export-ModuleMember -Function 'New-RotationConfiguration'
