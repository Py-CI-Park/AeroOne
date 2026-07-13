param(
  [Parameter(Mandatory = $true)][string]$Log,
  [Parameter(Mandatory = $true)][string]$Status
)

# Task 3 비-credential backend 회귀. credential-rotation 게이트는 focused suite로
# 별도 검증했으므로, 나머지 ~268개 테스트(newsletter/admin/auth/ai/collections 등)만
# 실행해 main.py maintenance-gate import 등 변경의 회귀 여부를 확인한다.

$ErrorActionPreference = 'Continue'
$py = 'D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe'
$backend = 'D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/backend'

Set-Location $backend
$env:PYTHONPATH = '.'

"START $(Get-Date -Format o) pid=$PID" | Out-File -FilePath $Status -Encoding utf8
"cwd=$backend" | Out-File -FilePath $Status -Append -Encoding utf8

& $py -m pytest tests `
  --ignore-glob='*credential_rotation*' `
  --ignore-glob='*windows_dpapi*' `
  -q -p no:cacheprovider *>&1 | Tee-Object -FilePath $Log
$code = $LASTEXITCODE

"EXITCODE $code" | Out-File -FilePath $Status -Append -Encoding utf8
"END $(Get-Date -Format o)" | Out-File -FilePath $Status -Append -Encoding utf8
