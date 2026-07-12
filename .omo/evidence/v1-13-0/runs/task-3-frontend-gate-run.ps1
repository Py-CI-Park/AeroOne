param(
  [Parameter(Mandatory = $true)][string]$Log,
  [Parameter(Mandatory = $true)][string]$Status
)

# Task 3 frontend 게이트: hotfix worktree frontend 소스를 검증된 root
# node_modules(junction)로 vitest full / typecheck / production build 순차 실행.
# 각 단계 exit code를 status 파일에 남겨 세션이 끊겨도 회수 가능하게 한다.

$ErrorActionPreference = 'Continue'
$fe = 'D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/frontend'
$npm = 'C:/Program Files/nodejs/npm.cmd'

Set-Location $fe
"START $(Get-Date -Format o) pid=$PID" | Out-File -FilePath $Status -Encoding utf8
"cwd=$fe" | Out-File -FilePath $Status -Append -Encoding utf8

"==== vitest run ====" | Tee-Object -FilePath $Log -Append | Out-Null
& $npm run test *>&1 | Tee-Object -FilePath $Log -Append
$vitest = $LASTEXITCODE
"VITEST_EXIT $vitest" | Out-File -FilePath $Status -Append -Encoding utf8

"==== typecheck ====" | Tee-Object -FilePath $Log -Append | Out-Null
& $npm run typecheck *>&1 | Tee-Object -FilePath $Log -Append
$tc = $LASTEXITCODE
"TYPECHECK_EXIT $tc" | Out-File -FilePath $Status -Append -Encoding utf8

"==== build ====" | Tee-Object -FilePath $Log -Append | Out-Null
& $npm run build *>&1 | Tee-Object -FilePath $Log -Append
$build = $LASTEXITCODE
"BUILD_EXIT $build" | Out-File -FilePath $Status -Append -Encoding utf8

"END $(Get-Date -Format o)" | Out-File -FilePath $Status -Append -Encoding utf8
