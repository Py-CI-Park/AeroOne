# AeroOne 폐쇄망 배포·운영 종합 가이드

이 문서는 **사람 운영자와 AI 에이전트가 동일하게 참조할 수 있는 단일 진실 원천(single source of truth)** 입니다. 폐쇄망 배포의 모든 흐름·검증·운영·문제 해결을 한 자리에 모았습니다. 더 깊은 세부는 §13의 참조 문서로 분기합니다.

- 기준 브랜치: `main` (현재 immutable 정식 `1.13.2`, immutable historical `1.13.1` 및 역사적 `1.13.0` 릴리스 계보)
- 갱신일: 2026-07-14
- 최근 완료 검증: 1.13.2는 backend full **570 passed**, focused **88 passed**, frontend full **397 passed / 73 files**, `tsc --noEmit`, Next production build, GitHub CLI 2.96.0 release/asset verification, 재다운로드 ZIP/sidecar digest, exact-tag pre/post verifier **10,317 entries**를 통과했다. 패치는 package fail-closed behavior와 QA contract seam만 변경하며 제품 feature behavior는 변경하지 않는다.
- 1.13.2 Release API `immutable=true`; PR #28 no-ff merge `a3dd77b93027dccffb36d663bb7ee1220c9fcdf5`, annotated tag object `62ba67eef7e2c2ac2357dc67d1cffb1c9eeedcc5` (merge commit으로 peel), published `2026-07-14T01:40:21Z`.
- 1.13.2는 현재 최신 운영 import이다. publication은 완료되었지만 사람이 air-gapped network에 물리적으로 import했다는 의미는 아니다.
- GitHub immutable releases 정책은 `enabled=true`; 기존 1.13.0 Release는 소급 적용되지 않아 `immutable=false`.
- 라이선스: All Rights Reserved (사내 사용 전제)

> [!CAUTION]
> `1.12.2` Release와 오프라인 ZIP은 철회되었습니다. `1.13.0` tag·asset·digest는 역사 릴리스로 보존되며 이동·교체·삭제하지 않습니다. 현재 운영 import는 정식 immutable `1.13.2` Release의 `AeroOne-offline-1.13.2.zip`과 업로드된 `.sha256`입니다. ZIP size는 `158728639` bytes, SHA-256은 `92d5178d6fb67573a1f0b36e0a744e00b4b559548081b463d45a4ba1d669d8a4`, sidecar asset SHA-256은 `02bb4827b149bbe36ffad1bdb7d6dd43b95a5c3c71b168671e7da854a4f2c6d5`이며 [Release URL](https://github.com/Py-CI-Park/AeroOne/releases/tag/1.13.2)에서 받습니다. published `2026-07-14T01:40:21Z`, API `immutable=true`입니다. `1.13.1`은 immutable historical patch로 보존하고, `1.13.0`은 `immutable=false` 역사 릴리스로 보존합니다. 물리적 air-gapped import 수행은 주장하지 않습니다.

---

## 목차

1. [이 문서를 읽는 두 종류의 독자](#1-이-문서를-읽는-두-종류의-독자)
2. [한 문장 요약 — 폐쇄망 사용 가능 여부](#2-한-문장-요약--폐쇄망-사용-가능-여부)
3. [현재 상태 스냅샷](#3-현재-상태-스냅샷)
4. [운영 모드 4종 비교](#4-운영-모드-4종-비교)
5. [End-to-End 배포 흐름](#5-end-to-end-배포-흐름)
6. [모드 A — 단일 PC (loopback)](#6-모드-a--단일-pc-loopback)
7. [모드 B — LAN 다중 PC (`--allow-host`)](#7-모드-b--lan-다중-pc---allow-host)
8. [검증 절차](#8-검증-절차)
9. [일상 운영](#9-일상-운영)
10. [백업·복원](#10-백업복원)
11. [보안 기본값과 정책](#11-보안-기본값과-정책)
12. [트러블슈팅과 FAQ](#12-트러블슈팅과-faq)
13. [테스트 인벤토리](#13-테스트-인벤토리)
14. [AI 에이전트 사용 지침](#14-ai-에이전트-사용-지침)
15. [참조 문서 색인](#15-참조-문서-색인)
16. [1.4.0 신규 기능 운영 안내](#16-140-신규-기능-운영-안내)
17. [1.5.0 Ollama AI·본문 검색 운영 안내](#17-150-ollama-ai본문-검색-운영-안내)
18. [Open Notebook co-deploy (1.5+)](#18-open-notebook-co-deploy-15)
19. [OpenAI-호환 AI 프로바이더 + 예약 대시보드 런처 (1.14+)](#19-openai-호환-ai-프로바이더--예약-대시보드-런처-114)

---

## 1. 이 문서를 읽는 두 종류의 독자

| 독자 | 기대하는 정보 | 우선 봐야 할 섹션 |
|---|---|---|
| 사람 운영자 (현장 설치/운영) | 어떤 모드로 어떻게 배포·검증·운영·복구하는가 | §4, §5, §6 또는 §7, §8, §9, §10, §12 |
| AI 에이전트 (자동화/유지보수) | 코드 정합성, 명령 시그니처, 분기 의미, 회귀 테스트 위치 | §3, §4, §11, §13, §14, §15 |

---

## 2. 한 문장 요약 — 폐쇄망 사용 가능 여부

**현재 최신 운영 import는 정식 immutable `1.13.2`입니다.** `1.12.2`는 철회되었고 `1.13.0`은 `immutable=false` 역사 보존 대상이며 `1.13.1`은 immutable historical patch입니다. `1.13.2`는 예기치 않은 Git tag inspection 실패를 `git-tag-inspection-failed`로 fail closed 합니다. 이 패치는 package fail-closed behavior와 QA contract seam만 변경하며 제품 feature behavior는 변경하지 않습니다. backend full 570, focused 88, frontend full 397/73, typecheck/build, GitHub CLI release/asset verification, 재다운로드 digest/sidecar, exact-tag pre/post verifier 10,317 entries가 통과했습니다. publication과 물리적 air-gapped import는 별개입니다.

---

## 3. 현재 상태 스냅샷

### 3.1 최근 릴리즈/단계 스냅샷

| 커밋 | 단계 | 의미 |
|---|---|---|
| `1.13.0` | 역사 릴리스 | 단계 26–27 기능·검증, PR #22/merge/tag/asset/digest 기록을 보존. tag·asset·digest는 이동·교체·삭제하지 않음 |
| `1.12.2` | **철회** | 화면 개선 이력만 보존. Release asset과 오프라인 ZIP은 신규 설치·재배포 금지 |
| `1.13.1` | immutable historical patch | 제품 tree와 historical digest/time을 보존. 1.13.2 이전 최신 운영 반입물이었던 역사 기록 |
| `1.13.2` | 정식 immutable Release | Git tag inspection 실패를 `git-tag-inspection-failed`로 fail closed. package fail-closed behavior와 QA contract seam만 변경하며 제품 feature behavior는 변경하지 않음. 현재 최신 운영 import |
| `1.12.1` | patch | 헤더 `로그인: <username>`/로그아웃 버튼, `login_events.status='logout'` 기록과 현재 세션 활동 제거, 사용자 생성의 필수 ID/PW·선택 이름/이메일(`users.display_name`, Alembic `20260707_0008`), 사용자 행별 **권한 수정** 패널, 감사 로그 페이지네이션·필터 초기화·현재 결과 CSV, 세션 마지막 갱신/15초 자동 새로고침 안내, 버전 배지 업데이트 날짜 표시 |
| `1.12.0` | 단계 25 | 권한 키 한국어 라벨·설명·카테고리 카탈로그와 RBAC 매트릭스 pill/유효권한 요약, 감사 로그 전용 탭(작업자/액션/상태/기간 검색·필터·CSV), 세션 상대시간·접속자 스코프 자동 새로고침·로그인 목록 페이지네이션, 탭 숫자 단축키 1~9·접이식 온보딩 도움말 (프론트-only, 백엔드/스키마 무변경) |
| `1.11.0` | 단계 24 | 관리자 로그인/CRUD same-origin `/api/frontend/auth/*`, `/api/frontend/admin/*` 프록시 통합, 전용 `/api/frontend/search/unified`, 탭형 `/admin` 콘솔(모듈/사용자/RBAC/세션/시스템/분류/검색/백업), RBAC 입력 위젯, 목록 검색/정렬/상태, ARIA Tabs, ResourceGrant key 방어 |
| `1.10.0` | 단계 23 | RBAC 읽기 권한 상승 차단, `can_read_collection` 단일 정책, NSA 0000 비밀번호 제거와 서버측 권한/ResourceGrant 적용, 사용자별 메뉴 힌트, 자산/config-health 진단, 사용자·그룹·리소스 권한/RBAC 매트릭스, 접속자·세션 대시보드 |
| `1.9.0` | 단계 22 | 관리자(서버 실행자) 전용 Admin 메뉴·개발중(Development)·Coming soon 노출, 헤더 다크·사용법·Admin 순서, 모듈 add/delete + 노출 대상(public/admin) 관리, 관리자 비밀번호 콘솔 변경, `start_offline` 마이그레이션 preflight |
| `1.8.0` | 단계 21 | 관리자 RBAC, same-transaction audit, `/admin` 운영 콘솔, `service_modules` DB 대시보드, 뉴스레터 자산/상태/bulk/taxonomy, 백업 manifest+sha256+복원 dry-run, 통합 검색 |
| `1.7.1` | 단계 20 | 뉴스레터 달력 접힘 가로 폭 축소, HTML 다운로드 버튼 강조, 사용법 팝업의 현재 서비스 중/개발중 구분 최신화 |
| `1.7.0` | 단계 19 | AeroAI Markdown 답변·HTML 검색 새 탭·모니터 높이 레이아웃, Viewer 미리보기 집중/전체화면, Open Notebook co-deploy 릴리즈 검증 |
| `1.6.2` | 단계 18 | 1.6.1 폐쇄망 smoke 결함 보강 — 뷰어 크기/스크롤, AeroAI 빈 응답, run_all/Open Notebook readiness, packaging hygiene |
| `1.6.1` | patch | 헤더 버전 표기와 사용 매뉴얼 정정 |
| `1.6.0` | 단계 17 | Viewer 탭 + 런처/AeroAI/HTML 스크롤 수정 |
| `1.5.0` | 단계 14–16 | Ollama AI 검색 + AI 대화 영속화/문서 근거 연결 |
| `1.0.22+` | 단계 7 | LAN 기본 바인딩 + `--local` loopback opt-out |

### 3.2 핵심 구성 요소

| 영역 | 파일 | 역할 |
|---|---|---|
| 패키징 | `offline_package.bat` → `scripts/build_offline_package.ps1` | tracked source allow-list + clean frontend build + production wheelhouse + 정확한 인스톨러를 Task 5 verifier로 검증한 뒤 ZIP/SHA 생성 |
| 설치 | `setup_offline.bat` | 폐쇄망 PC에서 사전 점검 → `.env` 작성 → pip install → DB → frontend build |
| 실행 | `start_offline.bat` | backend / frontend 동시 기동 + 자동 브라우저 |
| 프런트 wrapper | `scripts/start_frontend_offline.cmd` | `next start` 호스트 분기 |
| DB 상태 점검 | `backend/scripts/ensure_db_state.py` | exit 0/1/2/3 으로 alembic upgrade vs stamp 분기 |
| 보안 정책 | `backend/app/core/config.py` | `closed_network` 모드 + `validate_runtime_security` |

### 3.3 테스트 통계

- backend 전체: **570 passed**
- frontend 전체: **397 passed / 73 files**
- browser/package: production Chrome smoke·matrix·Axe·Lighthouse·React 및 QA ZIP pre-stage/post-ZIP verifier 통과
- 핵심 회귀: 모드 정책, LAN/loopback 배치, `run_all.bat` Open Notebook readiness, allow-list package builder/pre-post verifier, 관리자 auth/admin same-origin 프록시, ResourceGrant 방어, 자격 회전 service/listener preflight·연속 DB lock·DPAPI recovery·crash 재개·WPF ValidateOnly, Activity privacy, 관리자 Overview/Users/Sessions/Modules, 뉴스레터 상태/자산/bulk, 문서/컬렉션/AI API

### 3.4 릴리즈 1.13.2 현재 운영 import
`1.13.0` tag·asset·digest와 `1.13.1`의 게시 사실·정확한 commit/tag/URL/digest/size는 역사 기록으로 보존합니다. 현재 운영 import는 [정식 immutable Release `1.13.2`](https://github.com/Py-CI-Park/AeroOne/releases/tag/1.13.2)의 `AeroOne-offline-1.13.2.zip`과 함께 업로드된 `.sha256`입니다. PR #28 no-ff merge `a3dd77b93027dccffb36d663bb7ee1220c9fcdf5`, annotated tag object `62ba67eef7e2c2ac2357dc67d1cffb1c9eeedcc5` (merge commit으로 peel), published `2026-07-14T01:40:21Z`, API `immutable=true`, ZIP size `158728639`, ZIP SHA-256 `92d5178d6fb67573a1f0b36e0a744e00b4b559548081b463d45a4ba1d669d8a4`, sidecar SHA-256 `02bb4827b149bbe36ffad1bdb7d6dd43b95a5c3c71b168671e7da854a4f2c6d5`입니다. immutable historical patch `1.13.1`의 published `2026-07-13T23:31:18Z`과 ZIP SHA-256 `b05445b53ecca02175afcd016ac0e896163010e1a06a0b996b8ebe79a798e290` 및 `1.13.0`의 역사 digest/time은 변경하지 않습니다. 물리적 air-gapped import 수행은 주장하지 않습니다.

| 반입물 | 릴리즈/생성 위치 | 폐쇄망 배치 | 필수 여부 |
|---|---|---|---|
| `AeroOne-offline-1.13.2.zip` + `.sha256` | immutable=true로 확인된 정식 AeroOne GitHub Release `1.13.2` asset | `D:\AeroOne\` 로 압축 해제 후 `setup_offline.bat` | 필수 |
| `AeroOne-bundle.zip` + `.sha256` | immutable=true로 확인된 같은 Release asset 또는 Open Notebook `dist\` | `D:\AeroOne-bundle\` 로 압축 해제 후 `2-airgap-install.bat` | Open Notebook 사용 시 필수 |
| Ollama 모델 폴더(`manifests\`, `blobs\`) | 인터넷 PC `%USERPROFILE%\.ollama\models` | 폐쇄망 PC `%USERPROFILE%\.ollama\models` | AeroAI/Open Notebook AI 사용 시 필수 |
| `OllamaSetup.exe` | 인터넷 PC에서 별도 다운로드 | 폐쇄망 PC에 1회 설치 | 폐쇄망 PC에 Ollama 없을 때 필수 |

권장 배치:
```cmd
D:\AeroOne\
D:\AeroOne-bundle\
```
두 폴더를 형제로 두면 `D:\AeroOne\scripts\run_all.bat` 가 기본값(`..\AeroOne-bundle`)만으로 AeroOne 과 Open Notebook 을 순서대로 띄웁니다. 단일 PC 검증은 `scripts\run_all.bat --local`, LAN 운영은 기본 실행 또는 `--allow-host=<IP>` 를 사용합니다.

---

## 4. 운영 모드 4종 비교

`backend/.env` 의 `APP_ENV` 값에 따라 보안 정책이 분기됩니다.

| 모드 | secure cookie | secret 강도 검증 | 용도 |
|---|---|---|---|
| `development` | OFF | OFF | 개발자 로컬 (`setup.bat` 기본) |
| `test` | OFF | OFF | pytest 픽스처 전용 (`tests/conftest.py`) |
| `closed_network` | OFF | **ON** | 폐쇄망 HTTP 운영 (`setup_offline.bat` 기본) |
| `production` | **ON** | **ON** | 인터넷 노출 HTTPS (HTTPS + 리버스 프록시 별도 준비 필수) |

`closed_network` 모드는 단계 6에서 신설되었으며, HTTP 폐쇄망에서 쿠키가 살아 있는 상태에서 `JWT_SECRET_KEY` / `ADMIN_PASSWORD` 가 `change-me` 또는 짧을 때 부팅 즉시 거부합니다.

---

## 5. End-to-End 배포 흐름

```
[온라인 PC]                                      [폐쇄망 PC]
setup.bat                ─┐
start.bat (선택, 검증)    │
offline_package.bat      ─┘──→ ZIP 복사 ──→  압축 해제
                                              setup_offline.bat [--allow-host=<host>]
                                              start_offline.bat [--allow-host=<host>]
                                              (관리자에서 Import / Sync)
```

1. 온라인 PC `setup.bat` — 의존성·DB·시드 완비
2. (선택) `start.bat` — 동작 검증
3. 온라인 PC `offline_package.bat` — clean tree의 정확한 태그에서는 `dist\AeroOne-offline-X.Y.Z.zip` + `.sha256`, 태그 전 QA에서는 `artifacts\qa\X.Y.Z\X.Y.Z-pr-<SHA>\`에 `publishable=false` 산출물 생성
4. ZIP 을 USB / 사내 파일서버 등 단방향 허용 경로로 전달
5. 폐쇄망 PC 압축 해제 — 권장 위치 `D:\AeroOne\` 또는 `C:\Programs\AeroOne\` (한글·공백 금지)
6. (Python/Node 부재 시) `offline_assets\installers\python-*.exe`, `node-*.msi` 먼저 실행
7. `setup_offline.bat` — 사전 점검 통과 후 자동 설치
8. `start_offline.bat` — 두 포트 준비 시 브라우저 자동 오픈
9. 신규 발행 시 `_database\newsletter\` 에 파일 추가 → 관리자 페이지 **Import / Sync** 클릭

### 5.1 9단계 진행 체크리스트 (실 배포 추적용)

운영자가 본 PC 에서 폐쇄망 PC 까지 한 번에 따라가며 체크박스로 진행을 추적할 때 사용합니다. 마크다운 뷰어에서 `[ ]` 를 `[x]` 로 바꿔 가며 진행 상황을 기록할 수 있습니다.

#### 본 PC — 인터넷 가능

- [ ] **단계 1** — Python 3.12.x Windows installer (64-bit) 와 Node 20.x LTS .msi (64-bit) 다운로드.
  - 출처: <https://www.python.org/downloads/windows/> , <https://nodejs.org/en/download>
  - 완료 조건: 두 파일 (`python-3.12.x-amd64.exe`, `node-v20.x.x-x64.msi`) 확보.
  - 매뉴얼: `offline_installers/README.md`, `docs/runbook/windows-offline.md` §3.

- [ ] **단계 2** — 두 인스톨러를 `offline_installers/` 폴더에 그대로 배치.
  - 명령: `copy <다운로드받은_파일> D:\Chanil_Park\Project\Programming\AeroOne\offline_installers\`
  - 완료 조건: `dir offline_installers` 가 두 파일을 보여줌.
  - 매뉴얼: `offline_installers/README.md`.

- [ ] **단계 3** — 패키징.
  - 명령: `cd D:\Chanil_Park\Project\Programming\AeroOne` → `offline_package.bat`
  - 완료 조건: 정확한 annotated tag가 HEAD인 clean tree에서 `dist\AeroOne-offline-X.Y.Z.zip`과 `.sha256` 생성. PR 검증 단계에서는 `artifacts\qa\X.Y.Z\X.Y.Z-pr-<SHA>\AeroOne-offline-X.Y.Z-pr-<SHA>.zip` 생성.
  - 검증: builder 출력의 pre-stage/post-ZIP `{"ok": true}` 2건과 최종 `[OK] publishable=... sha256=...` 확인.
  - 매뉴얼: `docs/runbook/windows-offline.md` §1·§2, 본 가이드 §5 다이어그램.

#### 이동

- [ ] **단계 4** — ZIP 1개를 폐쇄망 PC 로 복사 (USB / 사내 파일서버 등 **단방향 허용 경로**).
  - 완료 조건: 폐쇄망 PC 에서 ZIP 파일이 보임.
  - 매뉴얼: `docs/runbook/windows-offline.md` §2.

#### 폐쇄망 PC — 인터넷 차단

- [ ] **단계 5** — 권장 위치에 압축 해제.
  - 권장: `D:\AeroOne\`, `C:\Programs\AeroOne\`, `C:\Users\<유저>\AeroOne\` (모두 한글·공백 없음).
  - 피해야 할 곳: `C:\Program Files\` (관리자 권한), 데스크톱 (path limit), 한글/공백 포함 경로.
  - 완료 조건: 압축 해제한 폴더 안에 `setup_offline.bat`, `start_offline.bat`, `offline_assets\` 가 보임.
  - 매뉴얼: `docs/runbook/windows-offline.md` §4.

- [ ] **단계 6** — (Python/Node 부재 시) 동봉된 인스톨러 두 개 차례로 실행.
  - 명령: `offline_assets\installers\python-3.12.x-amd64.exe` → 설치 마법사에서 **"Add python.exe to PATH"** 체크.
  - 명령: `offline_assets\installers\node-v20.x.x-x64.msi` → 설치 마법사에서 **"Add to PATH"** 체크.
  - 완료 조건: 새 CMD 창에서 `where py`, `where node`, `where npm` 모두 경로 출력.
  - 이미 설치되어 있으면 건너뜀.
  - 매뉴얼: `docs/runbook/windows-offline.md` §3.

- [ ] **단계 7** — 설치. **`--dry-run` 옵션은 붙이지 마세요** (그 옵션은 실제 설치 없이 단계만 미리보기). 곧장 실제 설치를 시작하려면:
  - 단일 PC 전용(이 PC 만): `setup_offline.bat --local` / LAN 배포(기본): `setup_offline.bat` (옵션 없이 = LAN) — 또는 탐색기에서 파일 더블클릭(기본 LAN)
  - LAN 다중 PC 운영: `setup_offline.bat --allow-host=192.168.1.10` (사내 IP 로 교체)
  - 미리 단계만 보고 싶으면 `setup_offline.bat --dry-run` — 설치 안 함, 단계 흐름만 출력. **단계 7 의 정답은 옵션 없이 실행**.
  - 완료 조건: `[OK] setup_offline.bat 완료` 메시지 + `backend\.env`, `frontend\.env.local`, `backend\.venv\`, `backend\data\aeroone.db` 모두 생성.
  - backend 의존성은 동봉 wheelhouse에서 `backend\requirements.txt`만 `--no-index`로 설치하며 개발용 `requirements-dev.txt`는 공개 패키지에 포함하거나 설치하지 않음.
  - 매뉴얼: `docs/runbook/windows-offline.md` §6, 본 가이드 §6 / §7.

- [ ] **단계 8** — 실행.
  - 단일 PC 전용(이 PC 만): `start_offline.bat --local`
  - LAN(기본): `start_offline.bat` (옵션 없이 = LAN, IP 자동 감지) 또는 호스트 고정 `start_offline.bat --allow-host=192.168.1.10`
  - 시작 시 maintenance preflight가 실행 파일의 물리 경로를 확인한 뒤 backend/frontend를 기동하므로, 패키지 폴더를 이동한 경우에도 `start_offline.bat` 자체가 그 폴더 안에 있어야 함.
  - 완료 조건: 두 CMD 창 (backend 녹색, frontend 청록) 자동 기동 + 브라우저 자동 오픈 (`http://localhost:29501/` 또는 `http://<host>:29501/`).
  - 매뉴얼: `docs/runbook/windows-offline.md` §5, 본 가이드 §6 / §7.

- [ ] **단계 9** — `ADMIN_PASSWORD` 확인 + 관리자 로그인 검증.
  - 명령: `type backend\.env | findstr ADMIN_PASSWORD` → 출력된 48자 hex 비밀번호 메모.
  - 검증: 브라우저에서 `http://localhost:29501/login` (또는 `http://<host>:29501/login`) 으로 들어가 `admin` + 위 비밀번호로 로그인 성공.
  - 추가 검증 (선택): `curl http://localhost:18437/api/v1/health` → `{"status":"ok",...}`.
  - 매뉴얼: `docs/runbook/windows-offline.md` §7.3, 본 가이드 §8.2 + §11.1.

> 단계 7 또는 8 에서 실패하면 본 가이드 §12 트러블슈팅 표를 먼저 확인하세요. 가장 흔한 두 원인은 (a) `[ERROR] Python` / `[ERROR] Node.js` (단계 6 인스톨러 미실행 또는 PATH 미반영), (b) 포트 18437/29501 점유 (다른 프로세스가 같은 포트 사용 중) 입니다.

---

## 6. 모드 A — 단일 PC (loopback, `--local`)

> **1.0.22+ 부터 옵션 없는 기본 실행은 LAN(모드 B)입니다.** 이 PC 에서만 쓰는 모드 A 는 이제 `--local` 로 명시 선택합니다(localhost 전용, 외부 노출 없음).

```cmd
setup_offline.bat --local
start_offline.bat --local
```

| 자리 | 값 |
|---|---|
| Backend uvicorn | `127.0.0.1:18437` |
| Frontend next start | `127.0.0.1:29501` |
| 자동 오픈 URL | `http://localhost:29501/` |
| `CORS_ORIGINS` | `http://localhost:29501` |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:18437` |
| `SERVER_API_BASE_URL` | `http://127.0.0.1:18437` |

같은 PC 의 브라우저에서만 접속 가능. 외부 노출 없음, 가장 안전.

---

## 7. 모드 B — LAN 다중 PC (`--allow-host`)

옵션 1개로 5자리(backend 호스트, frontend 호스트, CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL, 자동 오픈 URL)를 동시에 LAN 모드로 전환합니다.

### 7.1 옵션 형태 두 가지

```cmd
:: 형태 1 — 옵션 인자 (CMD 가 = 토큰을 자동 분리하지만 capture_host 서브루틴이 흡수)
setup_offline.bat --allow-host=192.168.1.10
start_offline.bat --allow-host=192.168.1.10

:: 형태 1b — auto: 이 PC 의 LAN IPv4 를 자동 감지 (scripts\windows\detect_lan_ip.ps1)
start_offline.bat --allow-host=auto

:: 형태 2 — 환경 변수 (자동화 스크립트 권장)
set AEROONE_ALLOW_HOST=192.168.1.10
setup_offline.bat
start_offline.bat
```

### 7.2 LAN 모드의 5자리

| 자리 | 기본 (loopback) | LAN 모드 |
|---|---|---|
| Backend uvicorn | `127.0.0.1:18437` | `0.0.0.0:18437` |
| Frontend next start | `127.0.0.1:29501` | `0.0.0.0:29501` |
| 자동 오픈 URL | `http://localhost:29501/` | `http://<host>:29501/` |
| `CORS_ORIGINS` | `http://localhost:29501` | `http://localhost:29501,http://<host>:29501` |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:18437` | `http://<host>:18437` |
| `SERVER_API_BASE_URL` | `http://127.0.0.1:18437` | `http://127.0.0.1:18437` (Next.js SSR 은 같은 PC 자기 자신을 IPv4 loopback 으로 호출) |

### 7.3 LAN 모드 운영 주의사항

- **자기 PC 도 반드시** `http://<host>:29501/` 로 접속. `localhost` 로 들어가면 페이지 호스트와 API 호스트가 달라 쿠키가 격리되어 로그인 실패.
- 자동 오픈 URL 을 그대로 사용하면 항상 같은 호스트로 통일됨.
- LAN 의 다른 PC 접속은 이 PC 에서 `scripts\allow_lan_firewall.cmd` 를 관리자 권한으로 실행해 인바운드(`18437`/`29501`, 로컬 서브넷 한정)를 허용 (`--remove` 로 원복). Windows 방화벽에서 두 포트를 LAN 외부로 차단하는 규칙도 함께 두기 권장.
- 인터넷 노출 production 으로 사용 금지 — 트래픽 평문 HTTP.

---

## 8. 검증 절차

### 8.1 dry-run 3종 (실 배포 없이 분기 흐름 검증)

```cmd
setup_offline.bat --dry-run --no-pause
start_offline.bat --dry-run
offline_package.bat --dry-run
```

각 dry-run 출력에 LAN 모드 인자를 넣으면 LAN 흐름도 동일하게 검증 가능합니다.

```cmd
setup_offline.bat --dry-run --no-pause --allow-host=192.168.1.10
start_offline.bat --dry-run --allow-host=192.168.1.10
```

`setup_offline.bat --dry-run`은 파일·DB·환경을 변경하지 않는 순수 미리보기이므로 실행 중인 서버의 maintenance gate를 기다리지 않습니다. 실제 설치에서만 workspace gate를 획득하며, 따라서 운영 서버를 유지한 채 LAN/loopback 분기 출력을 점검할 수 있습니다. `offline_package.bat --dry-run`은 clean tree 여부, release/QA mode, allow-list 경로 수와 출력 위치만 검증하며 의존성 다운로드나 ZIP 생성은 하지 않습니다.

### 8.2 라이브 5단계 시퀀스 (`start_offline.bat` 실행 후)

```cmd
:: 1. 헬스체크
curl http://localhost:18437/api/v1/health
:: 기대: {"status":"ok","db_ok":true,"import_root_exists":true,"storage_root_exists":true}

:: 2. 공개 목록 (페이지네이션 미지원 — HTTP 200 만 확인)
curl http://localhost:18437/api/v1/newsletters

:: 2-1. 단건 조회 (최신 발행 1건)
curl http://localhost:18437/api/v1/newsletters/latest

:: 3. 관리자 로그인 (admin_session + csrf_token 두 쿠키 발급 확인)
curl -i -X POST -H "Content-Type: application/json" ^
     -d "{\"username\":\"admin\",\"password\":\"<backend\.env 의 ADMIN_PASSWORD>\"}" ^
     http://localhost:18437/api/v1/auth/login
```

LAN 모드일 때는 `http://<host>:18437` 로 호출.

### 8.3 단위 테스트 회귀

```cmd
cd backend
.venv\Scripts\activate
set PYTHONPATH=.
python -m pytest tests -q
```

역사 릴리스 `1.13.0`의 전체 제품 게이트(backend **570 passed**, frontend **397 passed / 73 files**, typecheck/build, production Chrome·package gate)는 계승 근거로 보존합니다. `1.13.2`는 backend **570 passed**, focused **88 passed**, frontend **397 passed / 73 files**, typecheck/build, GitHub CLI 2.96.0의 `release verify` 및 두 asset `verify-asset`, 재다운로드 ZIP/sidecar digest, exact-tag pre/post verifier **10,317 entries**를 통과했습니다. 이 패치는 package fail-closed behavior와 QA contract seam만 변경하며 제품 feature behavior는 변경하지 않습니다. `1.13.2` publication은 물리적 air-gapped import를 주장하지 않습니다. `1.12.2` 기록은 철회 배포본의 승인 기준으로 재사용하지 않습니다.

### 8.4 단계 8 시뮬레이션 결과 (참고)

| 검증 | 결과 | 발견 사항 |
|---|---|---|
| `setup_offline.bat --dry-run` | PASS | 6단계 분기 모두 의도대로 |
| `start_offline.bat --dry-run --local` | PASS | backend `127.0.0.1` / frontend `127.0.0.1` (옵션 없는 기본은 1.0.22+ 부터 LAN) |
| `offline_package.bat --dry-run` | PASS | robocopy 제외 목록과 wheelhouse 경로 정합 |
| `GET /api/v1/health` | HTTP 200 | db_ok / import_root / storage_root 모두 true |
| `GET /api/v1/newsletters` | HTTP 200 | 38건 반환 (limit 미지원, F1) |
| `POST /api/v1/auth/login` | HTTP 200 | `admin_session` + `csrf_token` 동시 발급 |
| `/api/v1/categories`, `/api/v1/tags` | HTTP 404 | 의도된 admin-only (F2) |

자세한 절차는 §15의 `phase-8-offline-simulation.md`.

---

## 9. 일상 운영

| 시점 | 명령 / 절차 |
|---|---|
| PC 부팅 후 | `start_offline.bat` (LAN 모드면 `--allow-host=<host>` 또는 `AEROONE_ALLOW_HOST` 유지) |
| 신규 발행 추가 | `_database\newsletter\` 에 HTML/PDF 복사 (`newsletter_YYYYMMDD.html` 형식) → `/newsletters` 새로고침 시 자동 반영 (서버 재시작 불필요). 즉시 강제는 `/admin` 또는 `/admin/imports` 의 **Import / Sync** |
| 문서 추가 | `_database\document\` 에 HTML 복사 (하위 폴더로 분류하면 폴더 트리로 구분) → `/documents` 새로고침 시 바로 반영 (서버 재시작 불필요) |
| Civil 카탈로그 추가 | `_database\civil_aircraft\` 에 HTML 복사 (여러 파일, 하위 폴더 가능) → `/reports/civil-aircraft` 새로고침 시 목록에 반영 |
| NSA 문서 추가 | `_database\nsa\` 에 HTML 복사 (하위 폴더로 분류 가능) → `/nsa` 는 관리자이거나, 로그인 사용자에게 전역 `collections.nsa.read`/legacy `search.nsa.read` 권한 또는 `collection:nsa` ResourceGrant 중 하나가 있을 때 목록/본문을 제공 |
| 메타데이터/게시 상태 수정 | 관리자 화면의 **편집** 버튼 (제목·요약·카테고리·태그·게시 상태·활성 여부·썸네일) 또는 뉴스레터 목록 일괄 게시/보관 |
| 카테고리/태그 정리 | `/admin` 콘솔의 카테고리/태그 관리에서 생성·정렬·비활성화 |
| Markdown 신규 | 관리자 화면 우측 상단 **새 Markdown** 버튼 |
| 대시보드 카드 변경 | `http://<host>:29501/admin` 콘솔의 **모듈** 탭에서 `service_modules` 카드 추가·삭제, 활성/비활성, Development/Coming soon, 링크·설명·순서, 노출 대상(public: 모든 사용자 / admin: 관리자 전용)을 조정. 개발중·Coming soon 카드와 Admin 메뉴는 관리자에게만 노출 |
| 사용자/권한 관리 | `http://<host>:29501/admin` 콘솔의 **사용자/RBAC** 탭에서 admin/user/pending 사용자, 접속 아이디/임시 비밀번호, 선택 이름/이메일, 직접 권한, 그룹 권한, 리소스 권한, RBAC 매트릭스를 관리. 사용자 행의 **권한 수정** 버튼으로 직접 권한 패널을 펼치며, self-lockout 과 마지막 admin 제거는 API 가 거부 |
| 운영 상태 확인 | `http://<host>:29501/admin` 콘솔의 **세션/시스템/검색/백업** 탭에서 버전/DB/뉴스레터/자산/config-health/read/AI/audit/백업 요약, 통합 검색, 백업 생성·검증·복원 점검을 확인 |
| NSA 권한 부여 | `/admin` 사용자/권한 화면에서 대상 계정 또는 그룹에 전역 `collections.nsa.read`(또는 legacy `search.nsa.read`) 권한이나 `collection:nsa` ResourceGrant 중 하나를 부여합니다. 관리자는 별도 grant 없이 접근할 수 있으며, 이 세 경로 중 하나도 없으면 fail-closed |
| 접속자/세션 확인 | `/admin` 접속자 대시보드에서 로그인/로그아웃 이벤트, 세션 활동, 익명 IP 읽음 추적을 확인하고 보존 정책에 따라 감사 로그를 남긴 뒤 purge |
| 자산 진단 | `/admin` 자산 진단/config-health 에서 `_database`, storage, 썸네일, DB/마이그레이션 상태를 확인하고 누락 경로를 배포 산출물 또는 운영 백업에서 복구 |
| 단일 관리자 비밀번호 변경 | `/admin` 콘솔의 **관리자 계정 / 비밀번호** 에서 현재 비밀번호 확인 후 직접 변경합니다. 해당 계정의 기존 세션은 무효화됩니다. |
| 자격 증명 노출 사고 | 서비스를 중지하고 `scripts\rotate_aeroone_credentials.ps1`을 실행해 JWT, 전체 사용자 비밀번호, session version, live session을 하나의 사고 단위로 회전합니다. `setup_offline.bat` 재실행은 기존 DB 전체를 회전하지 않으므로 대체 수단이 아닙니다. 상세: [`runbook/credential-rotation.md`](runbook/credential-rotation.md). |
| AI 프로바이더 설정/전환 (1.14+) | `/admin` 콘솔 시스템 탭의 **AI 프로바이더** 섹션에서 Base URL/모델/API 키 저장 → 영속 테스트 `ok` → Activate → 선택(Ollama/OpenAI-호환) 전환. 상세: 본 문서 §19 |

### 9.1 관리자 same-origin 접속 원칙

운영자와 사용자는 로그인(`/login`)과 관리자 콘솔(`/admin`)을 모두 같은 frontend origin 인 `http://<host>:29501` 에서 엽니다. 브라우저는 backend origin(`http://<host>:18437`)을 직접 호출하지 않고 `/api/frontend/auth/*`, `/api/frontend/admin/*`, `/api/frontend/search/unified` same-origin 경로만 호출합니다. frontend 서버가 backend 로 relay 하므로 LAN 클라이언트에서도 쿠키/CORS 경계가 흔들리지 않습니다. 로그인 후 헤더는 `로그인: <username>` 과 `로그아웃` 버튼을 표시하고, 로그아웃은 DB 의 `login_events` 에 `logout` 이벤트를 남긴 뒤 현재 세션 쿠키를 제거합니다. `/admin` 콘솔은 모듈/사용자/RBAC/세션/시스템/분류/검색/백업/감사 탭으로 나뉘며, 1.12.0 부터 감사 로그 전용 탭·권한 라벨 카탈로그·세션 자동 새로고침·탭 숫자 단축키를 제공합니다.

### 9.2 NSA 접근제어 주의

1.10.0 부터 `/nsa` 의 `0000` 비밀번호 가림막은 제거되었습니다. NSA 는 암호화 비밀 저장소가 아니라 `_database\nsa\` HTML 컬렉션이며, 서버는 관리자이거나 로그인 세션에 전역 `collections.nsa.read`/legacy `search.nsa.read` 권한 또는 일치하는 `collection:nsa` ResourceGrant 중 하나가 있을 때 목록·본문·검색을 제공합니다. 운영자는 관리자 화면에서 계정/그룹 권한 또는 리소스 grant 를 명시적으로 부여하고, 미부여 사용자가 403 을 받는지 확인해야 합니다.

---

## 10. 백업·복원

### 10.1 백업 대상

| 경로 | 의미 | 권장 주기 |
|---|---|---|
| `backend\data\aeroone.db` | 메타데이터 + 사용자/RBAC + 감사 로그 + service_modules + 뉴스레터 상태 | 매일 |
| `storage\markdown\` | 운영자가 직접 작성한 Markdown 본문 | Markdown 신규/수정 시 |
| `storage\thumbnails\` | 업로드된 썸네일 | 썸네일 업로드 시 |
| `_database\newsletter\` | 뉴스레터 발행 원본 HTML/PDF | 신규 발행 시 |
| `_database\civil_aircraft\` | 민간항공기 규격 정적 HTML 보고서 (데이터 투입 위치) | 보고서 갱신 시 |
| `_database\document\` | 문서 보관소 HTML (하위 폴더로 분류 가능, `/documents` 폴더 트리) | 문서 추가/갱신 시 |
| `_database\nsa\` | NSA 탭 문서 (서버측 권한/ResourceGrant 통과 후 표시) — 암호화 저장소가 아니므로 별도 보안 분류 준수 | 문서 추가/갱신 시 |

관리자 콘솔의 **백업 생성** 버튼은 `storage\admin_backups\AeroOne-backup-*.zip` 형태의 manifest+sha256 백업을 만든 뒤 검증할 수 있습니다. 같은 줄의 **복원 점검**은 manifest/schema/checksum 과 포함 루트만 확인하는 dry-run 이며 실제 DB/파일 복원은 수행하지 않습니다. 이 ZIP 은 public/static root 밖에 생성되며, DB와 운영자가 관리하는 Markdown/thumbnail 자산을 포함합니다. 원본 `_database\` 폴더는 대용량 원본 보관 정책에 맞춰 별도 파일 백업을 유지하세요.
```cmd
xcopy /Y /E /I backend\data D:\backup\AeroOne\data
xcopy /Y /E /I storage D:\backup\AeroOne\storage
xcopy /Y /E /I _database D:\backup\AeroOne\_database
```

### 10.2 복원

같은 PC 또는 다른 폐쇄망 PC 에 새로 압축 해제한 뒤, 위 세 경로를 그대로 덮어쓰고 `setup_offline.bat` 실행. `ensure_db_state.py` 가 기존 DB 의 alembic 메타 부재를 감지해 `alembic stamp head` 분기로 데이터 보존하며 진행합니다 (§11.3 참고). 1.14+ 의 OpenAI-호환 프로바이더 자격(`%ProgramData%\AeroOne\provider-credentials\`)은 위 백업 대상에 포함되지 않으며, 다른 PC 또는 다른 서비스 신원으로 복원했다면 §19.7 의 재진입 절차를 새로 밟아야 합니다.

---

## 11. 보안 기본값과 정책

### 11.1 비밀 자동 생성

`setup_offline.bat` 매 실행 시 Windows PowerShell 5.1 호환 `RandomNumberGenerator.Create().GetBytes(...)` 로 다음 두 값을 새로 생성합니다.

- `JWT_SECRET_KEY` — 64자 hex (32바이트)
- `ADMIN_PASSWORD` — 48자 hex (24바이트)

기존 `backend\.env` 는 `.env.bak` 으로 자동 백업.

### 11.2 `validate_runtime_security` 분기

| 모드 | `change-me` 또는 짧은 secret 거부 |
|---|---|
| `development` | 면제 |
| `test` | 면제 |
| `closed_network` | **거부** (단계 6 신설) |
| `production` | **거부** |

`backend/app/core/config.py:85-95` 의 `validate_runtime_security()` 가 부팅 시 1회 검증 (`backend/app/main.py:18`).

### 11.3 `ensure_db_state.py` 종료 코드

| 종료 코드 | 의미 | setup 다음 단계 |
|---|---|---|
| 0 | DB + alembic_version 정상 | `alembic upgrade head` (이미 head 면 no-op) |
| 1 | 호출 인자 누락 | 사용 오류 |
| 2 | DB 부재 또는 핵심 테이블 부재 | `alembic upgrade head` (스키마 신규) |
| 3 | 핵심 테이블만 있고 alembic_version 부재 | `alembic stamp head` (메타데이터만, 데이터 보존) |

핵심 테이블 정의: `{users, newsletters, categories}` (`backend/scripts/ensure_db_state.py` 의 `CORE_TABLES` 상수). docstring 표 + 본 문서 §11.3 + `phase-9-docstring.md` + `tests/unit/test_ensure_db_state.py` 가 동일 종료 코드 매핑을 4자리에서 함께 유지합니다.

### 11.4 정적 자원 노출

`/storage/thumbnails` 마운트만 정적 노출. `markdown` 과 `attachments` 는 비공개. HTML 미리보기는 backend sanitize + CSP + sandbox iframe 3중. `_debug.html` 은 import / 공개 모두에서 제외.

### 11.5 LAN 모드 추가 권장

- 신뢰 가능한 폐쇄망 LAN 안에서만 사용
- Windows 방화벽 `18437`, `29501` 두 포트를 LAN 외부로 차단하는 인바운드 규칙 추가
- 인터넷 노출 시 반드시 HTTPS + `APP_ENV=production` + 리버스 프록시 (별 PR 작업)

### 11.5.1 자격 증명 사고 대응 회전

`setup.bat`과 `setup_offline.bat`은 설치·의존성·환경 파일·초기 시드를 준비합니다. setup 재실행으로 환경 파일 값이 다시 생성되더라도 기존 DB의 모든 사용자 비밀번호, `session_version`, live session이 원자적으로 회전되는 것은 아닙니다.

노출이 의심되면 서비스를 중지하고 [`scripts\rotate_aeroone_credentials.ps1`](../scripts/rotate_aeroone_credentials.ps1)을 사용합니다. 도구는 알려진 AeroOne Windows 서비스와 root/backend 환경에 설정된 포트 listener를 변경 전에 확인하며, 남아 있으면 자동 종료하지 않고 fail closed 합니다. configured admin과 활성 admin을 prepare/commit 양쪽에서 검증하고, recovery 생성부터 commit까지 하나의 `BEGIN IMMEDIATE` writer lock을 유지하면서 전체 사용자 비밀번호·session version·live session·ledger를 원자 반영합니다. 비활성 사용자는 활성화하지 않으며 로그인 실패는 기존 정책대로 **401**입니다.

완료된 bundle은 먼저 headless 검증한 뒤 같은 Windows 사용자 세션의 WPF 뷰어로 확인합니다. 임의 경로 인자는 없고 current SID의 DPAPI, exact secure path·ACL·schema를 모두 통과해야 합니다. setup 재실행으로 환경 파일의 초기 시드 값이 바뀌어도 기존 DB의 비밀번호 해시·세션은 교체되지 않으므로 이 뷰어와 회전 도구를 대체할 수 없습니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\view_aeroone_credentials.ps1 -ValidateOnly
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File scripts\view_aeroone_credentials.ps1
```

비밀번호는 기본 마스킹이며 명시적으로 표시하거나 복사합니다. 복사 시 Windows clipboard history·cloud roaming 제외 형식을 함께 게시하고, 다른 앱의 일시적 clipboard 점유에는 250ms 간격으로 최대 20회 게시·확인을 재시도합니다. 복사한 값이 그대로 남아 있을 때만 원자적으로 지우므로 이후 복사한 다른 내용은 삭제하지 않습니다. 30초 후 삭제가 일시적으로 실패하면 최대 5회 재시도하고 소유 상태를 유지합니다. 마지막 실패 뒤에는 명시적 재시도 버튼을 표시하며, 해당 비밀번호가 남아 있는 동안 창 닫기를 거부합니다.

중단 재개, DPAPI 보호 산출물, DB 복원 뒤 old completed 상태 보존과 명시적 신규 회전, retention 이후 삭제 책임은 [`runbook/credential-rotation.md`](runbook/credential-rotation.md)를 단일 진실 원천으로 따릅니다.

### 11.6 읽음추적과 개인정보 (IP)

뉴스레터 읽기는 접속 IP 별 열람 횟수로 기록되어 관리자만 `/admin/read-events` 에서 조회한다(독자 고지 없음 — 운영자 결정). 주의할 점:

- **IP 는 개인정보로 분류될 수 있다.** 고지 없는 수집은 사내 정책·법적 검토 대상이 될 수 있으므로 **사내 고지·보존기간 정책 수립을 권고**한다.
- **IP ≠ 개인.** DHCP 표류·NAT·공유 PC 환경에서는 IP 가 사람과 1:1 이 아니다. LAN 모드에서만 실제 IP 가 잡히고, `--local` 이면 전부 `127.0.0.1` 로 퇴화한다.
- **보존은 무기한**이며 자동 삭제가 없다. 정리는 관리자 화면 "전체 기록 삭제"(CSRF) 또는 SQL 로 수동 수행한다.
- 읽음 기록은 `backend/data/aeroone.db` 에 저장되어 기존 DB 백업 대상에 자동 포함된다.
- 설계·한계·절차 상세: [`runbook/read-tracking.md`](runbook/read-tracking.md)

---

## 12. 트러블슈팅과 FAQ

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| `setup_offline.bat` 사전 점검에서 `[ERROR] Python` | Python 미설치 / PATH 누락 | `offline_assets\installers\python-*.exe` 실행 → CMD 새로 열기 |
| 같은 자리에서 `[ERROR] Node.js` | Node 미설치 / PATH 누락 | `offline_assets\installers\node-*.msi` 실행 → 재시작 |
| 사전 점검 통과 후 wheelhouse 단계 실패 | wheel 파일 일부 누락 | 온라인 PC 에서 `offline_package.bat` 재실행 후 ZIP 재배포 |
| 포트 충돌 | 다른 프로세스 점유 | `netstat -ano | findstr 18437` 로 PID 확인 후 종료 |
| 페이지 로딩 후 `Failed to fetch` (뉴스레터·관리자) | 페이지 호스트 ↔ API 호스트 다름 | 주소를 동일 호스트 (`localhost` 또는 `<host>`) 로 통일 |
| Document·Civil·NSA 본문이 외부 PC 에서 `Failed to fetch` | (1.4.0 이전 버전) 클라이언트가 `localhost:18437` 를 직접 호출 | **1.4.0 이상에서는 same-origin 프록시로 자동 해결** — 별도 조치 불필요. 구버전이면 ZIP 을 1.4.0 으로 재배포하세요 |
| LAN 모드에서 같은 PC 로 들어갔는데 로그인 후 빈 화면 | `localhost` ↔ `<host>` 쿠키 격리 | `http://<host>:29501/` 로 접속 (`start_offline.bat` 자동 오픈 URL 사용) |
| LAN 내 다른 PC 에서 접근 불가 | `--local` 로 실행했거나 방화벽 인바운드 차단 (1.0.22+ 기본은 LAN) | `--local` 없이 실행(기본 LAN, IP 자동 감지) 또는 `--allow-host=<host>` 로 고정 후, 이 PC 에서 `scripts\allow_lan_firewall.cmd` 관리자 실행 (`--remove` 로 원복) |
| `start_offline.bat` 가 브라우저를 안 엶 | frontend 빌드 미완료 / `.next` 누락 | `setup_offline.bat` 재실행 (`npm run build` 까지) |
| `_database/newsletter` 에 파일 추가했는데 목록에 안 보임 | 페이지를 새로고침하지 않음 (공개 읽기 시 자동 동기화됨) | `/newsletters` 새로고침으로 자동 반영. 즉시 강제는 관리자 페이지 **Import / Sync** |

### FAQ

**Q. 폐쇄망 PC 에서 새 wheel / npm 패키지가 필요해지면?**
A. 온라인 PC 에서 의존성을 추가하고 `offline_package.bat` 을 다시 실행해 ZIP 을 새로 만들어 옮기세요. `pip install --no-index --find-links` 가 항상 동봉된 wheelhouse 만 참조합니다.

**Q. 동일 PC 에 이미 설치되어 있는데 다시 `setup_offline.bat` 을 돌려도 되는가?**
A. 재설치·의존성 갱신 목적으로는 가능합니다. 환경 파일의 `JWT_SECRET_KEY` 와 `ADMIN_PASSWORD` 가 다시 생성되고 기존 값은 `.bak` 으로 백업되며, DB 는 `ensure_db_state.py` 분기로 보존됩니다. 다만 **자격 증명 노출 사고 대응으로 사용하면 안 됩니다**. 기존 DB 전체 사용자와 live session을 함께 회전하려면 서비스를 중지하고 [`scripts\rotate_aeroone_credentials.ps1`](../scripts/rotate_aeroone_credentials.ps1)을 실행합니다.

**Q. SQLite 대신 PostgreSQL 을 쓸 수 있나?**
A. `backend\.env` 의 `DATABASE_URL` 을 PostgreSQL 연결 문자열로 바꾸고 alembic 을 다시 돌리세요. SQLAlchemy 추상화로 작성되어 있어 마이그레이션만 통과하면 동작합니다. 폐쇄망이면 PostgreSQL 도 별도 오프라인 인스톨러 필요.

**Q. `dist\offline-package-*` 가 누적되는데?**
A. 운영 PC 에서는 ZIP 만 받기 때문에 누적되지 않습니다. 온라인 PC 의 `dist\` 는 수동 정리.

---

## 13. 테스트 인벤토리

> 아래 개별 파일 건수와 합계는 phase-26 당시의 역사 스냅샷입니다. 최신 릴리스의 권위 있는 검증 기준은 1.13.0에서 통과한 backend **570** / frontend **397 (73 files)** 전체 제품 게이트와, 동일 product tree의 1.13.1에서 추가 통과한 backend **88** / frontend **10** 직접 영향 테스트입니다.

| 파일 | 건수 | 검증 대상 |
|---|---|---|
| `backend/tests/unit/test_config.py` | 10 | `closed_network` / `production` / `development` / `test` 모드 정책, `secure_cookies` 분기 |
| `backend/tests/unit/test_ensure_db_state.py` | 7 | 종료 코드 0/1/2/3 + 부모 디렉토리 자동 생성 |
| `backend/tests/unit/shared/test_windows_batch_scripts.py` | 31 | setup.bat / start.bat / start_offline.bat / run_all.bat / offline_package.bat dry-run·실행·LAN·Open Notebook readiness·패키징 제외 목록 |
| `backend/tests/unit/shared/test_windows_frontend_cmd_scripts.py` | 2 | `start_frontend_dev.cmd`, `start_frontend_offline.cmd` 본문 가드 |
| `backend/tests/integration/test_ai_api.py` | 9 | AeroAI status/chat, FTS degrade, Ollama 빈 응답 재시도·502/503 구분 |
| `backend/tests/integration/test_admin_operations_api.py` | 11 | 관리자 대시보드, RBAC 금지, self-lockout 방지, 자산 점검, 백업, 감사 로그 redaction |
| `backend/tests/{unit,integration}/test_credential_rotation*.py` + DPAPI zeroization | 79 | 전체 자격·세션 회전, service/listener preflight, 연속 writer lock, production provenance·ACL·hardlink, WAL recovery, strict journal/manifest, actual crash 재개, 독립 백업 복원→archive→신규 회전, old 401/new 200, WPF ValidateOnly |
| 그 외 backend unit / integration | 126 | 인증 API, 뉴스레터 public/admin/imports API, 문서/컬렉션/보고서/read-tracking/render, seed 등 |
| **backend 합계 (phase-26 스냅샷)** | **347** | 당시 `pytest tests` 전체 통과 |
| **frontend 합계 (phase-26 스냅샷)** | **313 / 66 files** | 당시 `npm test` 전체 통과 |

회귀 발생 시 §15 단계 보고서 4종(특히 phase-6, phase-7, phase-9)의 "구현 후 검증 결과" 섹션과 비교.

---

## 14. AI 에이전트 사용 지침

AI 에이전트가 본 저장소를 다룰 때 우선 참조해야 할 위치:

1. **현재 정합 상태** — 본 문서 §3 (commit 해시 + 테스트 카운트)
2. **운영 모드 분기** — 본 문서 §4, `backend/app/core/config.py:14, 82-95`
3. **배치 스크립트 시그니처** — 본 문서 §6, §7 + `setup_offline.bat`, `start_offline.bat` 의 `:help` 라벨
4. **DB 분기 로직** — 본 문서 §11.3 + `backend/scripts/ensure_db_state.py` 의 모듈/함수 docstring (단계 9에서 본문에 새겨 둠)
5. **회귀 테스트 위치** — 본 문서 §13 표
6. **변경 이력 의도** — 본 문서 §3 표 + `docs/reports/INDEX.md` 및 각 `docs/reports/phase-*.md`
7. **정식 1.13.0 상태** — [`docs/reports/phase-27-v1-13-0-release-candidate.md`](reports/phase-27-v1-13-0-release-candidate.md) (병합·태그·공식 asset·검증 결과)
8. **v1.13.0 개발 상태 상세 보고서** — [`docs/reports/v1-13-0-development-status-2026-07-11.md`](reports/v1-13-0-development-status-2026-07-11.md) (전체 계획·검토 이력·변경 파일·유효/무효 테스트·잔여 작업)

### 14.1 변경을 가할 때 따라야 할 순서

1. 변경 의도를 한국어 commit 메시지 본문 형식(제목 + 본문 + Lore trailer)으로 미리 적어 둔다 (`AGENTS.md`, `CLAUDE.md` 강제 규칙).
2. 코드/배치 변경과 동시에 본 문서의 해당 섹션을 갱신한다 (가능하면 동일 commit).
3. 분기 의미가 바뀌면 다음 4자리를 동시에 동기화한다 — 본 문서, `docs/runbook/windows-offline.md`, 코드 docstring, 회귀 테스트.
4. 새 모드 / 새 옵션을 추가하면 본 문서 §4 / §6 / §7 표에 행을 추가한다.

### 14.2 위험 신호 (즉시 멈추고 사용자에게 물어보기)

- `APP_ENV` Literal 의 값이 줄어드는 변경
- `validate_runtime_security` 가 `closed_network` 또는 `production` 에서 면제로 바뀌는 변경
- `setup_offline.bat` 가 `APP_ENV=development` 로 회귀
- `ensure_db_state.py` 의 종료 코드 매핑 (0/1/2/3) 이 바뀌는 변경
- LAN 기본 바인딩이 loopback 전용으로 회귀하거나, `--local` opt-out / LAN IP 미감지 시 loopback 폴백 / `scripts\allow_lan_firewall.cmd` 의 `remoteip=LocalSubnet` 범위가 깨지는 변경
- OpenAI-호환 프로바이더가 pending/staging 중이거나 credential_unavailable 일 때 자동으로 Ollama 로 폴백하거나, 반대로 candidate 테스트가 DB/자격/journal 에 흔적을 남기는 변경(§19.3~§19.4)
- API 키가 write-only 원칙을 벗어나 DB/로그/감사/URL/프런트엔드 상태 어디든 평문으로 노출되는 변경(§19.5)

---

## 15. 참조 문서 색인

### 15.1 진실 원천 (코드)

- `backend/app/core/config.py` — `Settings`, `secure_cookies`, `validate_runtime_security`
- `backend/app/main.py` — startup 시 `validate_runtime_security` 호출
- `backend/app/modules/auth/api.py` — `set_cookie(secure=settings.secure_cookies)`
- `backend/scripts/ensure_db_state.py` — 모듈/함수 docstring 에 종료 코드 표
- `scripts/rotate_aeroone_credentials.ps1`, `scripts/view_aeroone_credentials.ps1`, `scripts/credential_rotation/*` — production 경계, service/listener preflight, DPAPI journal/recovery/bundle, strict quarantine manifest, 중단 재개, DB 복원 뒤 history archive, current-SID WPF 인계
- `backend/app/commands/credential_rotation_commands.py`, `backend/app/operations/credential_rotation_*.py`, `backend/app/operations/sqlite_recovery.py` — strict 명령 경계, 전체 사용자 회전, ledger/audit, WAL-safe recovery
- `setup_offline.bat`, `start_offline.bat`, `scripts/start_frontend_offline.cmd` — `:help` 라벨 + `:parse_args` 루프 + `:capture_host` 서브루틴
- `backend/app/modules/admin/*` — RBAC permission, same-transaction audit, `/api/v1/admin/*`, `service_modules`, backup/asset/admin search API
- `frontend/app/admin/page.tsx`, `frontend/components/admin/admin-home-console.tsx` — 관리자 홈 콘솔과 DB 기반 대시보드 모듈 운영 화면
- `backend/app/modules/ai/`, `backend/app/operations/windows_dpapi.py`, `backend/alembic/versions/20260714_0011_*.py` — OpenAI-호환 프로바이더 config/proof state, DPAPI purpose, 예약 launcher 마이그레이션(§19)
- `frontend/components/dashboard/notebook-link-card.tsx`, `frontend/components/admin/sections/admin-system-section.tsx` — 예약 런처 카드(Open Notebook/OpenWebUI), 관리자 AI 프로바이더 설정 화면(§19)

### 15.2 운영 매뉴얼

- **단일 진입점**: [`docs/INDEX.md`](INDEX.md) — 본 가이드 외 모든 문서의 wiki 색인
- [`README.md`](../README.md) — 시스템 정체성과 빠른 시작
- [`docs/runbook/windows-offline.md`](runbook/windows-offline.md) — 폐쇄망 운영 13장 전체
- [`docs/runbook/local-dev.md`](runbook/local-dev.md) — 개발자 로컬 실행
- [`docs/runbook/credential-rotation.md`](runbook/credential-rotation.md) — 자격 증명 사고 대응 회전·중단 재개·복원·보존
- [`docs/runbook/admin-auth.md`](runbook/admin-auth.md) — 관리자 인증 정책
- [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md) — 한국어 커밋·PR 규칙
- [v1.13.0 Claude Code 사전 릴리스 핸드오프](../.omo/evidence/v1-13-0/handoff-2026-07-12-claude-code.md) — PR 병합 전 구현·검증·재개 절차를 보존한 역사 기록. 현재 상태는 단계 27 보고서를 따른다.
- [`docs/reports/v1-13-0-development-status-2026-07-11.md`](reports/v1-13-0-development-status-2026-07-11.md) — Task 1~3 작업·검토와 Task 4~27/F1~F6 잔여 상태의 상세 기록
- [`docs/runbook/ai-agent-handoff-2026-07-09.md`](runbook/ai-agent-handoff-2026-07-09.md) — 1.13.0 제품 구현 전 상태를 보존한 superseded 핸드오프
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — 기여 가이드

### 15.3 단계별 변경 보고서 (의도와 합의안)

- [`docs/reports/phase-6-app-env-production.md`](reports/phase-6-app-env-production.md) — `closed_network` 모드 합의안
- [`docs/reports/phase-7-lan-mode.md`](reports/phase-7-lan-mode.md) — `--allow-host` 옵션 설계
- [`docs/reports/phase-8-offline-simulation.md`](reports/phase-8-offline-simulation.md) — 시뮬레이션 결과 + 실 PC 플레이북
- [`docs/reports/phase-9-docstring.md`](reports/phase-9-docstring.md) — `ensure_db_state.py` docstring 통합
- [`docs/reports/phase-18-closed-network-smoke-fixes.md`](reports/phase-18-closed-network-smoke-fixes.md) — 1.6.1 폐쇄망 smoke 결함 보강
- [`docs/reports/phase-21-admin-rbac-operations-console.md`](reports/phase-21-admin-rbac-operations-console.md) — 1.8.0 관리자 RBAC·운영 콘솔·DB 기반 대시보드 관리

### 15.4 단계별 PR/발자국 매핑

| 단계 | 커밋 | 단계 보고서 |
|---|---|---|
| 단계 21 (1.8.0 admin/RBAC operations console) | `1.8.0-dev` | `phase-21-admin-rbac-operations-console.md` |
| 단계 20 (1.7.1 dashboard/newsletter UX patch) | `1.7.1-dev` | `phase-20-dashboard-development-section-handoff.md` |
| 단계 19 (1.7.0 AeroAI/Viewer UX release) | `1.7.0` | `phase-19-aeroai-viewer-ux-release.md` |
| 단계 18 (1.6.2 smoke patch) | `1.6.2` | `phase-18-closed-network-smoke-fixes.md` |
| 단계 17 (viewer/editor + launcher/AI fixes) | `1.6.0-dev` | `phase-17-viewer-editor-and-launcher-ai-fixes.md` |
| 단계 16 (AI conversation/document grounding) | `1.5.0-dev` | `phase-16-ai-conversation-and-document-grounding.md` |
| 단계 14 (Ollama AI search) | `1.5.0-dev` | `phase-14-ollama-ai-search.md` |
| 단계 8/6/7/9 (폐쇄망 기반) | `d2cec35` / `f43ae04` / `7a6879e` / `2e69b4b` | `phase-8-offline-simulation.md`, `phase-6-app-env-production.md`, `phase-7-lan-mode.md`, `phase-9-docstring.md` |

---

## 16. 1.4.0 신규 기능 운영 안내

### 16.1 Document·Civil·NSA 본문 same-origin 프록시 (외부접속 해결)

1.4.0 이전에는 Document·Civil 본문을 브라우저가 `http://localhost:18437` 로 직접 호출했습니다. 외부 PC 에서 접속하면 `localhost` 가 방문자 자신의 PC 를 가리켜 **Failed to fetch** 가 발생했습니다.

1.4.0 부터 본문 요청은 Next.js 서버의 same-origin 프록시(`/api/frontend/collections/...`)를 경유합니다. 브라우저는 항상 페이지와 같은 호스트에 요청하고, Next.js 서버가 서버 측 loopback 으로 백엔드에 전달합니다.

- **별도 환경 변수·LAN 재설정 없이** 외부 PC 에서도 문서 본문이 열립니다.
- 뉴스레터 본문이 이미 동일한 same-origin 프록시 방식으로 동작하고 있었으므로, Document·Civil·NSA 도 같은 패턴으로 통일된 것입니다.

### 16.2 Civil 다중 카탈로그

`_database\civil_aircraft\` 에 HTML 파일을 여러 개 넣으면 Document 와 동일한 폴더 트리 목록 UI 로 표시됩니다.

```
_database\
  civil_aircraft\
    상용기\
      B737.html
      A320.html
    군용기\
      F15.html
```

- 하위 폴더로 분류하면 폴더 트리로 구분됩니다.
- 목록은 기본 접힌 상태로 시작하며, 상단 드롭다운 또는 "목록 펼치기" 버튼으로 열 수 있습니다.

### 16.3 NSA 탭

대시보드에 NSA 카드가 추가되었습니다. 1.10.0 부터 `/nsa` 는 비밀번호 `0000` 가림막이 아니라 서버측 접근제어를 사용합니다.

- 허용 경로: 관리자 또는 전역 `collections.nsa.read` 권한
- legacy 허용 경로: 전역 `search.nsa.read` 권한
- 리소스 허용 경로: 사용자/그룹의 `collection:nsa` ResourceGrant
- 목록·본문·검색은 백엔드가 위 조건 중 하나라도 만족할 때 제공하며, 모두 없으면 403 으로 닫힙니다.
- 구성·UI 는 Document 와 동일하지만, `_database\nsa\` 는 암호화 저장소가 아닙니다. 민감도 높은 자료는 별도 보안 분류와 파일 백업 정책을 따르십시오.

### 16.4 Ladder(사다리타기) 게임

대시보드 개발중 섹션에 Ladder 카드가 있습니다. `/games/ladder` 에서 참가자와 상품을 입력하면 랜덤 사다리로 배정 결과를 표시합니다. 순수 프론트엔드로 동작하며 백엔드 연동이 없습니다.

## 17. 1.5.0 Ollama AI·본문 검색 운영 안내

### 17.1 대시보드 AI 채팅

대시보드 개발중 섹션의 `AeroAI` 카드에서 `/ai` 로 이동하면 폐쇄망 Ollama 기본 모델(`gemma4:12b`)과 대화할 수 있습니다. 답변 생성 중에는 "응답 생성 중" 대기 표시가 나오며, pending 중에는 중복 전송을 막습니다.

브라우저는 Ollama 포트(`11434`)를 직접 호출하지 않습니다. `/api/frontend/ai/*` same-origin route 를 호출하고, FastAPI 백엔드가 `OLLAMA_BASE_URL` 로 Ollama 에 요청합니다.

### 17.2 Ollama 설정

`setup.bat` / `setup_offline.bat` 는 다음 기본값을 `backend\.env` 에 기록합니다.

```env
AI_FEATURES_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=gemma4:12b
```

Ollama 가 AeroOne 과 같은 PC 에 있으면 기본값을 그대로 둡니다. Ollama 가 폐쇄망 내 다른 PC 에 있다면 `OLLAMA_BASE_URL=http://<ollama-ip>:11434` 로 바꾼 뒤 backend 를 재시작합니다. 프런트엔드 `.env.local` 에 Ollama URL 을 넣지 마십시오.

### 17.3 HTML 본문 검색과 파일 바로가기

`/ai` 의 "HTML 본문 검색"은 `_database\document\` 와 `_database\civil_aircraft\` 의 HTML 본문을 SQLite FTS5 로 검색합니다. 검색 결과는 바로 열기 링크를 포함합니다.

| 컬렉션 | 바로가기 |
|---|---|
| Document | `/documents?path=<상대 HTML 경로>` |
| Civil | `/reports/civil-aircraft?path=<상대 HTML 경로>` |
| NSA | `/nsa?path=<상대 HTML 경로>` |

NSA 는 기존 가림막을 제거했습니다. Dashboard/global 검색에는 기본적으로 NSA 결과가 포함되지 않으며, 관리자 또는 서버측 `collections.nsa.read`/`search.nsa.read` 권한이나 `collection:nsa` ResourceGrant 중 하나를 통과한 사용자에게만 NSA 문서가 로드됩니다.

### 17.4 장애 시 동작

| 상태 | 화면 동작 |
|---|---|
| Ollama 미실행 / 연결 실패 | AI 영역에 연결 불가 안내. Document/Civil/NSA 열람은 계속 동작 |
| `gemma4:12b` 미설치 | 모델 없음 안내 |
| 응답 지연 / timeout | 대기 표시 후 오류와 재시도 가능 상태 |
| FTS5 미지원 | 검색 degraded 안내. 앱 부팅은 실패하지 않음 |
---

## 18. Open Notebook co-deploy (1.5+)

AeroOne 옆에 **Open Notebook**(NotebookLM 대안, MIT)을 **별도 프로세스 군으로 나란히(co-deploy)** 배치해 함께 운영할 수 있습니다. 코드 병합 없이 동거하며 결합점은 둘 — 대시보드 개발중 섹션의 **Notebook 카드**(→ `http://<host>:8502` 새 탭)와 **공유 Ollama 엔드포인트**(`127.0.0.1:11434`)뿐입니다. 두 스택은 DB(AeroOne SQLite vs ON SurrealDB)·세션·포트를 공유하지 않습니다.

세부 절차(vendoring·adapter 동결·모델 provisioning·동시성 예산·동기화·운영자 게이트)는 단일 진실 원천 런북 [`docs/runbook/open-notebook-airgap.md`](runbook/open-notebook-airgap.md) 에 있습니다. 본 절은 운영 요약입니다.

### 18.1 분리 번들 · 5 포트

| 스택 | 빌드 | 설치 | 기동 | 포트 |
|---|---|---|---|---|
| AeroOne | `offline_package.bat` → allow-list builder (ZIP에 runtime/vendor/workflow state 제외) | `setup_offline.bat` | `start_offline.bat` | 18437 / 29501 |
| Open Notebook | `airgap\1-online-package.bat` (자체 번들) | `2-airgap-install.bat` | `3-run.bat` | 8000 / 5055 / 8502 |

두 산출물은 **각자 빌드·반입**합니다. AeroOne ZIP 은 tracked top-level allow-list에서만 구성하며 vendored open-notebook 트리, `.gjc`/`.omo` workflow state, `.env`, DB/storage, QA artifact/scratch, source `node_modules`/`.next`, `requirements-dev.txt`를 포함하지 않습니다. clean stage에서 production tree와 wheelhouse를 다시 만들고 Task 5 pre/post verifier를 모두 통과한 경우에만 신뢰합니다.

### 18.2 공동 기동 — `scripts\run_all.bat`

같은 폐쇄망 PC 에 두 번들을 나란히 풀고 staggered 로 기동합니다 — AeroOne 먼저 → backend `:18437` health 200 확인 → 그 다음 Open Notebook → ON API `:5055/health` + Frontend `:8502` + runtime `/config` 확인 후 READY. 한쪽(Open Notebook 번들)이 없으면 명확히 알리고 AeroOne 단독으로 둡니다(폴백).

```cmd
:: 두 번들이 나란히 있을 때 (기본: ..\AeroOne-bundle)
scripts\run_all.bat
scripts\run_all.bat --on-bundle D:\AeroOne-bundle    :: 번들 경로 지정
scripts\run_all.bat --dry-run                         :: 5포트 preflight + 기동 계획만
scripts\run_all.bat --local                           :: AeroOne+Open Notebook 모두 단일 PC(loopback) 전용
scripts\stop_all.bat                                  :: 역순 종료

:: 공유 Ollama 모델 (인터넷 PC 에서 pull → blob 반입 → 폐쇄망 적재)
ollama pull gemma4:12b
ollama pull nomic-embed-text
```

Open Notebook 단독 기동도 동일합니다. `D:\AeroOne-bundle\3-run.bat` 기본은 LAN IPv4 자동 감지 + `API_URL`/`CORS_ORIGINS` 출력이며, 단일 PC 전용은 `3-run.bat --local`, 호스트 고정은 `3-run.bat --allow-host <IP>` 입니다. "Unable to Connect to API Server" 는 Ollama 모델 문제보다 먼저 API `:5055`, browser-facing `API_URL`, CORS origin 불일치를 확인해야 합니다.

### 18.3 공유 Ollama 동시성 (요약)

3 소비자(AeroAI chat + ON chat + ON embedding) 공유 — **최소 24GB RAM**, `OLLAMA_MAX_LOADED_MODELS=2` / `OLLAMA_NUM_PARALLEL=1` / `OLLAMA_KEEP_ALIVE=30m`, staggered boot, health 임계(AeroOne ≤30s / ON ≤90s). 자세한 표·degraded mode 는 런북 §3.

### 18.4 운영자 게이트 (라이브 검증)

submodule 핀 + fork 브랜치 push(OP-1), 폐쇄망 4프로세스 e2e 스모크(OP-2), 24GB 공유 Ollama 실측(OP-3) 은 물리 폐쇄망/외부 인프라가 필요한 **운영자 수행 항목**입니다. 런북 §6 의 체크리스트를 따릅니다.

### 18.5 신원·세션 비대칭 (보안 주의)

두 스택의 신원 체계는 **분리**되어 있고 보호 수준이 다릅니다 — 통합 SSO 는 명시적 후속(비범위).

| 스택 | 신원·접근 통제 | LAN 노출 시 위험 |
|---|---|---|
| AeroOne | `/admin/*` 는 `admin_session` 쿠키 게이트(관리자 인증). 공개 열람은 의도적 무인증 | 관리 기능은 쿠키로 보호 |
| Open Notebook | **자체 인증 없음** — `:8502`(및 `:5055`/`:8000`)에 도달하는 누구나 노트북·소스 열람/조작 가능 | LAN 의 모든 PC 가 무인증 도달 가능 |

완화: `scripts\allow_lan_firewall.cmd --with-notebook` 가 ON 포트(8000/5055/8502)에 `remoteip=LocalSubnet` 인바운드 규칙만 추가해 **로컬 서브넷 밖(외부망) 도달을 차단**합니다(기존 AeroOne LocalSubnet 규칙은 무변경). ON 을 LAN 에 여는 것은 무인증 노출을 동반하므로 `--with-notebook` 는 **옵트인**이며, 단일 PC 사용 시에는 방화벽 규칙 자체가 불필요합니다.

### 18.6 AeroAI vs Open Notebook — 언제 무엇을 (포지셔닝 SoT)

두 AI 표면의 역할 경계 단일 진실 원천입니다(다른 문서는 이 절을 참조, 중복 금지).

| | **AeroAI** (`/ai`, AeroOne 내장) | **Open Notebook** (`:8502`, 별도 앱) |
|---|---|---|
| 쓰임새 | 사내 폐쇄망 문서를 **근거로 답하는** RAG 챗(인용·근거연결) | 소스 수집·정리·요약, 노트북 구성, 벡터 검색, (옵션)팟캐스트 |
| 데이터 | AeroOne SQLite + collections(Document/Civil/NSA) | 자체 SurrealDB(노트북·업로드·벡터) |
| 신원 | AeroOne 세션(공개 열람 무인증, 관리자 쿠키) | 자체 무인증(§18.5) |
| 공유 | Ollama `gemma4:12b` chat | Ollama `gemma4:12b` chat + `nomic-embed-text` embedding |
| 선택 기준 | "사내 문서에 근거한 빠른 질의응답" | "여러 소스를 모아 정리·벡터 탐색·산출물 생성" |

요약 — **AeroAI = 근거 기반 질의응답, Open Notebook = 소스 정리·지식 워크스페이스.** 둘은 같은 Ollama 를 공유하지만 DB·신원·포트는 분리됩니다.

## 19. OpenAI-호환 AI 프로바이더 + 예약 대시보드 런처 (1.14+)

v1.14.0 은 두 가지를 추가합니다 — (1) `service_modules` 에 코드가 소유하는 **예약 런처** 2종(Open Notebook `:8502`, 신규 OpenWebUI `:8080`), (2) 관리자가 설정하는 **OpenAI-호환 AI 프로바이더**가 기존 Ollama 와 나란히(병행) 존재합니다. 둘 다 기존 폐쇄망 경계(같은 LAN, HTTP/HTTPS 정책, DPAPI 자격 보관)를 그대로 따릅니다.

### 19.1 예약 대시보드 런처 — Open Notebook / OpenWebUI

`service_modules.launcher_kind` 가 `none|open_notebook|open_webui` 인 예약 행은 관리자 콘솔에서도 href 를 직접 입력할 수 없습니다. 프런트엔드가 **현재 브라우저가 접속한 host** 를 그대로 재사용해 포트만 붙여 새 탭으로 엽니다.

| 카드 | 포트 | 노출 대상 | 비고 |
|---|---|---|---|
| Open Notebook | `:8502` | 로그인 여부와 무관하게 공개 (기존 동작, 변경 없음) | §18 참고 |
| OpenWebUI (신규) | `:8080` | **활성 로그인 admin + user 역할 모두** (`dashboard.openwebui.launch` 권한). anonymous·pending·세션 없음은 카드 자체가 보이지 않음 | 아래 §19.1.1 |

두 카드 모두 **링크만** 제공합니다. AeroOne 은 OpenWebUI 의 기동·헬스체크·SSO·프록시를 전혀 수행하지 않습니다 — 서비스는 완전히 별도로 기동·인증됩니다(로그인 화면이 다르고, AeroOne 세션과 무관). 링크를 눌러도 이동 외의 어떤 부수효과도 없습니다.

#### 19.1.1 OpenWebUI 를 별도 기동해야 하는 이유

OpenWebUI 는 AeroOne/Open Notebook 과 마찬가지로 **자체 프로세스**로 폐쇄망 PC(또는 같은 LAN 의 다른 PC)에서 기동됩니다. 운영자는 OpenWebUI 를 자체 설치 절차(공식 배포본 또는 사내 승인된 방식)로 준비하고, 대시보드 카드가 가리키는 것과 동일한 host 의 `:8080` 에 서비스가 응답하는지 별도로 확인해야 합니다. AeroOne 쪽에서는 포트가 비어 있어도 카드가 그대로 노출되며(권한만 확인), 클릭 시 대상이 응답하지 않으면 일반적인 "연결할 수 없음" 브라우저 오류가 뜰 뿐입니다 — 이는 AeroOne 장애가 아니라 OpenWebUI 미기동입니다.

### 19.2 관리자 AI 프로바이더 설정 — Ollama 병행

`/admin` 콘솔의 시스템 탭에 **AI 프로바이더** 섹션이 추가됩니다. 두 프로바이더 종류(`ollama`, `openai_compatible`) 는 **동시에 존재**할 수 있지만 실제 채팅에 쓰이는 것은 그 순간 **선택된(selected) 한 종류**뿐입니다. Ollama 는 v1.13 이전과 동일하게 계속 동작하며, 이 화면이 추가되었다고 기존 AeroAI(`/ai`) 동작이 바뀌지 않습니다.

설정 화면에서 입력하는 값:

| 항목 | 의미 |
|---|---|
| Base URL | OpenAI 호환 엔드포인트의 절대 URL(예: `https://<사내-게이트웨이-호스트>:<포트>`). 실제 운영 URL 은 사내 보안팀이 승인한 값만 사용하고, 본 문서/커밋/이슈에 실제 값을 남기지 않습니다 |
| Model | 사용할 모델 식별자 |
| API Key | 프로바이더가 요구하는 API 키. **입력만 가능(write-only)** — 저장 후에는 화면 어디에서도 평문이 다시 보이지 않고 마스킹된 자격 유무만 표시됩니다 |

### 19.3 후보(candidate) 테스트 vs 영속(persisted) 테스트 vs Activate

저장 절차는 3단계로 나뉘며, **어느 단계도 건너뛸 수 없습니다.**

1. **후보 테스트** — 화면에 입력한 값(아직 저장 전)으로 즉시 연결을 시험합니다. 이 테스트는 DB 에 아무 것도 남기지 않으며(설정/자격/상태 모두 무변화), 감사 로그에는 결과 카테고리와 시각만 결과-only 로 1건 남습니다. 후보 테스트가 실패해도 이전에 저장된 프로바이더 설정에는 영향이 없습니다.
2. **저장(Save)** — 후보 값을 실제로 저장하면 새 세대(generation)가 "대기(pending)" 상태로 기록되고 DPAPI 에 키가 암호화됩니다. 이 시점에는 아직 채팅에 쓰이지 않습니다.
3. **영속 테스트** — 방금 저장한 대기 중 설정을 대상으로 다시 테스트합니다. 이번에는 결과가 DB 에 **영속 증거(safe proof)** 로 남고, 성공(`ok`) 이어야만 다음 단계인 **Activate** 버튼이 활성화됩니다.
4. **Activate** — 영속 테스트 결과가 `ok` 인 정확히 그 세대만 활성(active) 상태로 전환할 수 있습니다. 세부 값을 바꾸거나 재시도 없이 오래된 증거로 activate 를 누르는 것은 거부됩니다.

### 19.4 선택(Selection)과 유지보수 중 동작 — 자동 폴백 없음

Ollama ↔ OpenAI-호환 전환은 화면에서 **명시적으로 선택**해야만 바뀝니다. 다음 상황에서 AeroOne 은 **절대 자동으로 다른 프로바이더로 넘어가지 않습니다.**

- 선택된 프로바이더가 OpenAI-호환인데 관리자가 자격을 교체(rotate)하거나 새 후보를 저장 중이면, 그 사이 채팅 요청은 "현재 유지보수 중이라 사용할 수 없음" 으로 명확히 실패합니다. Ollama 로 조용히 넘어가지 않습니다.
- 선택을 Ollama 로 되돌리는 것은 언제나 가능한 **명시적 롤백 경로**입니다.
- 선택을 OpenAI-호환으로 바꾸려면 해당 세대가 활성(active) 상태여야 하며, 채팅 소비 권한(`ai.use`)이 있는 로그인 사용자만 실제로 사용할 수 있습니다.

### 19.5 API 키 저장 — write-only, Windows DPAPI

API 키는 데이터베이스, 백업, 감사 로그, 오프라인 패키지, 프런트엔드 상태/번들, 이 문서를 포함한 어떤 문서에도 평문으로 남지 않습니다. 저장 즉시 Windows DPAPI(CurrentUser, 지정된 비로밍 backend 서비스 계정)로 암호화되어 `%ProgramData%\AeroOne\provider-credentials\<backend-service-SID>\` 아래에 세대별 파일로만 존재합니다. DB 에는 자격이 있다는 사실과 세대/바인딩 식별자만 남고 키 자체나 암호문은 저장되지 않습니다.

### 19.6 등록(enrollment) 경로와 egress 정책

Base URL/모델/API 키를 저장(등록)하는 요청은 **신뢰할 수 있는 HTTPS 경로 또는 이 PC 의 loopback** 에서 온 것만 허용합니다. 폐쇄망 LAN 을 통한 평문 HTTP 원격 등록은 거부됩니다 — 키가 LAN 평문으로 노출될 수 있기 때문입니다. 실제 채팅/테스트 트래픽 또한 전용 egress 경로만 사용하며, 이 경로는 리다이렉트를 따라가지 않고, 프록시를 쓰지 않으며, 사내 승인된 엔드포인트 정책을 통과한 뒤에만 Authorization 헤더를 최초 요청 대상에 붙입니다. 정책을 벗어난 목적지, 알 수 없는 DNS 응답, TLS 실패는 모두 안전하게 차단됩니다.

### 19.7 DPAPI 신원 / 재진입(re-entry)

자격은 **이 PC 의 지정된 Windows 서비스 계정(SID)** 에 묶여 있습니다. 다음 경우에는 자동 복구가 아니라 **명시적 재등록(re-entry)** 이 필요합니다 — 화면에는 `credential_unavailable` 상태로 표시됩니다.

- 다른 PC 로 복원했거나, 같은 PC 라도 서비스 계정 SID 가 바뀐 경우
- DPAPI 저장소 파일이 손상되었거나 예상 바인딩과 일치하지 않는 경우

재진입은 관리자 화면에서 Base URL/모델/API 키를 다시 입력하고 위 §19.3 저장→영속 테스트→Activate 절차를 새로 밟는 것으로 완료됩니다. 재진입 중에도 선택이 Ollama 였다면 Ollama 는 계속 그대로 동작합니다.

### 19.8 백업 / 오프라인 패키지 제외

`storage\admin_backups\` 백업과 `offline_package.bat` ZIP 은 어느 쪽도 DPAPI 암호문·journal·`%ProgramData%\AeroOne\provider-credentials\` 루트를 포함하지 않습니다. 같은 PC 복원은 §19.7 조건(동일 서비스 SID)이 맞으면 자격이 그대로 유지되고, 다른 PC/신원 복원은 재진입이 필요합니다. 이는 §10(백업·복원)·§11.5.1(자격 증명 사고 대응 회전) 의 기존 원칙과 동일한 결을 따릅니다.

### 19.9 안전한 트러블슈팅 — 테스트 결과 카테고리

후보/영속 테스트는 항상 다음 안전한 카테고리 중 하나만 반환합니다. 원문 에러·URL·응답 본문은 노출되지 않습니다.

| 결과 | 의미 | 조치 |
|---|---|---|
| `ok` | 정상 — 모델까지 확인됨 | activate 진행 가능 |
| `model_missing` | 엔드포인트는 응답하지만 지정한 모델이 없음 | 모델명 재확인 |
| `auth_failed` | 인증 실패(401/403) | API 키 재확인 |
| `policy_blocked` | 사내 엔드포인트 정책(허용 목록) 위반 또는 리다이렉트 응답 | Base URL/목적지가 승인 목록에 있는지 보안팀에 확인 |
| `unreachable` | DNS/연결/타임아웃 실패 | 네트워크 경로·방화벽 확인 |
| `tls_failed` | TLS 핸드셰이크/인증서 실패 | 인증서/HTTPS 설정 확인 |
| `invalid_response` | 형식이 예상과 다른 응답(비JSON, 과대 응답 등) | 엔드포인트가 실제 OpenAI 호환 사양을 따르는지 확인 |
| `credential_unavailable` | DPAPI 자격을 이 PC/신원에서 열 수 없음 | §19.7 재진입 절차 수행 |

각 카테고리는 감사 로그와 관리자 화면에도 동일하게 나타나며, 원인 파악을 위해 로그 파일이나 DB 를 직접 열어 볼 필요가 없도록 설계되어 있습니다.

---

## 부록 — 빠른 명령 모음

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
