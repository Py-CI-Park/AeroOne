@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ==========================================================================
REM Leantime bundle SHA-256 verifier.
REM
REM Validates the on-disk Leantime co-deploy bundle - Leantime, PHP-FastCGI,
REM MariaDB, IIS prerequisite archives - against the pinned checksums in
REM packaging\leantime\leantime-bundle.manifest.json. Policy: AeroOne ships
REM the official unmodified Leantime release - no plugin patch, no core
REM patch. See manifest "policy" block and packaging\leantime\NOTICE.txt.
REM
REM Usage: verify-bundle.bat <bundle_dir> [manifest_path]
REM   bundle_dir     directory containing the component files named by the
REM                  manifest "filename" fields (required).
REM   manifest_path  defaults to packaging\leantime\leantime-bundle.manifest.json
REM                  relative to the repo root (optional).
REM
REM Log contract: [LEANTIME][VERIFY] <name> ok|mismatch|missing|placeholder
REM   one line per manifest component.
REM
REM Exit codes:
REM   0 = every non-placeholder component matched (manifest parsed OK).
REM   2 = at least one component mismatched or its file is missing.
REM   1 = usage/manifest/parse error (bundle dir or manifest not found/unreadable).
REM
REM Placeholder entries where sha256 equals the literal placeholder string
REM are reported as "placeholder" and are SKIPPED from the pass/fail
REM decision - the operator has not filled in the real checksum yet.
REM ==========================================================================

set "BUNDLE_DIR=%~1"
set "MANIFEST_PATH=%~2"

if "%BUNDLE_DIR%"=="" (
  echo [LEANTIME][ERROR] Usage: verify-bundle.bat ^<bundle_dir^> [manifest_path]
  exit /b 1
)

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "AEROONE_ROOT=%SCRIPT_DIR%\..\.."
pushd "%AEROONE_ROOT%" & set "AEROONE_ROOT=%CD%" & popd

if "%MANIFEST_PATH%"=="" set "MANIFEST_PATH=%AEROONE_ROOT%\packaging\leantime\leantime-bundle.manifest.json"

if not exist "%BUNDLE_DIR%" (
  echo [LEANTIME][ERROR] bundle directory not found: "%BUNDLE_DIR%"
  exit /b 1
)
if not exist "%MANIFEST_PATH%" (
  echo [LEANTIME][ERROR] manifest not found: "%MANIFEST_PATH%"
  exit /b 1
)

echo [LEANTIME][INFO ] bundle dir : %BUNDLE_DIR%
echo [LEANTIME][INFO ] manifest   : %MANIFEST_PATH%

REM Paths are passed via $env: (not raw string interpolation) so quotes/spaces
REM in either path never break the PowerShell command line.
set "LT_BUNDLE_DIR=%BUNDLE_DIR%"
set "LT_MANIFEST_PATH=%MANIFEST_PATH%"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ph='<fill-on-staging>'; try { $m = Get-Content -Raw -LiteralPath $env:LT_MANIFEST_PATH | ConvertFrom-Json } catch { Write-Host ('[LEANTIME][ERROR] failed to parse manifest: ' + $_.Exception.Message); exit 1 }; if (-not $m.components -or $m.components.Count -eq 0) { Write-Host '[LEANTIME][ERROR] manifest has no components array'; exit 1 }; $failed = $false; $verified = 0; $placeholder = 0; foreach ($c in $m.components) { $name = $c.name; $file = Join-Path $env:LT_BUNDLE_DIR $c.filename; $expected = [string]$c.sha256; if ($expected -eq $ph) { Write-Host ('[LEANTIME][VERIFY] ' + $name + ' placeholder'); $placeholder++; continue }; if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Write-Host ('[LEANTIME][VERIFY] ' + $name + ' missing'); $failed = $true; continue }; $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash; if ($actual.ToLowerInvariant() -eq $expected.ToLowerInvariant()) { Write-Host ('[LEANTIME][VERIFY] ' + $name + ' ok'); $verified++ } else { Write-Host ('[LEANTIME][VERIFY] ' + $name + ' mismatch'); $failed = $true } }; Write-Host ('[LEANTIME][INFO ] ' + $verified + ' verified / ' + $placeholder + ' placeholders'); if (-not $failed -and $verified -eq 0) { Write-Host '[LEANTIME][WARN ] no component checksums were verified (all placeholders); fill sha256 values on the staging PC before trusting this bundle' }; if ($failed) { exit 2 } else { exit 0 }"
set "PS_EXIT=%errorlevel%"

set "LT_BUNDLE_DIR="
set "LT_MANIFEST_PATH="

if "%PS_EXIT%"=="0" (
  echo [LEANTIME][INFO ] verification passed ^(see verified/placeholder summary above^).
) else if "%PS_EXIT%"=="2" (
  echo [LEANTIME][ERROR] verification failed: mismatch or missing component^(s^).
) else (
  echo [LEANTIME][ERROR] verification could not run ^(manifest/parse error^).
)

exit /b %PS_EXIT%
