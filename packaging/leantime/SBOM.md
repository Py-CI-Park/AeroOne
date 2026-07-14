# Leantime Co-Deploy Bundle — SBOM (placeholder)

This is a component/version/license/source table for the Leantime
co-deploy bundle packaged alongside AeroOne. Fill in the `SHA-256` column
from the staging build (see `leantime-bundle.manifest.json`); until then
entries carry the placeholder `<fill-on-staging>`.

Policy: AeroOne ships the **official, unmodified** Leantime release — no
plugin patch, no core patch (see `NOTICE.txt` and the manifest `policy`
block).

| Component     | Version | License              | SHA-256              | Source URL |
|---------------|---------|-----------------------|-----------------------|------------|
| leantime      | 3.9.8   | AGPL-3.0              | `28066ea769c3ccc25e7abed3d5191ac0b1fe89e0be2ca8314a53d397ac2439df` | https://github.com/Leantime/leantime/releases/tag/v3.9.8 |
| php-fastcgi   | 8.2     | PHP-3.01              | `<fill-on-staging>`   | https://windows.php.net/download |
| mariadb       | 11.4    | GPL-2.0               | `<fill-on-staging>`   | https://mariadb.org/download/ |
| iis-prereq    | n/a     | Microsoft-Windows-Feature | `<fill-on-staging>` | https://learn.microsoft.com/iis/ |

Notes:
- This table is generated/maintained manually until an automated SBOM
  export from the staging build process replaces it; keep it in sync with
  `leantime-bundle.manifest.json` (same components, same order).
- `verify-bundle.bat` cross-checks the manifest SHA-256 values against the
  actual bundle files at install/verify time; this file is documentation,
  not a verification input.
