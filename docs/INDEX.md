# AeroOne 문서 색인

이 문서는 AeroOne 저장소의 **모든 마크다운 문서를 한 자리에서 찾아갈 수 있는 wiki 인덱스** 입니다. 사람 운영자와 AI 에이전트가 동일한 입구에서 자기 깊이까지 들어갈 수 있도록 설계했습니다.

- 기준 버전: `1.12.2` (`대시보드 시간·버전 날짜 표시·로그인 카드 UI 정리`)
- 갱신일: 2026-07-09

---

## 0. 이 문서를 어떻게 읽는가

| 독자 | 우선 입구 | 다음 |
|---|---|---|
| **시스템을 처음 보는 사람** | [`README.md`](../README.md) (시스템 정체성, 빠른 시작) | §2 운영 매뉴얼 |
| **폐쇄망에 배포·운영하려는 사람** | [`docs/CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) | §2 운영 매뉴얼 + §3 단계 보고서 |
| **개발자 (코드 변경)** | [`docs/runbook/local-dev.md`](runbook/local-dev.md) | §4 설계 산출물 + §5 저장소 규칙 |
| **AI 에이전트 (자동화·유지보수)** | [`AGENTS.md`](../AGENTS.md), [`docs/runbook/ai-agent-handoff-2026-07-09.md`](runbook/ai-agent-handoff-2026-07-09.md), [`docs/CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) §14 | §6 코드 진실 원천 |
| **이 워크트리(`feature/dashboard-enhancements`)를 이어받는 에이전트** | [`docs/runbook/ai-agent-handoff-2026-07-11-dashboard-enhancements.md`](runbook/ai-agent-handoff-2026-07-11-dashboard-enhancements.md) | §2 운영 매뉴얼 + §6 코드 진실 원천 |

---

## 1. 진입점 문서 (저장소 루트)

| 문서 | 역할 | 길이 |
|---|---|---|
| [`README.md`](../README.md) | GitHub 첫 화면, 시스템 정체성과 빠른 시작 | 303줄 |
| [`AGENTS.md`](../AGENTS.md) | AI 에이전트 / 사람 협업자 모두를 위한 저장소 규칙 진입점 | 짧음 |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code 전용 추가 규칙 (AGENTS.md 보조) | 짧음 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | 커밋·PR·검증·보안 변경 절차 | 147줄 |
| [`LICENSE`](../LICENSE) | All Rights Reserved (사내 사용 전제) | — |
| [`offline_installers/README.md`](../offline_installers/README.md) | 폐쇄망 패키징 시 인스톨러 다운로드 안내 | 짧음 |

---

## 2. 운영 매뉴얼 (`docs/`)

| 문서 | 역할 | 길이 |
|---|---|---|
| [`CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) | **폐쇄망 운영 종합 가이드** (18장 + 부록, 9단계 진행 체크리스트, Open Notebook co-deploy §18, 관리자 콘솔/RBAC) — 입구 추천 | 700줄+ |
| [`runbook/closed-network-install-manual.md`](runbook/closed-network-install-manual.md) | **폐쇄망 상세 설치·사용 매뉴얼** — AeroOne + Open Notebook + Ollama, 운영자 단계별(반입물→설치→기동→확인→트러블슈팅). 패키지 동봉 | 중간 |
| [`runbook/windows-offline.md`](runbook/windows-offline.md) | Windows 폐쇄망 배포·운영 매뉴얼 (가장 깊은 세부, 13장) | 375줄 |
| [`runbook/local-dev.md`](runbook/local-dev.md) | 개발자 로컬 실행 가이드 (worktree 주의 포함) | 92줄 |
| [`runbook/admin-auth.md`](runbook/admin-auth.md) | 관리자 인증 정책 (`/admin/*` 신뢰 경계) | 짧음 |
| [`runbook/read-tracking.md`](runbook/read-tracking.md) | 읽음추적(IP 기반 열람 횟수) 설계·한계·개인정보·purge 절차 | 짧음 |
| [`runbook/open-notebook-airgap.md`](runbook/open-notebook-airgap.md) | Open Notebook 폐쇄망 co-deploy 단일 진실 원천 (vendoring·adapter 동결·Ollama provisioning·동시성 예산·운영자 게이트) | 중간 |
| [`runbook/office-tools.md`](runbook/office-tools.md) | **오피스 도구(보고서·차트·다이어그램) 런북** — Tool MVP 흡수 구조(5자리 통합면·`/api/v1/office-tools/*` 로그인 강제·same-origin 프록시)·서비스별 입출력/서버 상한·브라우저 렌더(ECharts/Mermaid) 결정·pandas/openpyxl 오프라인 의존성·AI 선택적 폴백·회귀 테스트·운영자 검증 | 중간 |
| [`runbook/llm-connections.md`](runbook/llm-connections.md) | **LLM 연결(AI 연결) 설정 런북** — OpenAI 호환 단일화·관리자 콘솔 'AI 연결' 카드·`/api/v1/admin/llm-connections*`(`admin.ai.read`/`admin.ai.manage`+CSRF)·`llm_crypto` 키 암호화/마스킹/감사·`/v1/models` 검증·시크릿 회전 재등록·운영자 검증 | 중간 |
| [`runbook/leantime-codeploy.md`](runbook/leantime-codeploy.md) | **Leantime 동거(co-deploy) 런북** — 두 스택 경계(코드 병합 금지, 링크+포트만)·오프라인 설치(IIS/PHP/MariaDB, 8081/3307)·`run_all.bat` 기동 훅(`AEROONE_LEANTIME_LAUNCHER`)·AGPL v3 소스오퍼 의무·백업/방화벽/자동시작·운영자 검증 체크리스트 | 중간 |
| [`runbook/ai-agent-handoff-2026-07-09.md`](runbook/ai-agent-handoff-2026-07-09.md) | **AI 에이전트 핸드오프** — 1.12.2 안정판, 1.13.0-dev 계획/blocked 상태, 다음 작업 순서, guardrail, 검증/커밋 규칙을 Codex/Claude/GJC 공통 문맥으로 정리 | 중간 |
| [`runbook/ai-agent-handoff-2026-07-11-dashboard-enhancements.md`](runbook/ai-agent-handoff-2026-07-11-dashboard-enhancements.md) | **`feature/dashboard-enhancements` 워크트리 핸드오프** — 이 브랜치가 v1.13.0-dev 활성 계획(Wave 0 Task 3 리뷰 실패 중)과 왜/어떻게 독립인지, 병합 보류 조건, 대시보드 코드 진실 원천 지도 | 짧음 |

---

## 3. 단계별 변경 보고서 (`docs/reports/`)

폐쇄망 운영 보강 4단계 + 기능 모듈/운영 패치 단계(읽음추적·민간 항공기 보고서·문서 보관소·컬렉션 프록시/Civil·NSA·사다리·Ollama AI 검색·Open Notebook 연구/동거 배포·AI 대화 영속화·뷰어·폐쇄망 smoke 패치·AeroAI/Viewer UX 강화·대시보드 개발중 섹션 재분류·관리자 RBAC/운영 콘솔·관리자 콘솔 UX/same-origin 프록시 통합·관리자 계정/세션 UX 개선)의 의도와 합의안. 각 보고서는 변경 commit 또는 릴리즈 패치와 대응됩니다. 자세한 인덱스: [`docs/reports/INDEX.md`](reports/INDEX.md).

| 단계 | 보고서 | 핵심 결과 | commit |
|---|---|---|---|
| 단계 6 | [`reports/phase-6-app-env-production.md`](reports/phase-6-app-env-production.md) | `closed_network` 모드 신설 — HTTP 쿠키 + secret 강도 검증 동시 충족 | `f43ae04` |
| 단계 7 | [`reports/phase-7-lan-mode.md`](reports/phase-7-lan-mode.md) | `--allow-host=<host>` 옵션으로 LAN 5자리 일괄 동기화 | `7a6879e` |
| 단계 8 | [`reports/phase-8-offline-simulation.md`](reports/phase-8-offline-simulation.md) | dry-run 3종 + 라이브 5단계 + 실 PC 플레이북 | `d2cec35` |
| 단계 9 | [`reports/phase-9-docstring.md`](reports/phase-9-docstring.md) | `ensure_db_state.py` 종료 코드 docstring + 회귀 테스트 7건 | `2e69b4b` |
| 단계 10 | [`reports/phase-10-read-tracking.md`](reports/phase-10-read-tracking.md) | IP 기반 읽음추적(열람 횟수) 모듈 — minor 1.1.0 | `2ec9016` |
| 단계 11 | [`reports/phase-11-civil-aircraft-report.md`](reports/phase-11-civil-aircraft-report.md) | 민간 항공기 보고서 모듈 + 콘텐츠 폴더 `_database` 재편 — minor 1.2.0 | `9898203` |
| 단계 12 | [`reports/phase-12-document-module.md`](reports/phase-12-document-module.md) | 문서(Document) 보관소 모듈 — `_database/document` HTML 을 폴더 트리로 열람 — minor 1.3.0 | `1.3.0-dev` |
| 단계 13 | [`reports/phase-13-collections-proxy-and-features.md`](reports/phase-13-collections-proxy-and-features.md) | 컬렉션 same-origin 프록시 + Civil/NSA 목록화 + 사다리 게임 — minor 1.4.0 | `1.4.0-dev` |
| 단계 14 | [`reports/phase-14-ollama-ai-search.md`](reports/phase-14-ollama-ai-search.md) | 폐쇄망 Ollama AI 채팅 + HTML 본문 검색 — minor 1.5.0 | `1.5.0-dev` |
| 단계 15 | [`reports/phase-15-openwebui-reference-research.md`](reports/phase-15-openwebui-reference-research.md) | Open WebUI 참조 기능 연구 — 대화/관리/RAG 후보 정리 | research |
| 단계 16 | [`reports/phase-16-ai-conversation-and-document-grounding.md`](reports/phase-16-ai-conversation-and-document-grounding.md) | AI 대화 영속화 + 문서 근거 연결 강화 — 1.5 2차 증분 | `1.5.0-dev` |
| 단계 17 | [`reports/phase-17-viewer-editor-and-launcher-ai-fixes.md`](reports/phase-17-viewer-editor-and-launcher-ai-fixes.md) | Viewer 탭 + 런처/AeroAI/HTML 스크롤 수정 — minor 1.6.0 | `1.6.0-dev` |
| 단계 18 | [`reports/phase-18-closed-network-smoke-fixes.md`](reports/phase-18-closed-network-smoke-fixes.md) | 1.6.1 폐쇄망 smoke 결함 보강 — patch 1.6.2 | `1.6.2` |
| 단계 19 | [`reports/phase-19-aeroai-viewer-ux-release.md`](reports/phase-19-aeroai-viewer-ux-release.md) | AeroAI Markdown 답변·HTML 검색 새 탭·모니터 높이 레이아웃 + Viewer 집중/전체화면 + Open Notebook 동거 릴리즈 — minor 1.7.0 | `1.7.0-dev` |
| 단계 20 | [`reports/phase-20-dashboard-development-section-handoff.md`](reports/phase-20-dashboard-development-section-handoff.md) | 대시보드 개발중 섹션 신설 + AeroAI/Notebook/Viewer/Ladder active 이동 + coming-soon 카드 비활성 유지 + 1.7.1 뉴스레터/사용법 patch | `1.7.1-dev` |
| 단계 21 | [`reports/phase-21-admin-rbac-operations-console.md`](reports/phase-21-admin-rbac-operations-console.md) | 관리자 RBAC·same-transaction audit·운영 콘솔·service_modules DB 대시보드·뉴스레터 자산/상태/bulk·백업 — minor 1.8.0 | `1.8.0-dev` |
| 단계 22 | [`reports/phase-22-operator-visibility-and-module-management.md`](reports/phase-22-operator-visibility-and-module-management.md) | 관리자 전용 Admin/개발중(Development)/Coming soon 노출 + 헤더 다크·사용법·Admin 순서 + 모듈 add/delete·노출 대상 관리 + 관리자 비밀번호 변경 + start_offline 마이그레이션 preflight — minor 1.9.0 | `1.9.0-dev` |
| 단계 23 | [`reports/phase-23-admin-authz-hardening.md`](reports/phase-23-admin-authz-hardening.md) | RBAC 읽기 권한 상승 수정 + NSA 서버측 접근제어 + 사용자별 메뉴 힌트 + 자산 진단 + 사용자/그룹/리소스 권한·RBAC 매트릭스 + 접속자 대시보드 — minor 1.10.0 | `1.10.0-dev` |
| 단계 24 | [`reports/phase-24-admin-console-proxy-redesign.md`](reports/phase-24-admin-console-proxy-redesign.md) | 관리자 로그인/CRUD same-origin 프록시 통합 + `/admin` 탭형 콘솔 UX/RBAC 입력/목록 상태/ARIA Tabs — minor 1.11.0 | `1.11.0-dev` |
| 단계 25 | [`reports/phase-25-admin-console-ux-polish.md`](reports/phase-25-admin-console-ux-polish.md) | 권한 이해 카탈로그 + 감사 로그 전용 탭(검색/필터/CSV) + 세션 상대시간·접속자 스코프 자동 새로고침·로그인 목록 페이지네이션 + 탭 숫자 단축키 1~9·온보딩 도움말 — 프론트-only minor 1.12.0 | `1.12.0-dev` |
| 1.12.1 patch | — | 헤더 로그인 사용자 아이디/로그아웃, `users.display_name` 선택 프로필, 사용자 행별 권한 수정 패널, 감사 로그 페이지네이션·필터 초기화·현재 결과 CSV, 세션 15초 갱신 안내, 버전 배지 업데이트 날짜 표시 | `1.12.1` |
| 1.12.2 patch | — | 헤더 버전 날짜 즉시 노출 제거(클릭 모달에만 표시), 대시보드 한국 시간 실시간 표시, 로그인 중앙 카드 UI, 로그인 후 아이디 단독 표시, 세션 탭 세로 가독성 보강 | `1.12.2` |

---

## 4. 설계 산출물 (`docs/superpowers/`, `docs/dev_plan/`, `design-handoff/`)

| 디렉토리 | 내용 | 개수 |
|---|---|---|
| [`superpowers/plans/`](superpowers/plans/) | 기능별 구현 계획 (Tier-0 OMC superpowers 형식) | 14건 |
| [`superpowers/specs/`](superpowers/specs/) | 기능별 설계 명세 (plan 과 1:1 매칭) | 14건 |
| [`dev_plan/20260327_newsletter_platform_mvp.md`](dev_plan/20260327_newsletter_platform_mvp.md) | 2026-03-27 작성 MVP 개발 계획 (범위·완료 기준·리스크) | 299줄 |
| [`../design-handoff/`](../design-handoff/) | **UI/UX 재디자인 요청용 핸드오프 패키지** (브리프 / 여정 / 화면 인벤토리 / 제약 + 추천 프롬프트) | 6건 |

자세한 인덱스: [`docs/superpowers/INDEX.md`](superpowers/INDEX.md).

---

## 5. 저장소 규칙 / 협업 절차

| 문서 | 핵심 |
|---|---|
| [`AGENTS.md`](../AGENTS.md) | 한국어 커밋 규칙, Lore trailer, PR 규칙. AI 에이전트 진입점. |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code 전용 추가 규칙 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | 커밋·PR 형식, 코드 컨벤션, 검증 절차, 보안 변경 절차 |
| [`closed-network-oss-adoption-process.md`](closed-network-oss-adoption-process.md) | 폐쇄망 오픈소스 도입 **재사용 프로세스 플레이북** (co-deploy·vendoring·airgap 번들·자동 프로비저닝·검증 게이트·동기화). 향후 외부 OSS 도입 표준 |

---

## 6. 코드 진실 원천 (AI 에이전트가 직접 보아야 할 자리)

`docs/CLOSED_NETWORK_GUIDE.md` §15.1 의 코드 진실 원천 표가 가장 정확합니다. 빠른 요약은 다음과 같습니다.

| 영역 | 코드 위치 | 무엇을 |
|---|---|---|
| 운영 모드 분기 | `backend/app/core/config.py:14` | `app_env: Literal['development', 'test', 'production', 'closed_network']` |
| secure cookie 분기 | `backend/app/core/config.py:82` | `secure_cookies` 프로퍼티 (production 만 True) |
| secret 강도 검증 | `backend/app/core/config.py:85-95` | `validate_runtime_security` (production / closed_network 에서 강제) |
| 부팅 검증 호출 | `backend/app/main.py:18` | startup 시 1회 호출 |
| DB 분기 (배치용) | `backend/scripts/ensure_db_state.py` | 종료 코드 0/1/2/3, docstring 에 의미 직접 기재 |
| 폐쇄망 LAN 옵션 / 기본 바인딩 | `setup_offline.bat`, `start_offline.bat` 의 `:parse_args` / `:capture_host` / `:resolve_auto_host` 라벨 | **1.0.22+ 기본 = LAN**: 옵션 없으면 `ALLOW_HOST=auto` → `scripts/windows/detect_lan_ip.ps1` 로 LAN IPv4 자동 감지(미감지 시 loopback 폴백, 0.0.0.0 바인딩). `--local` 로 loopback 전용, `--allow-host=<IP>` 로 호스트 고정, `AEROONE_ALLOW_HOST` env 도 인식 |
| 패키징 제외 목록 | `offline_package.bat:46` | robocopy `/XD` + `/XF` 인자. `.git` 디렉터리/파일, `.gjc`, `.omc`, `.worktrees`, venv/node_modules/build/cache/vendor/artifacts 트리와 `.ug-*` scratch 파일은 ZIP 에 넣지 않음 |
| 프론트엔드 디자인 토큰 | `frontend/app/globals.css` (`[data-theme]` light/dark CSS 변수) + `frontend/tailwind.config.ts` (surface/ink/line/accent 시맨틱 유틸) | Claude Design 핸드오프(`design-handoff/`) 이식. 시스템 폰트만(외부 의존 0) |
| 테마 적용 지점 | `frontend/app/layout.tsx` 가 `aeroone_theme` 쿠키를 읽어 `<html data-theme>` 1곳에 서버 렌더. 토글은 `newsletter-theme-selector.tsx` 의 일반 `<a>`(풀 내비) → `/theme` 라우트(`frontend/app/theme/route.ts`)가 쿠키 설정 후 **상대 경로**로 리다이렉트 | 테마를 페이지 RSC 가 아니라 `<html>` 한 곳에 두어 클라이언트 내비게이션 간 stale flip 방지. 토글이 `<Link>` 면 풀 로드가 안 돼 즉시 반영 안 됨 → 의도적으로 `<a>`. **1.1.1**: `/theme` 리다이렉트는 `request.url` 의 origin 대신 origin 없는 상대 Location 을 쓴다 — LAN 모드(`next start -H 0.0.0.0`)에서 origin 이 `http://0.0.0.0:29501` 로 잡혀 브라우저가 접속 불가 주소로 튕기던 테마 토글 연결 종료 버그를 회피 |
| 공유 UI primitive | `frontend/components/ui/icons.tsx` (인라인 SVG), `frontend/components/ui/primitives.tsx` (Tag/Btn/Thumb) | 외부 아이콘 CDN 0 |
| 출력 폴더 자동 동기화 | `backend/app/modules/newsletter/services/newsletter_autosync_service.py` + `backend/app/modules/newsletter/api/public.py` (`auto_sync_newsletters` 의존성) | 공개 읽기 요청 시 `_database/newsletter` 시그니처(파일명+크기+mtime) 변화를 감지해 변경 시에만 `sync()`. 수동 Sync 엔드포인트(`api/imports.py`)도 베이스라인 시그니처를 갱신해 직후 읽기가 관리자 메타데이터 편집을 덮어쓰지 않게 함 |
| 관리자 RBAC/Audit/운영 콘솔 | `backend/app/modules/admin/`, `backend/app/modules/auth/dependencies.py`, `backend/app/modules/auth/api.py`, `backend/app/modules/auth/models.py`, `backend/alembic/versions/20260707_0008_user_display_name.py`, `frontend/app/admin/page.tsx`, `frontend/components/admin/`, `frontend/components/layout/admin-nav-link.tsx`, `frontend/app/api/frontend/{auth,admin,search,session}/` | `admin/user/pending` 역할 + additive permissions/groups/resource grants. 새 관리자 API 는 `require_permission(...)` 과 `require_csrf` 를 분리해 조합. 감사 대상 mutation 은 같은 transaction 에 `admin_audit_events` 기록(fail-closed), 비밀번호·토큰·AI prompt/answer/snippet 미저장. 1.11.0 부터 브라우저 로그인과 관리자 CRUD 는 same-origin `/api/frontend/auth/*`, `/api/frontend/admin/*` 로 relay 하고, 통합 검색은 `/api/frontend/search/unified` 를 사용한다. 사용자는 로그인과 탭형 `/admin` 콘솔을 모두 같은 frontend origin(`http://<host>:29501`) 으로 열며, 헤더는 현재 로그인 사용자 아이디와 로그아웃 버튼을 표시한다. 로그아웃은 `login_events.status='logout'` 을 기록하고 현재 토큰의 세션 활동을 제거한다. 1.12.1 은 선택 프로필 `users.display_name` 과 사용자 행별 **권한 수정** 패널을 추가한다 |
| 대시보드 DB 원천 | `backend/app/modules/admin/api.py` (`service_modules`), `frontend/app/page.tsx` | 대시보드 카드를 `service_modules` DB 에서 읽고 관리자 콘솔에서 active/development/coming_soon, 설명, 링크, 정렬, 외부 링크를 조정. DB/table 미준비 시 visible degraded banner + 내장 fallback 목록. 카드 시드 진실은 마이그레이션(office 3종 `20260711_0010`, Leantime 외부링크 `20260711_0011`) + `DEFAULT_SERVICE_MODULES` + `FALLBACK_MODULES` 3자리가 일치. Leantime 은 `is_external` 링크 카드로만 동거 — [`runbook/leantime-codeploy.md`](runbook/leantime-codeploy.md) |
| 오피스 도구(보고서/차트/다이어그램) | `backend/app/modules/office_tools/` + `backend/app/main.py`(`/api/v1/office-tools`) + `frontend/app/office-tools/{report,chart,diagram}/page.tsx` + `frontend/components/office-tools/` + `frontend/app/api/frontend/office-tools/[...segments]/route.ts` | Tool MVP(`AeroOne Tool/tool-mvp-v0.1.0/`) 흡수. 상위 라우터가 세션 로그인 강제(미로그인 401), 브라우저는 same-origin 프록시만 호출. 차트=브라우저 ECharts(서버 pandas 집계), 다이어그램=브라우저 Mermaid, 서버 PNG(CairoSVG/Matplotlib)는 비활성. AI 보조는 활성 LLM 연결 우선·없으면 규칙 기반 폴백. 산출물은 `OfficeJobStore` 에 `owner_id` 스코프(타인 403). 상세 [`runbook/office-tools.md`](runbook/office-tools.md) |
| LLM 연결 레지스트리 | `backend/app/modules/ai/{models.py(LlmConnection),schemas.py,llm_connection_service.py,llm_crypto.py,openai_client.py,api/admin.py}` + `backend/alembic/versions/20260711_0009_llm_connections.py` + `frontend/components/admin/sections/admin-llm-connections-card.tsx` | 관리자가 OpenAI 호환 엔드포인트(base_url+api_key)를 등록 → `/v1/models` 검증 → `/v1/chat/completions` 호출. API `/api/v1/admin/llm-connections*`, 읽기 `admin.ai.read`·변경 `admin.ai.manage`+CSRF, 모든 변경 감사기록. 키는 `llm_crypto`(stdlib HMAC Encrypt-then-MAC, 원천 `jwt_secret_key`)로 암호화·응답/감사는 마스킹만. 활성 기본 1개 유일, office-tools AI 보조가 소비. 상세 [`runbook/llm-connections.md`](runbook/llm-connections.md) |
| LAN 인바운드 허용 | `scripts/allow_lan_firewall.cmd` | 다른 PC 접속용 Windows 방화벽 인바운드(18437/29501, profile=any, remoteip=LocalSubnet) 추가/`--remove`. profile=any 라 Public/Unidentified 로 분류된 폐쇄망 NIC 에도 적용, LocalSubnet 으로 LAN 외부는 차단. `start_offline.bat --allow-host` 와 짝 |
| 뉴스레터 화면 구조 | `frontend/app/newsletters/page.tsx` + `frontend/app/newsletters/[slug]/page.tsx` → `newsletters-reading.tsx` (좌: 펼친 달력 / 우: 이슈 HTML 직접) | `/newsletters` 진입 시 최신 이슈 HTML 을 본문에 직접 렌더(HTML 전용 출력 대응). 달력 `defaultOpen`, 달력 날짜 클릭은 `?slug=` 로 이슈 전환. 제목은 sans 폰트로 통일. 대시보드에 민간항공기 규격 카탈로그 카드(활성)도 포함 |
| 민간항공기 규격 카탈로그 | `backend/app/modules/collections/api/public.py` (`GET /api/v1/collections/civil/list`, `GET /api/v1/collections/civil/content/html?path=`) + `frontend/app/reports/civil-aircraft/page.tsx` + `frontend/components/documents/documents-workspace.tsx`(collection="civil") | `_database/civil_aircraft` 의 여러 HTML 을 Document 와 동일한 폴더 트리 목록 UI 로 표시(기본 접힘). 1.4.0 에서 단일 보고서에서 다중 카탈로그 목록으로 전환. 단일보고서 엔드포인트(`/api/v1/reports/civil-aircraft/content/html`)는 1릴리즈 deprecated 유지 |
| 문서 보관소 | `backend/app/modules/collections/api/public.py` (`GET /api/v1/collections/document/list`, `GET /api/v1/collections/document/content/html?path=`) + `frontend/app/documents/page.tsx` + `frontend/components/documents/documents-workspace.tsx`(재귀 폴더 트리) | `_database/document` 의 HTML 을 하위 폴더 포함 재귀 수집해 좌측 접을 수 있는 폴더 트리로 목록화(기본 접힘), 선택 1개를 우측 HtmlViewer(sandbox iframe)로 렌더. `_debug.html` 제외, `(folder,name)` 정렬, 디렉토리 이탈 400 |
| 로컬 Viewer | `frontend/app/viewer/page.tsx` + `frontend/components/viewer/viewer-editor.tsx` + `backend/app/modules/render/api.py` | 대시보드 개발중 섹션 카드 → `/viewer`. 로컬 `.md`/`.html` 파일을 열어 편집·렌더·다운로드. 1.7.0 부터 편집+미리보기 / 미리보기 집중 / 전체화면 미리보기 모드를 제공하며, 모든 미리보기는 빈 `sandbox` iframe 으로 스크립트와 동일출처 권한을 차단 |
| 컬렉션 same-origin 프록시 | `frontend/app/api/frontend/collections/[...segments]/route.ts` | 브라우저가 `/api/frontend/collections/<collection>/...` 로 요청하면 Next.js 서버가 `SERVER_API_BASE_URL`(loopback) 경유로 백엔드에 전달. 외부 PC 에서 document·civil·nsa 본문이 "failed to fetch" 로 실패하던 문제를 구조적으로 해결(1.4.0). 첫 세그먼트 화이트리스트(document·civil·nsa) 검증. 뉴스레터 프록시와 동일 패턴 |
| NSA 탭 | `frontend/app/nsa/page.tsx` + `backend/app/modules/collections/` + `_database/nsa/`(문서 보관 폴더) | 대시보드 카드 → /nsa. 1.10.0 부터 비밀번호 0000 가림막 대신 서버가 `collections.nsa.read` 권한과 `collection:nsa` ResourceGrant 를 확인해 목록·본문·검색을 제공. 암호화 비밀 저장소는 아님 |
| Ladder(사다리타기) | `frontend/app/games/ladder/page.tsx` + `frontend/components/games/ladder-game.tsx` | 대시보드 개발중 섹션 카드 → /games/ladder. 참가자·상품 입력 후 랜덤 사다리로 배정 결과 표시. 순수 프론트엔드, 백엔드 없음 |
| Ollama AI / 본문 검색 | `backend/app/modules/ai/`, `backend/app/modules/collections/search_service.py`, `frontend/app/ai/page.tsx`, `frontend/components/ai/ai-chat-workspace.tsx`, `frontend/app/api/frontend/ai/` | 대시보드 개발중 섹션의 AeroAI 카드 → `/ai`. 브라우저는 same-origin AI 프록시만 호출하고 백엔드가 `OLLAMA_BASE_URL` 의 `gemma4:12b` 와 통신. reasoning-only 빈 응답은 1회 재시도 후 계속 비면 502 로 구분. 1.7.0 부터 답변은 안전한 Markdown 으로 렌더링하고 복사는 원문 텍스트를 유지하며, `_database` HTML 본문 검색 결과는 새 탭으로 열린다. 1.8.0 부터 `ai_request_logs` 에 metadata-only 운영 로그를 남기며 prompt/answer/snippet/citation 원문은 저장하지 않는다. 기본 scope 는 `document,civil`, NSA 는 서버측 권한/ResourceGrant 통과 후에만 포함 |
| 헤더 버전 팝업 | `frontend/components/layout/version-badge.tsx` + `frontend/lib/changelog.ts` (AppShell 헤더에서 사용) | 헤더 버전 라벨 클릭 시 업데이트 내역 + 문의(박찬일) 모달. `APP_VERSION = CHANGELOG[0].version` 으로 헤더 라벨을 단일 원천화 |
| 읽음추적(IP 기반) | `backend/app/modules/read_tracking/` (모델 `models/read_event.py`, 디바운스 upsert `repositories/read_event_repository.py`, 공개 비콘 `api/public.py`, 관리자 조회·purge `api/admin.py`) + 프런트 `frontend/components/newsletter/read-beacon.tsx` · `frontend/app/admin/read-events/page.tsx` | 브라우저가 백엔드를 직접 호출하는 무인증 비콘으로 `request.client.host`(독자 LAN IP)를 (newsletter_id, client_ip) upsert. 30분 디바운스로 read_count 집계. SSR/프록시 경로는 IP 가 loopback 으로 퇴화. 상세 [`runbook/read-tracking.md`](runbook/read-tracking.md) |

---

## 7. 회귀 테스트 위치

최신 회귀 통계는 README.md §검증과 각 phase report 를 기준으로 한다. 1.12.2 기준 backend 268 passed, frontend Vitest 313 passed(66 파일), `tsc --noEmit`, `next build` 를 수행한다. release gate 에서는 여기에 브라우저 smoke 를 더한다.

| 테스트 파일 | 건수 | 다루는 영역 |
|---|---|---|
| `backend/tests/unit/test_config.py` | 10 | `closed_network` / `production` / `development` / `test` 모드 + `secure_cookies` |
| `backend/tests/unit/test_ensure_db_state.py` | 7 | 종료 코드 0/1/2/3 + 부모 디렉토리 자동 생성 |
| `backend/tests/unit/shared/test_windows_batch_scripts.py` | 33 | setup.bat / start.bat / start_offline.bat / run_all.bat / offline_package.bat 의 dry-run / 실행 / 기본 LAN / `--local` / `--allow-host` / `--allow-host=auto` / Open Notebook readiness / Leantime 동거 훅(dry-run + help) / packaging 제외 목록 |
| `backend/tests/unit/shared/test_windows_frontend_cmd_scripts.py` | 2 | frontend 런처 본문 가드 |
| `backend/tests/unit/shared/test_lan_firewall_cmd_script.py` | 2 | LAN 방화벽 헬퍼 cmd 본문 가드 (포트 / 스코프 profile=any / `--remove` / help) |
| `backend/tests/unit/shared/test_detect_lan_ip_ps1_script.py` | 1 | `--allow-host=auto` LAN IP 자동 감지 스크립트 본문 가드 |
| `backend/tests/unit/newsletter/test_newsletter_autosync_service.py` | 3 | 읽기 시 지연 자동 동기화 (변경 감지 / 무변화 스킵 / 폴더 부재 가드) |
| `backend/tests/integration/test_newsletter_autosync.py` | 2 | 새 output 파일이 관리자 Sync 없이 달력 / 최신글에 반영 |
| `backend/tests/unit/read_tracking/test_read_event_repository.py` | 6 | record_read 30분 디바운스 upsert / 별도 IP 별도 행 / summarize / purge |
| `backend/tests/integration/test_read_tracking_api.py` | 7 | 공개 비콘 200·404(행 미생성) / 관리자 read-events 401·200 / purge 401·403(무CSRF)·삭제 |
| `backend/tests/integration/test_reports_api.py` | 3 | 민간 항공기 보고서 200·sanitize·CSP / 404 / `_debug` 제외 |
| `backend/tests/integration/test_documents_api.py` | 8 | 문서 목록(하위폴더·`_debug` 제외·정렬) / 빈 목록 / 콘텐츠 sanitize·CSP / HTML 다운로드 / 404 / 디렉토리 이탈 400 |
| `backend/tests/integration/test_ai_api.py` | 9 | AI status/chat, 기본 document/civil scope, 명시 NSA scope, FTS unavailable degrade, unknown collection validation, Ollama 빈 답변 재시도 |
| `backend/tests/integration/test_admin_operations_api.py` | 2 | 관리자 대시보드/service_modules/asset health/backup validate/audit, 사용자 RBAC self-lockout·비관리자 403·비밀번호 reset 감사 redaction |
| 그 외 unit / integration | 85+ | 인증 API, 뉴스레터 public/admin/imports/content API, 컬렉션 다운로드, seed 등 |

프론트엔드 Vitest: `frontend/tests/components/app-shell.test.tsx` 는 Admin 상단 네비를 포함하고, `frontend/tests/app/home-page.test.tsx` 는 `service_modules` API 실패 시 fallback 대시보드가 기존 카드/개발중/Coming soon 구성을 유지하는지 확인한다. 그 밖에 read-beacon/read-events, 민간 항공기 보고서, 문서 보관소, AI workspace/proxy, NSA 서버측 권한, 사다리, 뉴스레터 날짜 aria-label 테스트가 포함된다.

회귀 1건이라도 발생하면 §3의 단계 보고서를 거꾸로 읽어 어느 단계의 회귀인지 진단합니다.

---

## 8. 외부 / 비공개 위치

| 위치 | 의미 | git tracked? |
|---|---|---|
| `.env.example` | 환경 변수 템플릿 | YES (예시 값만) |
| `.env`, `.env.local`, `.env.bak` | 실제 secret | NO (gitignore) |
| `.omc/` | 현재 OMC 런타임 상태 (notepad / project-memory / state) | NO |
| `.omx/` | 옛 OMC 런타임 상태 | NO |
| `dist/` | 패키징 산출물 (`AeroOne-offline-*.zip`) | NO |
| `offline_installers/*` | 폐쇄망 인스톨러 (Python EXE / Node MSI) | NO (단 `README.md` 만 예외) |
| `_database/newsletter/` | 뉴스레터 발행 원본 HTML/PDF (`newsletter_YYYYMMDD.html`) | NO (정책상 비공개) |
| `_database/civil_aircraft/` | 민간항공기 규격 HTML 카탈로그 (여러 HTML 가능, 목록 UI 로 표시) | NO (정책상 비공개) |
| `_database/document/` | 문서 보관소 HTML (하위 폴더로 분류 가능) | NO (정책상 비공개) |
| `_database/nsa/` | NSA 탭 문서 보관소 (서버측 권한/ResourceGrant 통과 후 표시, 암호화 저장소 아님) | NO (정책상 비공개) |
| `storage/` | 운영 storage (썸네일·markdown·첨부) | NO |
| `backend/data/aeroone.db` | 운영 DB | NO |

위 7자리는 **저장소 공개에 부적합** 하므로 wiki 색인에서 의도적으로 git 외 자리로 분리했습니다. 폐쇄망 PC 운영 시 백업 대상은 [`CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) §10 참고.

---

## 9. 빠른 명령 모음 (Cheatsheet)

```cmd
:: 온라인 PC 패키징
setup.bat
offline_package.bat

:: 폐쇄망 단일 PC
setup_offline.bat
start_offline.bat

:: 폐쇄망 LAN
setup_offline.bat --allow-host=192.168.1.10
start_offline.bat --allow-host=192.168.1.10

:: 검증
setup_offline.bat --dry-run --no-pause
start_offline.bat --dry-run
curl http://localhost:18437/api/v1/health

:: 회귀 테스트
cd backend && .venv\Scripts\activate && set PYTHONPATH=. && python -m pytest tests -q
```

---

## 10. 본 색인을 갱신할 때

새 문서를 추가하거나 본문 섹션이 크게 바뀌면 본 INDEX.md 의 해당 섹션도 같은 commit 에서 갱신하세요. wiki 의 입구가 코드 변경과 어긋나면 다음 독자가 잘못된 자리에 도착합니다.
