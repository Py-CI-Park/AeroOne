# 단계 11 — 민간 항공기 보고서 모듈 + 콘텐츠 폴더 `_database` 재편

- 분류: **minor (`1.2.0`)** — 신규 읽기 전용 모듈 + 콘텐츠 경로 이전
- dev 브랜치: `1.2.0-dev` / 기능 commit: `9898203`
- 진입점: 대시보드 → "Civil Aircraft Spec Catalog" 카드 → `/reports/civil-aircraft`

---

## 1. 배경

운영자가 콘텐츠 보관 구조를 바꿨다. 기존 `Newsletter/output/` 폴더를 `_database/newsletter/` 로 옮기고 날짜별 디버그 중복본(`Aerospace Daily News_YYYYMMDD_debug.html` 41개)을 정리했으며, 별도로 `_database/civil_aircraft/` 에 "민간 항공기 종합 분석"(상용항공기 종합스펙·시장경쟁분석) HTML 보고서를 두었다. 요구는 두 가지였다 — (a) 백엔드가 새 위치에서 뉴스레터를 읽을 것, (b) 그 보고서를 대시보드에서 바로 열되 뉴스레터와 달리 **달력 없이** 보고서 본문만 보여줄 것.

## 2. 선택한 접근

`import_root` 기본값과 `.env` / `.env.example` / `setup.bat` / `setup_offline.bat` / `docker-compose.yml` / `.gitignore` 를 `_database/newsletter` 로 일괄 이전하고, 신규 `civil_aircraft_root`(`./_database/civil_aircraft`) 설정을 추가했다. 보고서는 뉴스레터 모듈에 끼워넣지 않고 **별도 `reports` 모듈**의 읽기 전용 엔드포인트 `GET /api/v1/reports/civil-aircraft/content/html` 로 제공한다 — DB·달력·슬러그가 없는 정적 단일 보고서이기 때문이다. 다만 폐쇄망 순도(외부 자동 요청 0)를 위해 **뉴스레터와 똑같은 `HtmlRenderService` sanitize**(외부 `<link>`/외부 `src` 차단, 인라인 스크립트 보존)를 그대로 재사용한다. 프런트는 달력 없는 `/reports/civil-aircraft` 페이지에서 `HtmlViewer`(샌드박스 iframe)로 렌더하고, 대시보드에 active 카드 1개를 추가했다(상단 active/coming 카운트는 `MODULES` 에서 파생). `_database` 는 운영 콘텐츠라 `.gitignore` 로 두되 `offline_package.bat` robocopy 가 ZIP 에는 포함한다.

## 3. 검토하고 제외한 대안

- **(a) 보고서를 프런트 정적 자산으로 번들** — 폐쇄망 sanitize 로직을 TS 로 재구현해야 하고 백엔드 파이프라인과 이원화돼 제외.
- **(b) 뉴스레터 모듈에 보고서를 편입** — 달력/DB/슬러그가 불필요해 별도 read-only 모듈로 분리.
- **(c) 디버그 `_debug.html` 을 `newsletter_*.html` 로 개명** — 같은 날짜의 기존 파일과 충돌하고 정책상 import/공개 제외 대상이라 운영자 확인 후 삭제로 결정.

## 4. 코드 (진실 원천)

| 영역 | 위치 |
|---|---|
| import root / civil_aircraft 설정 | `backend/app/core/config.py` (`newsletter_import_root_container='./_database/newsletter'`, `civil_aircraft_root='./_database/civil_aircraft'`, `civil_aircraft_root_path`) |
| 보고서 엔드포인트 | `backend/app/modules/reports/api/public.py` (`/civil-aircraft/content/html`, `_latest_report` 가 최신 비-`_debug` html 선택, `HtmlRenderService` 재사용, 404 가드) |
| 라우터 등록 | `backend/app/main.py` (`/api/v1/reports`) |
| 프런트 페이지(달력 없음) | `frontend/app/reports/civil-aircraft/page.tsx` + `frontend/components/reports/civil-aircraft-report.tsx`(`'use client'` 래퍼) |
| 서버 fetch | `frontend/lib/api.ts` (`fetchCivilAircraftReport`) |
| 대시보드 카드 | `frontend/app/page.tsx` (`MODULES` active 카드 + 파생 카운트) |

## 5. 회귀 방지

- 백엔드: `backend/tests/integration/test_reports_api.py` (200+sanitize+CSP / 404 / `_debug` 제외 3건), `backend/tests/conftest.py` (tmp `civil_aircraft_root` 격리 — 실 폴더 미접근), `backend/tests/unit/shared/test_windows_batch_scripts.py` (setup 가 `_database/newsletter`·`_database/civil_aircraft` 생성 + env 기록 단언).
- 프런트: `frontend/tests/app/civil-aircraft-report-page.test.tsx` (렌더 / **달력 testid 부재** / 폴백 2건), `frontend/tests/app/home-page.test.tsx` (카드 href·라벨·파생 카운트).

## 6. 검증 게이트

- backend `pytest tests`: **99 passed**
- frontend Vitest: **80 passed** (31 files)
- `tsc --noEmit`: exit 0 · `next build`: exit 0 (`/reports/civil-aircraft` 라우트 컴파일)
- 리뷰: critic(Opus) **APPROVED** (CRITICAL/MAJOR 0)
- 라이브 HTTP(0.0.0.0, 새 경로): reports `200`(실 보고서), 뉴스레터 calendar `200`(자동 동기화), 대시보드 카드/href, `/reports/civil-aircraft` `200`·달력 testid 0.

## 7. 후속 / 연관

- 같은 IP 다른 포트·외부 서비스 허브로 대시보드를 확장하는 계획은 문서로만 선반영돼 있다: [`docs/superpowers/plans/2026-06-04-dashboard-external-service-panel.md`](../superpowers/plans/2026-06-04-dashboard-external-service-panel.md). 그 §2 호스트 제약(포트 링크는 서버가 호스트를 추측하지 말고 브라우저 접속 호스트 기준)은 1.1.1 의 0.0.0.0 리다이렉트 버그와 같은 뿌리다.
