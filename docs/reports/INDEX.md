# 단계별 변경 보고서 색인

폐쇄망 운영 보강 4단계 + 기능 모듈 4건(읽음추적·민간 항공기 보고서·문서 보관소·컬렉션 프록시/Civil·NSA·사다리)의 의도·합의안·구현·검증을 단일 commit 단위로 묶어 둔 보고서 8종 입니다. 본 디렉토리는 "왜 그렇게 만들었는가" 의 진실 원천이며, "어떻게 사용하는가" 는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) 와 [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md) 에 있습니다.

---

## 권장 읽기 순서

1. [단계 8 — 시뮬레이션](phase-8-offline-simulation.md) — 변경 직전 운영 신뢰도 확보
2. [단계 6 — `closed_network` 모드](phase-6-app-env-production.md) — 정책 합의
3. [단계 7 — `--allow-host` LAN 모드](phase-7-lan-mode.md) — 운영 폭 확장
4. [단계 9 — `ensure_db_state.py` docstring](phase-9-docstring.md) — 코드 안 진실 원천 매듭

---

## 단계별 요약

### 단계 6 — `closed_network` 모드 신설

- 파일: [`phase-6-app-env-production.md`](phase-6-app-env-production.md) (151줄)
- commit: `f43ae04`
- 무엇: `app_env` Literal 에 `closed_network` 추가. secure cookie 는 OFF 유지하면서 `JWT_SECRET_KEY` / `ADMIN_PASSWORD` 강도 검증을 강제.
- 코드: `backend/app/core/config.py:14, 82-95`
- 회귀 방지: `backend/tests/unit/test_config.py` (10건)

### 단계 7 — `--allow-host` LAN 운영 모드

- 파일: [`phase-7-lan-mode.md`](phase-7-lan-mode.md) (119줄)
- commit: `7a6879e`
- 무엇: 옵션 1개로 backend 호스트, frontend 호스트, CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL, 자동 오픈 URL 5자리를 일괄 LAN 모드로 전환.
- 코드: `setup_offline.bat`, `start_offline.bat`, `scripts/start_frontend_offline.cmd`
- 회귀 방지: `backend/tests/unit/shared/test_windows_batch_scripts.py` (--allow-host 6건 + 기존 11건)

### 단계 8 — 폐쇄망 배포 시뮬레이션

- 파일: [`phase-8-offline-simulation.md`](phase-8-offline-simulation.md) (205줄)
- commit: `d2cec35`
- 무엇: dry-run 3종 (setup_offline / start_offline / offline_package) + 라이브 5단계 검증 (health, list, login) + 실 PC 시뮬레이션 플레이북.
- 부수: `docs/runbook/windows-offline.md` §10 의 `?limit=1` 잘못된 가이드 정정.

### 단계 9 — `ensure_db_state.py` docstring + 단위 테스트

- 파일: [`phase-9-docstring.md`](phase-9-docstring.md) (73줄)
- commit: `2e69b4b`
- 무엇: 종료 코드 0/1/2/3 의 의미를 모듈/함수 docstring 에 직접 새기고, 4분기를 회귀 차단하는 단위 테스트 7건 추가.
- 코드: `backend/scripts/ensure_db_state.py`
- 회귀 방지: `backend/tests/unit/test_ensure_db_state.py` (7건)

### 단계 10 — IP 기반 읽음추적(열람 횟수) 모듈

- 파일: [`phase-10-read-tracking.md`](phase-10-read-tracking.md)
- 분류: minor (`1.1.0`) — 신규 모듈. commit: `2ec9016` (dev 브랜치 `1.1.0-dev`)
- 무엇: 브라우저 직접 호출 read-beacon 으로 접속 IP 를 잡아 `(newsletter_id, client_ip)` 30분 디바운스 upsert 로 열람 횟수를 집계하고, 관리자만 조회·수동 purge. SSR loopback 우회가 핵심.
- 코드: `backend/app/modules/read_tracking/`, `frontend/components/newsletter/read-beacon.tsx`, `frontend/app/admin/read-events/`
- 회귀 방지: `backend/tests/unit/read_tracking/` (6), `backend/tests/integration/test_read_tracking_api.py` (7), frontend Vitest 6건

### 단계 11 — 민간 항공기 보고서 모듈 + 콘텐츠 폴더 `_database` 재편

- 파일: [`phase-11-civil-aircraft-report.md`](phase-11-civil-aircraft-report.md)
- 분류: minor (`1.2.0`) — 신규 read-only 모듈 + 콘텐츠 경로 이전. commit: `9898203` (dev 브랜치 `1.2.0-dev`)
- 무엇: `Newsletter/output` → `_database/newsletter` 이전(+디버그 41개 정리), `_database/civil_aircraft` 의 단일 HTML 보고서를 뉴스레터와 동일 sanitize 로 제공하는 `GET /api/v1/reports/civil-aircraft/content/html`, 달력 없는 `/reports/civil-aircraft` 페이지 + 대시보드 active 카드.
- 코드: `backend/app/modules/reports/`, `backend/app/core/config.py`(`civil_aircraft_root`), `frontend/app/reports/civil-aircraft/`, `frontend/components/reports/`
- 회귀 방지: `backend/tests/integration/test_reports_api.py` (3), `frontend/tests/app/civil-aircraft-report-page.test.tsx` (2), `home-page.test.tsx` 카드

### 단계 12 — 문서(Document) 보관소 모듈

- 파일: [`phase-12-document-module.md`](phase-12-document-module.md)
- 분류: minor (`1.3.0`) — 신규 read-only 모듈. dev 브랜치 `1.3.0-dev`
- 무엇: `_database/document` 의 HTML 을 `rglob` 로 재귀 수집해 폴더 트리로 목록화(`GET /api/v1/documents/list`)하고, 선택 1개를 뉴스레터와 동일 sanitize 로 제공(`GET /api/v1/documents/content/html?path=`, path-guard 404/400). 좌측 접을 수 있는 폴더 트리 + 우측 `HtmlViewer` 의 `/documents` 페이지 + 대시보드 active 카드 + 헤더 네비.
- 코드: `backend/app/modules/documents/`, `backend/app/core/config.py`(`document_root`), `frontend/app/documents/`, `frontend/components/documents/`, `frontend/components/layout/app-shell.tsx`
- 회귀 방지: `backend/tests/integration/test_documents_api.py` (5), `frontend/tests/app/documents-page.test.tsx` (3), `frontend/tests/components/documents-workspace.test.tsx` (4), `home-page.test.tsx` 카드/카운트

### 단계 13 — 컬렉션 same-origin 프록시 + Civil/NSA 목록화 + 사다리 게임

- 파일: [`phase-13-collections-proxy-and-features.md`](phase-13-collections-proxy-and-features.md)
- 분류: minor (`1.4.0`) — 외부접속 버그 수정 + 신규 모듈/페이지 다수. dev 브랜치 `1.4.0-dev`
- 무엇: Document/Civil/NSA 본문을 same-origin BFF 프록시(`/api/frontend/collections/[...segments]`)로 받아 **다른 PC 접속 시 "failed to fetch" 해결**(브라우저가 `localhost` 직접 호출 안 함). 백엔드 `HtmlCollectionService` + 화이트리스트 라우터(`/api/v1/collections/{document,civil,nsa}`)로 일반화하고 `documents`/`reports` 는 위임. Civil 다중 카탈로그 목록, 비번(0000) 가림막 NSA 탭, 사다리 게임(`/games/ladder`) 추가. Document 목록 기본 접힘, 뉴스레터 달력 접힘 시 컴팩트. 상단 네비는 3개 유지.
- 코드: `backend/app/modules/collections/`, `backend/app/core/config.py`(`nsa_root`), `frontend/lib/collection-proxy.ts`, `frontend/app/api/frontend/collections/`, `frontend/components/collections/`, `frontend/components/games/`, `frontend/app/{nsa,games/ladder}/`, `frontend/app/reports/civil-aircraft/`
- 회귀 방지: `backend/tests/integration/test_collections_api.py`, `frontend/tests/app/api/frontend/collections-route.test.ts`, `api.test.ts`(C1 가드), `collection-password-gate.test.tsx`, `ladder-game.test.tsx`, 갱신된 `documents-workspace`/`civil-aircraft-report-page`/`home-page`/`app-shell`/`newsletter-date-calendar` 테스트

---

## 보고서가 다루지 않는 자리

- 운영 절차: [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md), [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md)
- 코드 진실 원천: 각 보고서의 "코드" 항목 + [`docs/INDEX.md`](../INDEX.md) §6
- 회귀 테스트 인벤토리: [`docs/INDEX.md`](../INDEX.md) §7
