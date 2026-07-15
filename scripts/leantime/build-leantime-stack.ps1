#Requires -Version 5.1
<#
  .SYNOPSIS
  Builds the separate AeroOne Leantime co-deploy stack import
  (AeroOne-Leantime-Stack-v3.9.8-<stamp>.zip): portable PHP + MariaDB + Leantime
  plus the setup/start/stop orchestration. Ships alongside AeroOne but as its own
  import so the main offline ZIP stays lightweight and AGPL/GPL binaries are isolated.

  Components are downloaded (or reused from leantime_stack\downloads) and verified
  against pinned SHA-256 values before assembly. Run on the internet-connected PC.
#>
[CmdletBinding()]
param(
  [string]$Stamp = (Get-Date -Format 'yyyyMMdd-HHmmss'),
  [switch]$SkipDownload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Work = Join-Path $RepoRoot 'leantime_stack'
$Downloads = Join-Path $Work 'downloads'
$Staging = Join-Path $Work 'staging'
$Dist = Join-Path $RepoRoot 'dist'
$ScriptsSrc = Join-Path $RepoRoot 'scripts\leantime\stack'

$Components = @(
  @{ name='php';      file='php-8.3.32-nts-Win32-vs16-x64.zip'; sha256='67c724e7b675b50d8f0476d816c3e2a3064ce3a53d572575d63c321cc0a3a6cf'; url='https://windows.php.net/downloads/releases/php-8.3.32-nts-Win32-vs16-x64.zip'; dest='php';      strip=$false }
  @{ name='mariadb';  file='mariadb-11.4.8-winx64.zip';         sha256='ed86e93157af46317bb49161451c2ec258498a6fa8e68ca821ef1d780d855e6b'; url='https://archive.mariadb.org/mariadb-11.4.8/winx64-packages/mariadb-11.4.8-winx64.zip'; dest='mariadb'; strip=$true }
  @{ name='leantime'; file='Leantime-v3.9.8.zip';               sha256='28066ea769c3ccc25e7abed3d5191ac0b1fe89e0be2ca8314a53d397ac2439df'; url='https://github.com/Leantime/leantime/releases/download/v3.9.8/Leantime-v3.9.8.zip'; dest='leantime'; strip=$false }
)

New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
New-Item -ItemType Directory -Path $Dist -Force | Out-Null

function Get-Sha256([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }

foreach ($c in $Components) {
  $target = Join-Path $Downloads $c.file
  if (-not (Test-Path $target) -and -not $SkipDownload) {
    Write-Host "[STACK] downloading $($c.name) ..."
    Invoke-WebRequest -UseBasicParsing -Uri $c.url -OutFile $target
  }
  if (-not (Test-Path $target)) { throw "missing component $($c.file) (run without -SkipDownload)" }
  $got = Get-Sha256 $target
  if ($got -ne $c.sha256) { throw "SHA-256 mismatch for $($c.file): expected $($c.sha256) got $got" }
  Write-Host "[STACK] verified $($c.file) ($got)"
}

if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Path $Staging -Force | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($c in $Components) {
  $src = Join-Path $Downloads $c.file
  $out = Join-Path $Staging $c.dest
  New-Item -ItemType Directory -Path $out -Force | Out-Null
  Write-Host "[STACK] extracting $($c.name) -> $($c.dest)"
  if ($c.strip) {
    $tmp = Join-Path $Staging ("_x_" + $c.dest)
    [System.IO.Compression.ZipFile]::ExtractToDirectory($src, $tmp)
    $top = Get-ChildItem -Directory $tmp | Select-Object -First 1
    Get-ChildItem -Force $top.FullName | Move-Item -Destination $out -Force
    Remove-Item -Recurse -Force $tmp
  } else {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($src, $out)
  }
}

# Orchestration scripts + operator README at the stack root. Batch files MUST ship
# with CRLF line endings: cmd.exe mis-parses LF-only .bat files (setlocal -> 'tlocal',
# chcp -> 'cp'), which breaks the closed-network install. Copy-Item would preserve
# whatever the builder checkout produced (LF on a checkout that did not apply the
# .gitattributes eol=crlf rule), so normalize to CRLF on stage instead of trusting it.
function Copy-BatchAsCrlf {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $text = [System.IO.File]::ReadAllText($Source)
    $text = $text -replace "`r`n", "`n"
    $text = $text -replace "`r", "`n"
    $text = $text -replace "`n", "`r`n"
    [System.IO.File]::WriteAllText($Destination, $text, (New-Object System.Text.UTF8Encoding($false)))
}
foreach ($bat in @('setup-leantime-stack.bat', 'start-leantime-stack.bat', 'stop-leantime-stack.bat')) {
    Copy-BatchAsCrlf (Join-Path $ScriptsSrc $bat) (Join-Path $Staging $bat)
    Write-Host "[STACK] staged (CRLF-normalized) $bat"
}
$readme = Join-Path $ScriptsSrc 'README-LEANTIME-STACK.txt'
if (Test-Path $readme) { Copy-Item $readme (Join-Path $Staging 'README.txt') -Force }

$zipName = "AeroOne-Leantime-Stack-v3.9.8-$Stamp.zip"
$zipPath = Join-Path $Dist $zipName
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Write-Host "[STACK] zipping -> $zipName"
[System.IO.Compression.ZipFile]::CreateFromDirectory($Staging, $zipPath)
$zipSha = Get-Sha256 $zipPath
Set-Content -Path "$zipPath.sha256" -Value "$zipSha  $zipName" -Encoding ascii -NoNewline

Write-Host "[STACK][OK] $zipPath"
Write-Host "[STACK][OK] size=$((Get-Item $zipPath).Length) sha256=$zipSha"
