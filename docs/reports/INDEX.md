# 단계별 변경 보고서 색인

폐쇄망 운영 보강 4단계 + 기능 모듈 5건(읽음추적·민간 항공기 보고서·문서 보관소·컬렉션 프록시/Civil·NSA·사다리·Ollama AI 검색) + Open WebUI 참조 연구 1건 + AI 대화 영속화/문서 근거 2차 증분 1건 + 뷰어-에디터/런처·AeroAI·스크롤 수정 1건 + 1.6.2 폐쇄망 smoke 패치 1건 + 1.7.0 AeroAI/Viewer UX 릴리즈 1건 + 대시보드 개발중 섹션/1.7.1 뉴스레터 UX 패치 1건 + 1.8.0 관리자 RBAC·운영 콘솔 1건 + 1.10.0 관리자 권한 강화 1건 + 1.11.0 관리자 콘솔 UX/same-origin 프록시 통합 1건 + 1.12.0 관리자 콘솔 UX/UI 개선 1건의 의도·합의안·구현·검증·후속 후보를 단일 commit 단위로 묶어 둔 보고서 색인입니다. 본 디렉토리는 "왜 그렇게 만들었는가" 의 진실 원천이며, "어떻게 사용하는가" 는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) 와 [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md) 에 있습니다.

---

> **보안 사고 대응 기록**: [`incident-2026-07-10-offline-asset-containment.md`](incident-2026-07-10-offline-asset-containment.md) — 공개 배포 ZIP의 운영 자산 노출을 봉쇄하고 재발 방지 도구(자격증명 회전·패키지 verifier·내부 번들 경계·builder)를 구축한 사고 대응 보고서(redacted, exact 식별자·비밀 미기재).

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


### 단계 14 — 폐쇄망 Ollama AI 채팅 + HTML 본문 검색

- 파일: [`phase-14-ollama-ai-search.md`](phase-14-ollama-ai-search.md)
- 분류: minor (`1.5.0`) — AI 채팅 + 컬렉션 본문 검색.
- 무엇: 대시보드 `AI` 카드에서 `gemma4:12b` 와 채팅하고, `_database` HTML 본문을 SQLite FTS5 로 검색해 `/documents?path=...`, `/reports/civil-aircraft?path=...`, `/nsa?path=...` 로 바로 연다. 브라우저 직접 Ollama 호출 금지, backend-only Ollama, same-origin AI proxy, NSA unlock 전 비노출을 지킨다.
- 코드: `backend/app/modules/ai/`, `backend/app/modules/collections/search_service.py`, `frontend/app/ai/`, `frontend/components/ai/`, `frontend/app/api/frontend/ai/`
- 회귀 방지: `backend/tests/integration/test_ai_api.py`, 갱신된 `test_collections_api.py`, `ai-chat-workspace.test.tsx`, `ai-route.test.ts`, 갱신된 home/collection/DocumentsWorkspace 테스트

### 단계 15 — Open WebUI 참조 기능 연구

- 파일: [`phase-15-openwebui-reference-research.md`](phase-15-openwebui-reference-research.md)
- 분류: research / next minor 후보 (`1.5.x` 또는 `1.6.0`) — 채팅 기록·관리자 AI 설정·계정/권한·지식베이스 참조 연구.
- 무엇: `D:\Chanil_Park\Project\Programming\open-webui` 의 채팅 GUI, 대화 기록, 관리자 메뉴, 계정/RBAC, RAG/Knowledge, 평가/분석 기능을 분석하고 AeroOne 폐쇄망 문서 시스템에 반영할 우선순위와 제외 범위를 정리.
- 후속 후보: AI 대화 저장/목록, 관리자 AI 설정, 문서 근거 프리셋, citation 패널, 사용량/피드백 로그.
---

### 단계 16 — AI 대화 영속화 + 문서 근거 연결 강화 (1.5 2차 증분)

- 파일: [`phase-16-ai-conversation-and-document-grounding.md`](phase-16-ai-conversation-and-document-grounding.md)
- 합의 계획: `.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md` (Architect CLEAR/APPROVE, Critic OKAY) / 실행 원장 `.gjc/ultragoal/` (G001–G008)
- 무엇: `/ai` 대화 영속화(3테이블+Alembic 20260613_0003, 세션쿠키 단독 스코프), 3분할 UI+대화목록, copy/regenerate/stop, 검색결과 선택 후 질문(selected_refs, collections 위임), citation 우측 패널(새 탭+sandboxed 미리보기), 근거 범위 토글(nsa-gated), 보고서 검토 프롬프트 preset.
- 코드: `backend/app/modules/ai/{models,repositories,schemas,service}.py`, `api/public.py`, `collections/search_service.py(load_refs)`, `app/db/session.py(PRAGMA foreign_keys=ON)`, `frontend/components/ai/ai-chat-workspace.tsx`, `frontend/app/api/frontend/ai/*`
- 회귀 방지: backend 162 passed(test_ai_migration/test_ai_conversations/test_ai_chat_refs 신규), frontend 176 passed/46 files(ai-conversations/-controls/-selected-refs/-citation-panel/-scope/-presets 신규)
- 비범위: 계정 신원 2단계, nsa 백엔드 게이트, vector RAG, 서버측 streaming/취소, 공유/export

### 단계 17 — Markdown/HTML 뷰어-에디터 + 런처·AeroAI·HTML 스크롤 수정 (1.6 증분)

- 파일: [`phase-17-viewer-editor-and-launcher-ai-fixes.md`](phase-17-viewer-editor-and-launcher-ai-fixes.md)
- 분류: minor (`1.6.0`) — 신규 `render` 모듈 + `/viewer` 페이지 + 운영 결함 3종 수정. 합의 계획 `.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`(deliberate, Architect pass2 CLEAR/APPROVE, Critic OKAY) / 실행 원장 `.gjc/ultragoal/`(G001–G005)
- 무엇: 런처 행 de-hang(`start_offline.bat --no-pause` + `run_all.bat` 전달), AeroAI "죄송" 무응답 수정(과잉제약 프롬프트 개정 + `_strip_think_blocks` + `OllamaEmptyResponse` 502), HTML 뷰어 content-mode 스크롤 보존(scrollY 복원+threshold+poll, `showFitToggle`), 무상태 `POST /api/v1/render`(md/html 세니타이즈, path 미사용), Markdown/HTML 뷰어-에디터 `/viewer`(File API 로드+편집+빈 샌드박스 iframe 미리보기+Blob 다운로드) + 대시보드 Viewer 카드(active 8).
- 코드: `start_offline.bat`, `scripts/run_all.bat`, `backend/app/modules/ai/{service.py,api/public.py}`, `backend/app/modules/render/`, `backend/app/modules/newsletter/services/html_render_service.py(sanitize_html_fragment)`, `backend/app/main.py`, `frontend/components/newsletter/{html-viewer,newsletter-detail-client}.tsx`, `frontend/components/viewer/viewer-editor.tsx`, `frontend/app/{viewer,api/frontend/render}/`, `frontend/app/page.tsx`
- 회귀 방지: backend 171 passed(test_ai_api +3, test_render_api +6), frontend 188 passed/47 files(html-viewer +3, viewer-editor +5, home-page +1)
- 비범위: 서버측 파일 쓰기, 렌더 프록시 4xx/5xx fall-through, PDF/이미지 뷰어 확장

### 단계 18 — 1.6.1 폐쇄망 smoke 수정 (1.6.2 패치)

- 파일: [`phase-18-closed-network-smoke-fixes.md`](phase-18-closed-network-smoke-fixes.md)
- 분류: patch (`1.6.2`) — 폐쇄망 실사용 테스트에서 확인된 뷰어 크기/스크롤, AeroAI 빈 응답, `run_all.bat` READY 오판, Open Notebook API 연결 실패 보강.
- 무엇: HTML 뷰어 viewport 높이 확대와 full-height scroll ownership 보정, 환경 변수 공백/줄바꿈 API URL 방어, AeroAI reasoning-only 빈 응답 1회 재시도, `run_all.bat` 의 ON API/Frontend/runtime config readiness 확인 및 `--local`/`--allow-host` ON 전달, Open Notebook airgap adapter 의 LAN `API_URL`/`CORS`/비대화형 대기 정리.
- 코드: `frontend/components/newsletter/html-viewer.tsx`, `frontend/components/documents/documents-workspace.tsx`, `frontend/lib/api.ts`, `backend/app/modules/ai/service.py`, `scripts/run_all.bat`, `offline_package.bat`, `../open-notebook/airgap/{3-run.bat,write_env.ps1}`
- 회귀 방지: `frontend/tests/components/{html-viewer,documents-workspace,version-badge}.test.tsx`, `backend/tests/integration/test_ai_api.py`, `backend/tests/unit/shared/test_windows_batch_scripts.py`

### 단계 19 — AeroAI/Viewer UX 강화 + Open Notebook 동거 릴리즈 (1.7.0)

- 파일: [`phase-19-aeroai-viewer-ux-release.md`](phase-19-aeroai-viewer-ux-release.md)
- 분류: minor (`1.7.0`) — 기존 AeroAI/Viewer 표면의 사용자 기능 강화와 Open Notebook co-deploy 릴리즈 절차 정리.
- 무엇: AeroAI 모니터 높이 3분할 레이아웃, 안전한 Markdown 답변 렌더링 + 원문 복사, HTML 본문 검색 결과 새 탭 열기와 navigation URL 방어, 인용 미리보기 전체 보기, Viewer 미리보기 집중/전체화면, Open Notebook 8502/5055/모델 설정/주요 메뉴 스모크.
- 코드: `frontend/components/ai/ai-chat-workspace.tsx`, `frontend/components/viewer/viewer-editor.tsx`, `frontend/components/layout/help-manual-button.tsx`, `frontend/lib/changelog.ts`
- 문서: `README.md`, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/closed-network-install-manual.md`, `docs/runbook/open-notebook-airgap.md`
- 회귀 방지: `frontend/tests/components/{ai-chat-workspace,ai-chat-controls,ai-citation-panel,ai-scope,viewer-editor}.test.tsx`, full frontend Vitest 203 passed, backend pytest 175 passed, `scripts\run_all.bat --dry-run --on-bundle ..\AeroOne-bundle --local`, 브라우저 AeroAI/Viewer/Open Notebook smoke.

### 단계 20 — 대시보드 개발중 섹션 재분류 핸드오프

- 파일: [`phase-20-dashboard-development-section-handoff.md`](phase-20-dashboard-development-section-handoff.md)
- 분류: patch UI 정리 — 대시보드 운영 상태 분류와 핸드오프 문서화.
- 무엇: `개발중` 섹션을 새로 만들고 Viewer/AeroAI/Notebook/Ladder 를 active 카드로 이동, Announcement/Schedule 은 같은 섹션 안의 비활성 `Coming soon` 카드로 유지. 별도 `Coming soon` 섹션 제거. 1.7.1 추가 패치로 뉴스레터 달력 접힘 폭 축소, HTML 다운로드 버튼 강조, 사용법 팝업의 현재 서비스 중/개발중 구분 최신화를 포함.
- 코드: `frontend/app/page.tsx`, `frontend/tests/app/home-page.test.tsx`, `frontend/components/newsletter/newsletters-reading.tsx`, `frontend/components/newsletter/newsletter-date-calendar.tsx`, `frontend/components/newsletter/html-viewer.tsx`, `frontend/components/layout/help-manual-button.tsx`, `frontend/lib/changelog.ts`
- 문서: `README.md`, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/closed-network-install-manual.md`, `docs/runbook/open-notebook-airgap.md`
- 회귀 방지: backend `pytest tests` 175 passed(경고 3), frontend Vitest 205 passed(47 파일), `tsc --noEmit`, `next build`, production browser dashboard/newsletter smoke, Ultragoal review/QA gate.

### 단계 21 — 관리자 RBAC·운영 콘솔·DB 관리 기반 (1.8.0)

- 파일: [`phase-21-admin-rbac-operations-console.md`](phase-21-admin-rbac-operations-console.md)
- 분류: minor (`1.8.0`) — 관리자 권한·감사·운영 콘솔·DB 기반 대시보드 관리 확장.
- 무엇: Open WebUI 벤치마크에서 `admin/user/pending`, additive permissions/groups, 운영 analytics 패턴만 채택해 `require_permission`/CSRF 분리, same-transaction audit, `service_modules` DB 원천, `/admin` 홈 콘솔, 뉴스레터 상태/자산/bulk/taxonomy, 백업 manifest+sha256+restore dry-run, 통합 검색, AI metadata-only 로그를 구현.
- 코드: `backend/app/modules/admin/`, `backend/alembic/versions/20260703_0004_admin_rbac_operations.py`, `frontend/app/admin/page.tsx`, `frontend/components/admin/admin-home-console.tsx`, `frontend/app/page.tsx`
- 회귀 방지: backend `pytest tests` 177 passed(경고 3), frontend Vitest 205 passed(47 파일), `tsc --noEmit`, `next build`, browser dashboard/admin smoke, Ultragoal architect/QA gate CLEAR.

### 단계 22 — 관리자 전용 노출·헤더 정리·모듈 DB 관리 강화·비밀번호 변경 (1.9.0)

- 파일: [`phase-22-operator-visibility-and-module-management.md`](phase-22-operator-visibility-and-module-management.md)
- 분류: minor (`1.9.0`) — 관리자(서버 실행자) 전용 노출 제어와 대시보드 운영 편의 강화.
- 무엇: `service_modules.visibility`(public/admin) 신설로 개발중(Development)·Coming soon 카드와 Admin 메뉴를 관리자에게만 노출, 헤더를 다크·사용법·Admin 순서로 정리, `/admin` 에서 모듈 추가·삭제·노출 대상 관리, 관리자 비밀번호 콘솔 변경, `start_offline` 마이그레이션 preflight 로 stale-DB 500 예방, `개발중` 섹션 라벨 영어(Development)화.
- 코드: `backend/alembic/versions/20260703_0005_service_module_visibility.py`, `backend/app/modules/admin/{models,schemas,api}.py`, `backend/app/modules/auth/{api,schemas,dependencies}.py`, `frontend/components/layout/{app-shell,admin-nav-link,help-manual-button}.tsx`, `frontend/app/page.tsx`, `frontend/components/admin/admin-home-console.tsx`, `frontend/lib/{api,types,server-auth,changelog}.ts`, `start_offline.bat`
- 회귀 방지: backend `pytest tests` 181 passed(경고 3), frontend Vitest 206 passed(47 파일), `tsc --noEmit`, `next build`, sqlite alembic upgrade, 라이브 API/브라우저 smoke(익명 4개 공개 카드·관리자 자격 로그인·관리자 10개 공개 카드).


### 단계 23 — 관리자 권한 강화·NSA 서버측 접근제어·접속자 대시보드 (1.10.0)

- 파일: [`phase-23-admin-authz-hardening.md`](phase-23-admin-authz-hardening.md)
- 분류: minor (`1.10.0`) — 관리자 권한 모델을 사용자/그룹/리소스 단위로 확장하고 문서 컬렉션 읽기 경계를 서버측으로 고정.
- 무엇: `READ_PERMISSION_BY_PREFIX` 권한 상승 경로를 차단하고 `can_read_collection` 단일 정책으로 collections/admin-search/AI 를 통일, NSA 0000 비밀번호 가림막 제거 후 `collections.nsa.read` + `collection:nsa` ResourceGrant 를 요구, 사용자별 유효 권한 기반 메뉴 힌트, 자산/config-health 진단, 사용자·그룹·리소스 권한 CRUD 와 RBAC 매트릭스, 로그인/세션/익명 IP 읽음 추적 접속자 대시보드를 추가.
- 코드: `backend/alembic/versions/20260704_0006_*.py`, `backend/alembic/versions/20260704_0007_*.py`, `backend/app/modules/{admin,auth,collections,ai,read_tracking}/`, `frontend/app/{admin,nsa,ai}/`, `frontend/components/{admin,layout,documents,ai}/`, `frontend/lib/changelog.ts`
- 회귀 방지: backend `pytest tests` 248 passed(경고 3), frontend Vitest 216 passed(49 파일), `tsc --noEmit`, `next build`, alembic upgrades through `20260704_0007`, 단계별 architect/executor QA gate 통과.

### 단계 24 — 관리자 콘솔 UX 재설계·same-origin 인증/관리 프록시 통합 (1.11.0)

- 파일: [`phase-24-admin-console-proxy-redesign.md`](phase-24-admin-console-proxy-redesign.md)
- 분류: minor (`1.11.0`) — 관리자 브라우저 표면을 같은 frontend origin 으로 고정하고 `/admin` 운영 UX 를 탭형 콘솔로 재정리.
- 무엇: 브라우저 로그인/관리자 CRUD 를 `/api/frontend/auth/*`, `/api/frontend/admin/*` same-origin 프록시로 통일, 통합 검색은 `/api/frontend/search/unified` 로 분리, ResourceGrant global/unknown/malformed key 거부, `/admin` 을 모듈/사용자/RBAC/세션/시스템/분류/검색/백업 탭으로 분할, RBAC 권한 체크박스·리소스 grant 드롭다운·NSA 열람권 프리셋·사용자/그룹 선택기·목록 검색/정렬/상태·ARIA Tabs 키보드 접근성을 추가.
- 코드: `backend/app/modules/{admin,auth}/`, `frontend/app/{admin,api/frontend/auth,api/frontend/admin,api/frontend/search}/`, `frontend/components/admin/`, `frontend/lib/{api,server-auth,changelog}.ts`
- 회귀 방지: backend `pytest tests` 265 passed, frontend Vitest 265 passed(56 파일), `tsc --noEmit`, `next build`, 단계별 architect CLEAR 및 executor red-team 통과(`artifacts/qa/1.11.0-admin-proxy/`).

### 단계 25 — 관리자 콘솔 UX/UI 개선 (권한 이해·감사 로그·세션/목록 인체공학·전역 폴리시) (1.12.0)

- 파일: [`phase-25-admin-console-ux-polish.md`](phase-25-admin-console-ux-polish.md)
- 분류: minor (`1.12.0`) — 프론트-only 관리자 콘솔 UX/UI 개선(백엔드 인가/스키마/마이그레이션 무변경).
- 무엇: 권한 키 한국어 라벨·설명·카테고리 카탈로그와 RBAC 매트릭스 pill/유효권한 요약, 감사 로그 전용 탭(작업자/액션/상태/기간 검색·필터·CSV 내보내기), 세션 상대시간·접속자 스코프 자동 새로고침 토글·로그인 이벤트 페이지네이션, 탭 숫자 단축키 1~9·접이식 온보딩 도움말을 추가.
- 코드: `frontend/lib/{permission-catalog,relative-time,changelog}.ts`, `frontend/components/admin/admin-console-tabs.tsx`, `frontend/components/admin/sections/{admin-audit,admin-rbac,admin-sessions,admin-backups}-section.tsx`, `frontend/components/admin/widgets/{permission-checkbox-grid,resource-grant-form,list-filter}.tsx`, `backend/app/core/config.py`(버전 문자열만)
- 회귀 방지: backend `pytest tests` 265 passed, frontend Vitest 310 passed(65 파일), `tsc --noEmit`, `next build`, alembic head `0007`(스키마 변경 없음), 스토리별 architect CLEAR/APPROVE 및 executor red-team 통과(`artifacts/qa/1.12.0-admin-ux/`).

### 1.12.1 patch — 관리자 계정/세션 UX 보강

- 분류: patch (`1.12.1`) — 관리자 계정 생성/권한 수정 UX, 헤더 신원/로그아웃, 감사·세션 가독성 보강.
- 무엇: 사용자 생성에서 접속 아이디/임시 비밀번호만 필수로 명확화하고 이름(`display_name`)·이메일은 선택값으로 저장, 사용자별 행의 **권한 수정** 패널, 헤더 `로그인: <username>`·로그아웃 버튼, `login_events.status='logout'` 기록, 버전 배지 업데이트 날짜를 추가.
- 코드: `backend/app/modules/{admin,auth}/`, `backend/alembic/versions/20260707_0008_user_display_name.py`, `frontend/components/{admin,layout}/`, `frontend/app/api/frontend/session/route.ts`, `frontend/lib/{api,changelog,types}.ts`
- 회귀 방지: backend `pytest tests` 268 passed, frontend Vitest 311 passed(65 파일), `tsc --noEmit`, `next build`, live dashboard/admin smoke.

### 1.12.2 patch — 대시보드 시간·로그인 UI 정리

- 분류: patch (`1.12.2`, **배포 철회**) — 화면 변경 이력은 보존하지만 Release asset/오프라인 ZIP은 신규 설치·재배포 금지.
- 무엇: 헤더 버전 배지에서 날짜를 즉시 노출하지 않고 클릭한 업데이트 모달에서만 보이게 했으며, 대시보드 상단에 한국 시간을 실시간 표시합니다. 로그인 화면은 중앙 카드형 계정 접속 UI로 재배치하고, 로그인 후 헤더에는 `로그인:` 접두어 없이 아이디만 표시합니다. 세션 탭은 세로 공간을 키워 로그인/로그아웃 목록을 더 쉽게 읽게 했습니다.
- 코드: `frontend/components/layout/{version-badge,korean-clock,admin-nav-link,app-shell}.tsx`, `frontend/components/auth/login-form.tsx`, `frontend/components/admin/sections/admin-sessions-section.tsx`, `frontend/lib/changelog.ts`
- 회귀 방지: backend `pytest tests` 268 passed, frontend Vitest 313 passed(66 파일), `tsc --noEmit`, `next build`, live dashboard/admin smoke.

### 단계 26 — 자격 증명 사고 대응 회전 강화 (1.13.0)

- 파일: [`phase-26-credential-rotation-hardening.md`](phase-26-credential-rotation-hardening.md)
- 분류: minor (`1.13.0`) — DB 전체 사용자·세션을 포함하는 별도 사고 대응 경계와 복구 계약 추가.
- 무엇: setup-only 오해를 제거하고 service/listener preflight, production 물리 provenance, exact env/ACL/single-link, recovery→commit 연속 SQLite writer lock, unique ledger, DPAPI recovery, strict journal/quarantine manifest, actual process-kill 재개, ordinary backup 복원 뒤 old secure root archive→새 rotation, current-SID WPF 자격 인계를 구현.
- 코드: `scripts/{rotate_aeroone_credentials,view_aeroone_credentials}.ps1`, `scripts/credential_rotation/`, `backend/app/commands/`, `backend/app/operations/credential_rotation_*.py`, `backend/app/operations/{sqlite_recovery,windows_dpapi}.py`, `backend/alembic/versions/20260710_0009_credential_rotation_ledger.py`
- 회귀 방지: backend full 347 passed, credential focused 79 passed, frontend 313 passed(66 파일), ruff·basedpyright·compileall, PowerShell AST, `tsc --noEmit`, `next build`, old 401/new 200. 실제 WPF 창 시각 조작과 web 브라우저 smoke는 미실행.

---

## 보고서가 다루지 않는 자리

- 운영 절차: [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md), [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md)
- 코드 진실 원천: 각 보고서의 "코드" 항목 + [`docs/INDEX.md`](../INDEX.md) §6
- 회귀 테스트 인벤토리: [`docs/INDEX.md`](../INDEX.md) §7
