# AeroOne — 주 LAN IPv4 자동 감지 (--allow-host=auto 용).
# 기본 게이트웨이가 있는 Up 어댑터의 IPv4 를 우선(주 회선)하고, 폐쇄망처럼 게이트웨이가
# 없으면 loopback(127.*)/APIPA(169.254.*) 가 아닌 사설 IPv4(192.168 / 10 / 172.16-31)
# 중 첫 번째로 폴백한다. 결과 IP 한 줄만 출력하고, 못 찾으면 아무것도 출력하지 않는다.
$ErrorActionPreference = 'SilentlyContinue'

$ip = $null

$gw = Get-NetIPConfiguration |
  Where-Object { $_.NetAdapter -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway } |
  Select-Object -First 1
if ($gw -and $gw.IPv4Address) {
  $ip = @($gw.IPv4Address)[0].IPAddress
}

if (-not $ip) {
  $candidate = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
      $_.IPAddress -notlike '127.*' -and
      $_.IPAddress -notlike '169.254.*' -and
      (
        $_.IPAddress -like '192.168.*' -or
        $_.IPAddress -like '10.*' -or
        $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
      )
    } |
    Select-Object -First 1
  if ($candidate) { $ip = $candidate.IPAddress }
}

if ($ip) { Write-Output $ip }
