param(
  [Parameter(Mandatory = $true)][string]$Log,
  [Parameter(Mandatory = $true)][string]$Status
)

# Task 3 backend full 재실행 래퍼.
# 이전 세션이 usage limit로 실패 node를 잃은 문제를 방지하기 위해
# stdout/stderr 전체를 로그 파일에 tee 하고, 실제 child exit code를
# 별도 status 파일에 남겨 세션이 끊겨도 다음 에이전트가 회수하도록 한다.

$ErrorActionPreference = 'Continue'
$py = 'D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe'
$backend = 'D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/backend'

Set-Location $backend
$env:PYTHONPATH = '.'

"START $(Get-Date -Format o) pid=$PID" | Out-File -FilePath $Status -Encoding utf8
"cwd=$backend" | Out-File -FilePath $Status -Append -Encoding utf8

& $py -m pytest tests -vv --tb=short -p no:cacheprovider *>&1 | Tee-Object -FilePath $Log
$code = $LASTEXITCODE

"EXITCODE $code" | Out-File -FilePath $Status -Append -Encoding utf8
"END $(Get-Date -Format o)" | Out-File -FilePath $Status -Append -Encoding utf8
