param(
  [Parameter(Mandatory = $true)][string]$Log,
  [Parameter(Mandatory = $true)][string]$Status
)

# Task 3 credential-rotation focused suite (핸드오프 gate "focused 85").
# 369 full은 280개 비관련 fast 테스트 + 경합으로 crawl하므로, credential 게이트만
# 격리 실행해 clean 판정한다. 로그+exit code를 디스크에 보존.

$ErrorActionPreference = 'Continue'
$py = 'D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe'
$backend = 'D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/backend'

Set-Location $backend
$env:PYTHONPATH = '.'

$files = @(
  Get-ChildItem -Path `
    'tests/integration/test_credential_rotation_*.py', `
    'tests/unit/test_credential_rotation*.py', `
    'tests/unit/shared/test_credential_rotation_*.py', `
    'tests/unit/test_windows_dpapi_zeroization.py' `
    -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
) | Sort-Object -Unique

"START $(Get-Date -Format o) pid=$PID" | Out-File -FilePath $Status -Encoding utf8
"cwd=$backend" | Out-File -FilePath $Status -Append -Encoding utf8
"files=$($files.Count)" | Out-File -FilePath $Status -Append -Encoding utf8

& $py -m pytest $files -vv --tb=short -p no:cacheprovider *>&1 | Tee-Object -FilePath $Log
$code = $LASTEXITCODE

"EXITCODE $code" | Out-File -FilePath $Status -Append -Encoding utf8
"END $(Get-Date -Format o)" | Out-File -FilePath $Status -Append -Encoding utf8
