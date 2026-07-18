AeroOne Leantime Co-Deploy Stack (portable) — v3.9.8
=====================================================

This is the SEPARATE Leantime import for AeroOne. It bundles a portable
PHP + MariaDB + Leantime so Leantime actually runs on a closed-network
Windows PC without installing anything. It is shipped apart from the main
AeroOne offline ZIP so that ZIP stays lightweight and the AGPL (Leantime) /
GPL (MariaDB) binaries are isolated in their own import.

Components
----------
  php/        PHP 8.3.32 (NTS x64)          — PHP-3.01
  mariadb/    MariaDB 11.4.8 (winx64)       — GPL-2.0
  leantime/   Leantime v3.9.8               — AGPL-3.0 (official, unmodified)

First-time setup (run once)
---------------------------
  1. Extract this ZIP to a stable folder next to AeroOne, e.g. D:\AeroOne-Leantime-Stack\
  2. Double-click  setup-leantime-stack.bat
       - generates php\php.ini, initializes MariaDB, creates the leantime DB,
         installs the schema and the first admin account.
       - the window stays open (pause) so you can read the result; set
         AEROONE_LT_NO_PAUSE=1 to suppress the pause in automation.
       - admin/DB credentials: set from the initial env. If LEANTIME_ADMIN_PASSWORD /
         LEANTIME_DB_PASSWORD are not provided via env (nor already in leantime.env),
         setup GENERATES a strong random one PER INSTALL (no shared hardcoded password).
         The final values are persisted to leantime.env in this stack folder and reused by
         start-leantime-stack.bat. Read leantime.env for the admin login. Override before
         running via env vars LEANTIME_ADMIN_EMAIL / LEANTIME_ADMIN_PASSWORD /
         LEANTIME_DB_PASSWORD. Keep leantime.env private; delete it + re-run setup to rotate.
       - note: db:migrate may print an AuthorizationException about the demo
         project (tickets.create) — schema and admin account are still created;
         log in and create your own project.

Day-to-day
----------
  start-leantime-stack.bat   -> starts MariaDB (127.0.0.1:3307) + Leantime web (0.0.0.0:8081)
                                APP_URL defaults to the auto-detected LAN IPv4 so other
                                PCs on the LAN get working links/assets; override with
                                LEANTIME_APP_URL (e.g. http://192.168.0.10:8081).
  stop-leantime-stack.bat    -> stops both (addressed by window title; unrelated php/mariadbd untouched)

AeroOne integration
-------------------
  AeroOne's dashboard Leantime card + status badge probe http://127.0.0.1:8081 by
  default. Once this stack is running, the badge turns ready and the launch button
  opens Leantime. AeroOne integrates only over Leantime's official HTTP surface — it
  never shares AeroOne's database, session, or cookies with Leantime.

Ports (override via env before setup/start)
-------------------------------------------
  LEANTIME_PORT      web        (default 8081)
  LEANTIME_DB_PORT   MariaDB    (default 3307, loopback only)
  LEANTIME_APP_URL   absolute base URL used in pages (default: auto LAN IP, fallback localhost)

Notes
-----
  - Redis is not required; sessions use the local file driver.
  - The Leantime news service is disabled (airgapped).
  - This is the official, unmodified Leantime release — no core/plugin patches.
