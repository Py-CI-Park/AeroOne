# AeroOne 문서 색인

이 문서는 AeroOne 저장소의 **모든 마크다운 문서를 한 자리에서 찾아갈 수 있는 wiki 인덱스** 입니다. 사람 운영자와 AI 에이전트가 동일한 입구에서 자기 깊이까지 들어갈 수 있도록 설계했습니다.

- 기준 commit: `bb94269` (offline_package.bat 결함 수정 직후)
- 작성일: 2026-05-07

---

## 0. 이 문서를 어떻게 읽는가

| 독자 | 우선 입구 | 다음 |
|---|---|---|
| **시스템을 처음 보는 사람** | [`README.md`](../README.md) (시스템 정체성, 빠른 시작) | §2 운영 매뉴얼 |
| **폐쇄망에 배포·운영하려는 사람** | [`docs/CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) | §2 운영 매뉴얼 + §3 단계 보고서 |
| **개발자 (코드 변경)** | [`docs/runbook/local-dev.md`](runbook/local-dev.md) | §4 설계 산출물 + §5 저장소 규칙 |
| **AI 에이전트 (자동화·유지보수)** | [`AGENTS.md`](../AGENTS.md), [`docs/CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) §14 | §6 코드 진실 원천 |

---

## 1. 진입점 문서 (저장소 루트)

| 문서 | 역할 | 길이 |
|---|---|---|
| [`README.md`](../README.md) | GitHub 첫 화면, 시스템 정체성과 빠른 시작 | 295줄 |
| [`AGENTS.md`](../AGENTS.md) | AI 에이전트 / 사람 협업자 모두를 위한 저장소 규칙 진입점 | 짧음 |
| [`CLAUDE.md`](../CLAUDE.md) | Claude Code 전용 추가 규칙 (AGENTS.md 보조) | 짧음 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | 커밋·PR·검증·보안 변경 절차 | 147줄 |
| [`LICENSE`](../LICENSE) | All Rights Reserved (사내 사용 전제) | — |
| [`offline_installers/README.md`](../offline_installers/README.md) | 폐쇄망 패키징 시 인스톨러 다운로드 안내 | 짧음 |

---

## 2. 운영 매뉴얼 (`docs/`)

| 문서 | 역할 | 길이 |
|---|---|---|
| [`CLOSED_NETWORK_GUIDE.md`](CLOSED_NETWORK_GUIDE.md) | **폐쇄망 운영 종합 가이드** (15장 + 부록, 9단계 진행 체크리스트) — 입구 추천 | 514줄 |
| [`runbook/windows-offline.md`](runbook/windows-offline.md) | Windows 폐쇄망 배포·운영 매뉴얼 (가장 깊은 세부, 13장) | 315줄 |
| [`runbook/local-dev.md`](runbook/local-dev.md) | 개발자 로컬 실행 가이드 (worktree 주의 포함) | 92줄 |
| [`runbook/admin-auth.md`](runbook/admin-auth.md) | 관리자 인증 정책 (`/admin/*` 신뢰 경계) | 짧음 |
| [`runbook/read-tracking.md`](runbook/read-tracking.md) | 읽음추적(IP 기반 열람 횟수) 설계·한계·개인정보·purge 절차 | 짧음 |

---

## 3. 단계별 변경 보고서 (`docs/reports/`)

폐쇄망 운영 보강 4단계의 의도와 합의안. 각 보고서는 변경 commit 과 1:1 대응됩니다. 자세한 인덱스: [`docs/reports/INDEX.md`](reports/INDEX.md).

| 단계 | 보고서 | 핵심 결과 | commit |
|---|---|---|---|
| 단계 6 | [`reports/phase-6-app-env-production.md`](reports/phase-6-app-env-production.md) | `closed_network` 모드 신설 — HTTP 쿠키 + secret 강도 검증 동시 충족 | `f43ae04` |
| 단계 7 | [`reports/phase-7-lan-mode.md`](reports/phase-7-lan-mode.md) | `--allow-host=<host>` 옵션으로 LAN 5자리 일괄 동기화 | `7a6879e` |
| 단계 8 | [`reports/phase-8-offline-simulation.md`](reports/phase-8-offline-simulation.md) | dry-run 3종 + 라이브 5단계 + 실 PC 플레이북 | `d2cec35` |
| 단계 9 | [`reports/phase-9-docstring.md`](reports/phase-9-docstring.md) | `ensure_db_state.py` 종료 코드 docstring + 회귀 테스트 7건 | `2e69b4b` |

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
| 패키징 제외 목록 | `offline_package.bat:34` | robocopy `/XD` 인자 |
| 프론트엔드 디자인 토큰 | `frontend/app/globals.css` (`[data-theme]` light/dark CSS 변수) + `frontend/tailwind.config.ts` (surface/ink/line/accent 시맨틱 유틸) | Claude Design 핸드오프(`design-handoff/`) 이식. 시스템 폰트만(외부 의존 0) |
| 테마 적용 지점 | `frontend/app/layout.tsx` 가 `aeroone_theme` 쿠키를 읽어 `<html data-theme>` 1곳에 서버 렌더. 토글은 `newsletter-theme-selector.tsx` 의 일반 `<a>`(풀 내비) → `/theme` 라우트(`frontend/app/theme/route.ts`)가 쿠키 설정 후 **상대 경로**로 리다이렉트 | 테마를 페이지 RSC 가 아니라 `<html>` 한 곳에 두어 클라이언트 내비게이션 간 stale flip 방지. 토글이 `<Link>` 면 풀 로드가 안 돼 즉시 반영 안 됨 → 의도적으로 `<a>`. **1.1.1**: `/theme` 리다이렉트는 `request.url` 의 origin 대신 origin 없는 상대 Location 을 쓴다 — LAN 모드(`next start -H 0.0.0.0`)에서 origin 이 `http://0.0.0.0:29501` 로 잡혀 브라우저가 접속 불가 주소로 튕기던 테마 토글 연결 종료 버그를 회피 |
| 공유 UI primitive | `frontend/components/ui/icons.tsx` (인라인 SVG), `frontend/components/ui/primitives.tsx` (Tag/Btn/Thumb) | 외부 아이콘 CDN 0 |
| 출력 폴더 자동 동기화 | `backend/app/modules/newsletter/services/newsletter_autosync_service.py` + `backend/app/modules/newsletter/api/public.py` (`auto_sync_newsletters` 의존성) | 공개 읽기 요청 시 `Newsletter/output` 시그니처(파일명+크기+mtime) 변화를 감지해 변경 시에만 `sync()`. 수동 Sync 엔드포인트(`api/imports.py`)도 베이스라인 시그니처를 갱신해 직후 읽기가 관리자 메타데이터 편집을 덮어쓰지 않게 함 |
| LAN 인바운드 허용 | `scripts/allow_lan_firewall.cmd` | 다른 PC 접속용 Windows 방화벽 인바운드(18437/29501, profile=any, remoteip=LocalSubnet) 추가/`--remove`. profile=any 라 Public/Unidentified 로 분류된 폐쇄망 NIC 에도 적용, LocalSubnet 으로 LAN 외부는 차단. `start_offline.bat --allow-host` 와 짝 |
| 뉴스레터 화면 구조 | `frontend/app/newsletters/page.tsx` + `frontend/app/newsletters/[slug]/page.tsx` → `newsletters-reading.tsx` (좌: 펼친 달력 / 우: 이슈 HTML 직접) | `/newsletters` 진입 시 최신 이슈 HTML 을 본문에 직접 렌더(HTML 전용 출력 대응). 달력 `defaultOpen`, 달력 날짜 클릭은 `?slug=` 로 이슈 전환. 제목은 sans 폰트로 통일 |
| 헤더 버전 팝업 | `frontend/components/layout/version-badge.tsx` + `frontend/lib/changelog.ts` (AppShell 헤더에서 사용) | 헤더 버전 라벨 클릭 시 업데이트 내역 + 문의(박찬일) 모달. `APP_VERSION = CHANGELOG[0].version` 으로 헤더 라벨을 단일 원천화 |
| 읽음추적(IP 기반) | `backend/app/modules/read_tracking/` (모델 `models/read_event.py`, 디바운스 upsert `repositories/read_event_repository.py`, 공개 비콘 `api/public.py`, 관리자 조회·purge `api/admin.py`) + 프런트 `frontend/components/newsletter/read-beacon.tsx` · `frontend/app/admin/read-events/page.tsx` | 브라우저가 백엔드를 직접 호출하는 무인증 비콘으로 `request.client.host`(독자 LAN IP)를 (newsletter_id, client_ip) upsert. 30분 디바운스로 read_count 집계. SSR/프록시 경로는 IP 가 loopback 으로 퇴화. 상세 [`runbook/read-tracking.md`](runbook/read-tracking.md) |

---

## 7. 회귀 테스트 위치

총 96건 PASS (읽음추적 도입 기준, backend pytest). 프론트엔드 Vitest 는 77건 PASS (30 파일).

| 테스트 파일 | 건수 | 다루는 영역 |
|---|---|---|
| `backend/tests/unit/test_config.py` | 10 | `closed_network` / `production` / `development` / `test` 모드 + `secure_cookies` |
| `backend/tests/unit/test_ensure_db_state.py` | 7 | 종료 코드 0/1/2/3 + 부모 디렉토리 자동 생성 |
| `backend/tests/unit/shared/test_windows_batch_scripts.py` | 28 | setup.bat / start.bat / start_offline.bat 의 dry-run / 실행 / 기본 LAN / `--local` / `--allow-host` / `--allow-host=auto` |
| `backend/tests/unit/shared/test_windows_frontend_cmd_scripts.py` | 2 | frontend 런처 본문 가드 |
| `backend/tests/unit/shared/test_lan_firewall_cmd_script.py` | 2 | LAN 방화벽 헬퍼 cmd 본문 가드 (포트 / 스코프 profile=any / `--remove` / help) |
| `backend/tests/unit/shared/test_detect_lan_ip_ps1_script.py` | 1 | `--allow-host=auto` LAN IP 자동 감지 스크립트 본문 가드 |
| `backend/tests/unit/newsletter/test_newsletter_autosync_service.py` | 3 | 읽기 시 지연 자동 동기화 (변경 감지 / 무변화 스킵 / 폴더 부재 가드) |
| `backend/tests/integration/test_newsletter_autosync.py` | 2 | 새 output 파일이 관리자 Sync 없이 달력 / 최신글에 반영 |
| `backend/tests/unit/read_tracking/test_read_event_repository.py` | 6 | record_read 30분 디바운스 upsert / 별도 IP 별도 행 / summarize / purge |
| `backend/tests/integration/test_read_tracking_api.py` | 7 | 공개 비콘 200·404(행 미생성) / 관리자 read-events 401·200 / purge 401·403(무CSRF)·삭제 |
| 그 외 unit / integration | 28 | 인증 API, 뉴스레터 public/admin/imports/content API, seed 등 |

프론트엔드 Vitest 신규: `frontend/tests/components/read-beacon.test.tsx`(sessionStorage 중복가드 2), `read-events-list.test.tsx`(집계·loopback 배너·빈상태 3), `frontend/tests/lib/record-read.test.ts`(비콘 URL 1).

회귀 1건이라도 발생하면 §3의 단계 보고서 4종을 거꾸로 읽어 어느 단계의 회귀인지 진단합니다.

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
| `Newsletter/output/` | 발행 원본 HTML/PDF | NO (정책상 비공개) |
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
