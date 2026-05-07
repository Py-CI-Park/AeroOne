# AeroOne 폐쇄망 배포·운영 종합 가이드

이 문서는 **사람 운영자와 AI 에이전트가 동일하게 참조할 수 있는 단일 진실 원천(single source of truth)** 입니다. 폐쇄망 배포의 모든 흐름·검증·운영·문제 해결을 한 자리에 모았습니다. 더 깊은 세부는 §13의 참조 문서로 분기합니다.

- 기준 commit: `2e69b4b` (`ensure_db_state.py 의 종료 코드 분기를 docstring 과 단위 테스트로 매듭짓는다`)
- 작성일: 2026-05-07
- 테스트 상태: `pytest tests` **66 passed** (실패 0)
- 라이선스: All Rights Reserved (사내 사용 전제)

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

---

## 1. 이 문서를 읽는 두 종류의 독자

| 독자 | 기대하는 정보 | 우선 봐야 할 섹션 |
|---|---|---|
| 사람 운영자 (현장 설치/운영) | 어떤 모드로 어떻게 배포·검증·운영·복구하는가 | §4, §5, §6 또는 §7, §8, §9, §10, §12 |
| AI 에이전트 (자동화/유지보수) | 코드 정합성, 명령 시그니처, 분기 의미, 회귀 테스트 위치 | §3, §4, §11, §13, §14, §15 |

---

## 2. 한 문장 요약 — 폐쇄망 사용 가능 여부

**가능합니다.** 두 가지 폐쇄망 운영 시나리오를 단일 PC(`Mode A`) 와 LAN 다중 PC(`Mode B`) 로 즉시 배포할 수 있고, 두 시나리오 모두 단계 8의 시뮬레이션과 단계 9의 단위 테스트로 회귀 차단된 상태입니다.

---

## 3. 현재 상태 스냅샷

### 3.1 최근 5개 커밋 (push 완료, `origin/main`)

| 커밋 | 단계 | 의미 |
|---|---|---|
| `2e69b4b` | 단계 9 | `ensure_db_state.py` 종료 코드 0/1/2/3 docstring + 회귀 테스트 7건 |
| `7a6879e` | 단계 7 | LAN 운영 모드 `--allow-host=<host>` 신설 (옵션 1개로 5자리 동기화) |
| `4c5e42a` | sub-step | stale 배치 테스트 9건 일괄 보정 |
| `f43ae04` | 단계 6 | `closed_network` 모드 신설 (HTTP 쿠키 + secret 강도 검증 동시 충족) |
| `d2cec35` | 단계 8 | 폐쇄망 배포 시뮬레이션 보고 + runbook §10 정정 |

### 3.2 핵심 구성 요소

| 영역 | 파일 | 역할 |
|---|---|---|
| 패키징 | `offline_package.bat` | 온라인 PC에서 wheelhouse + node_modules + 인스톨러 동봉 ZIP 생성 |
| 설치 | `setup_offline.bat` | 폐쇄망 PC에서 사전 점검 → `.env` 작성 → pip install → DB → frontend build |
| 실행 | `start_offline.bat` | backend / frontend 동시 기동 + 자동 브라우저 |
| 프런트 wrapper | `scripts/start_frontend_offline.cmd` | `next start` 호스트 분기 |
| DB 상태 점검 | `backend/scripts/ensure_db_state.py` | exit 0/1/2/3 으로 alembic upgrade vs stamp 분기 |
| 보안 정책 | `backend/app/core/config.py` | `closed_network` 모드 + `validate_runtime_security` |

### 3.3 테스트 통계

- 백엔드 전체: **66 passed**
- 단위 테스트: 단계 6 신규 10 (`test_config.py`) + 단계 7 신규 6 (`test_windows_batch_scripts.py`) + 단계 9 신규 7 (`test_ensure_db_state.py`)
- 회귀: 단계 8의 dry-run 3종 + 라이브 5단계 시퀀스 모두 통과

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
3. 온라인 PC `offline_package.bat` — `dist\AeroOne-offline-YYYYMMDD-HHMMSS.zip` 생성
4. ZIP 을 USB / 사내 파일서버 등 단방향 허용 경로로 전달
5. 폐쇄망 PC 압축 해제 — 권장 위치 `D:\AeroOne\` 또는 `C:\Programs\AeroOne\` (한글·공백 금지)
6. (Python/Node 부재 시) `offline_assets\installers\python-*.exe`, `node-*.msi` 먼저 실행
7. `setup_offline.bat` — 사전 점검 통과 후 자동 설치
8. `start_offline.bat` — 두 포트 준비 시 브라우저 자동 오픈
9. 신규 발행 시 `Newsletter\output\` 에 파일 추가 → 관리자 페이지 **Import / Sync** 클릭

---

## 6. 모드 A — 단일 PC (loopback)

```cmd
setup_offline.bat
start_offline.bat
```

| 자리 | 값 |
|---|---|
| Backend uvicorn | `127.0.0.1:18437` |
| Frontend next start | `127.0.0.1:29501` |
| 자동 오픈 URL | `http://localhost:29501/` |
| `CORS_ORIGINS` | `http://localhost:29501` |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:18437` |
| `SERVER_API_BASE_URL` | `http://localhost:18437` |

같은 PC 의 브라우저에서만 접속 가능. 외부 노출 없음, 가장 안전.

---

## 7. 모드 B — LAN 다중 PC (`--allow-host`)

옵션 1개로 5자리(backend 호스트, frontend 호스트, CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL, 자동 오픈 URL)를 동시에 LAN 모드로 전환합니다.

### 7.1 옵션 형태 두 가지

```cmd
:: 형태 1 — 옵션 인자 (CMD 가 = 토큰을 자동 분리하지만 capture_host 서브루틴이 흡수)
setup_offline.bat --allow-host=192.168.1.10
start_offline.bat --allow-host=192.168.1.10

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
| `SERVER_API_BASE_URL` | `http://localhost:18437` | `http://localhost:18437` (Next.js SSR 은 같은 PC 자기 자신을 호출하므로 loopback 유지) |

### 7.3 LAN 모드 운영 주의사항

- **자기 PC 도 반드시** `http://<host>:29501/` 로 접속. `localhost` 로 들어가면 페이지 호스트와 API 호스트가 달라 쿠키가 격리되어 로그인 실패.
- 자동 오픈 URL 을 그대로 사용하면 항상 같은 호스트로 통일됨.
- Windows 방화벽에서 `18437`, `29501` 두 포트를 LAN 외부로 차단하는 인바운드 규칙 별도 설정 권장.
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

기대 출력 예: `66 passed in <시간>`. 실패가 1건이라도 나오면 §15의 단계 보고서 4종을 거꾸로 읽어 어느 단계의 회귀인지 진단합니다.

### 8.4 단계 8 시뮬레이션 결과 (참고)

| 검증 | 결과 | 발견 사항 |
|---|---|---|
| `setup_offline.bat --dry-run` | PASS | 6단계 분기 모두 의도대로 |
| `start_offline.bat --dry-run` | PASS | backend `127.0.0.1` / frontend `127.0.0.1` 유지 |
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
| 신규 발행 추가 | `Newsletter\output\` 에 HTML/PDF 복사 → 관리자 페이지 **Import / Sync** |
| 메타데이터 수정 | 관리자 화면의 **편집** 버튼 (제목·요약·카테고리·태그·활성 여부·썸네일) |
| Markdown 신규 | 관리자 화면 우측 상단 **새 Markdown** 버튼 |
| 비밀번호 교체 | `setup_offline.bat` 재실행 → `backend\.env` 의 `ADMIN_PASSWORD` 재확인. 기존 `.env` 는 `.bak` 자동 백업 |

---

## 10. 백업·복원

### 10.1 백업 대상

| 경로 | 의미 | 권장 주기 |
|---|---|---|
| `backend\data\aeroone.db` | 메타데이터 + 사용자 + 카테고리/태그 | 매일 |
| `storage\markdown\` | 운영자가 직접 작성한 Markdown 본문 | Markdown 신규/수정 시 |
| `storage\thumbnails\` | 업로드된 썸네일 | 썸네일 업로드 시 |
| `Newsletter\output\` | 발행 원본 HTML/PDF | 신규 발행 시 |

```cmd
xcopy /Y /E /I backend\data D:\backup\AeroOne\data
xcopy /Y /E /I storage D:\backup\AeroOne\storage
xcopy /Y /E /I Newsletter\output D:\backup\AeroOne\Newsletter\output
```

### 10.2 복원

같은 PC 또는 다른 폐쇄망 PC 에 새로 압축 해제한 뒤, 위 세 경로를 그대로 덮어쓰고 `setup_offline.bat` 실행. `ensure_db_state.py` 가 기존 DB 의 alembic 메타 부재를 감지해 `alembic stamp head` 분기로 데이터 보존하며 진행합니다 (§11.3 참고).

---

## 11. 보안 기본값과 정책

### 11.1 비밀 자동 생성

`setup_offline.bat` 매 실행 시 PowerShell `RandomNumberGenerator` 로 다음 두 값을 새로 생성합니다.

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

---

## 12. 트러블슈팅과 FAQ

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| `setup_offline.bat` 사전 점검에서 `[ERROR] Python` | Python 미설치 / PATH 누락 | `offline_assets\installers\python-*.exe` 실행 → CMD 새로 열기 |
| 같은 자리에서 `[ERROR] Node.js` | Node 미설치 / PATH 누락 | `offline_assets\installers\node-*.msi` 실행 → 재시작 |
| 사전 점검 통과 후 wheelhouse 단계 실패 | wheel 파일 일부 누락 | 온라인 PC 에서 `offline_package.bat` 재실행 후 ZIP 재배포 |
| 포트 충돌 | 다른 프로세스 점유 | `netstat -ano | findstr 18437` 로 PID 확인 후 종료 |
| 페이지 로딩 후 `Failed to fetch` | 페이지 호스트 ↔ API 호스트 다름 | 주소를 동일 호스트 (`localhost` 또는 `<host>`) 로 통일 |
| LAN 모드에서 같은 PC 로 들어갔는데 로그인 후 빈 화면 | `localhost` ↔ `<host>` 쿠키 격리 | `http://<host>:29501/` 로 접속 (`start_offline.bat` 자동 오픈 URL 사용) |
| LAN 내 다른 PC 에서 접근 불가 | 기본 모드 (loopback) | `setup_offline.bat --allow-host=<host>` → `start_offline.bat --allow-host=<host>` |
| `start_offline.bat` 가 브라우저를 안 엶 | frontend 빌드 미완료 / `.next` 누락 | `setup_offline.bat` 재실행 (`npm run build` 까지) |
| `Newsletter/output` 추가했는데 목록에 안 보임 | sync 미실행 | 관리자 페이지 **Import / Sync** 또는 `setup_offline.bat` 재실행 |

### FAQ

**Q. 폐쇄망 PC 에서 새 wheel / npm 패키지가 필요해지면?**
A. 온라인 PC 에서 의존성을 추가하고 `offline_package.bat` 을 다시 실행해 ZIP 을 새로 만들어 옮기세요. `pip install --no-index --find-links` 가 항상 동봉된 wheelhouse 만 참조합니다.

**Q. 동일 PC 에 이미 설치되어 있는데 다시 `setup_offline.bat` 을 돌려도 되는가?**
A. 네. `JWT_SECRET_KEY` 와 `ADMIN_PASSWORD` 가 새 랜덤 값으로 재생성되며 기존 값은 `.bak` 으로 백업됩니다. DB 는 `ensure_db_state.py` 가 코드 0 또는 3으로 분기해 보존됩니다.

**Q. SQLite 대신 PostgreSQL 을 쓸 수 있나?**
A. `backend\.env` 의 `DATABASE_URL` 을 PostgreSQL 연결 문자열로 바꾸고 alembic 을 다시 돌리세요. SQLAlchemy 추상화로 작성되어 있어 마이그레이션만 통과하면 동작합니다. 폐쇄망이면 PostgreSQL 도 별도 오프라인 인스톨러 필요.

**Q. `dist\offline-package-*` 가 누적되는데?**
A. 운영 PC 에서는 ZIP 만 받기 때문에 누적되지 않습니다. 온라인 PC 의 `dist\` 는 수동 정리.

---

## 13. 테스트 인벤토리

| 파일 | 건수 | 검증 대상 |
|---|---|---|
| `backend/tests/unit/test_config.py` | 10 | `closed_network` / `production` / `development` / `test` 모드 정책, `secure_cookies` 분기 |
| `backend/tests/unit/test_ensure_db_state.py` | 7 | 종료 코드 0/1/2/3 + 부모 디렉토리 자동 생성 |
| `backend/tests/unit/shared/test_windows_batch_scripts.py` | 17 | setup.bat / start.bat / start_offline.bat 의 dry-run / 실행 / `--allow-host` 분기 |
| `backend/tests/unit/shared/test_windows_frontend_cmd_scripts.py` | 2 | `start_frontend_dev.cmd`, `start_frontend_offline.cmd` 본문 가드 |
| 그 외 unit / integration | 30 | 인증 API, 뉴스레터 public/admin/imports API, seed 등 |
| **합계** | **66** | `pytest tests` 전체 통과 |

회귀 발생 시 §15 단계 보고서 4종(특히 phase-6, phase-7, phase-9)의 "구현 후 검증 결과" 섹션과 비교.

---

## 14. AI 에이전트 사용 지침

AI 에이전트가 본 저장소를 다룰 때 우선 참조해야 할 위치:

1. **현재 정합 상태** — 본 문서 §3 (commit 해시 + 테스트 카운트)
2. **운영 모드 분기** — 본 문서 §4, `backend/app/core/config.py:14, 82-95`
3. **배치 스크립트 시그니처** — 본 문서 §6, §7 + `setup_offline.bat`, `start_offline.bat` 의 `:help` 라벨
4. **DB 분기 로직** — 본 문서 §11.3 + `backend/scripts/ensure_db_state.py` 의 모듈/함수 docstring (단계 9에서 본문에 새겨 둠)
5. **회귀 테스트 위치** — 본 문서 §13 표
6. **변경 이력 의도** — 본 문서 §3 표 + `docs/reports/phase-{6,7,8,9}-*.md`

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
- LAN 모드에서 `0.0.0.0` 바인딩이 무조건적으로 켜지는 변경 (옵션 미지정 시 회귀 0 원칙 위반)

---

## 15. 참조 문서 색인

### 15.1 진실 원천 (코드)

- `backend/app/core/config.py` — `Settings`, `secure_cookies`, `validate_runtime_security`
- `backend/app/main.py` — startup 시 `validate_runtime_security` 호출
- `backend/app/modules/auth/api.py` — `set_cookie(secure=settings.secure_cookies)`
- `backend/scripts/ensure_db_state.py` — 모듈/함수 docstring 에 종료 코드 표
- `setup_offline.bat`, `start_offline.bat`, `scripts/start_frontend_offline.cmd` — `:help` 라벨 + `:parse_args` 루프 + `:capture_host` 서브루틴

### 15.2 운영 매뉴얼

- [`README.md`](../README.md) — 시스템 정체성과 빠른 시작
- [`docs/runbook/windows-offline.md`](runbook/windows-offline.md) — 폐쇄망 운영 13장 전체
- [`docs/runbook/local-dev.md`](runbook/local-dev.md) — 개발자 로컬 실행
- [`docs/runbook/admin-auth.md`](runbook/admin-auth.md) — 관리자 인증 정책
- [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md) — 한국어 커밋·PR 규칙
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — 기여 가이드

### 15.3 단계별 변경 보고서 (의도와 합의안)

- [`docs/reports/phase-6-app-env-production.md`](reports/phase-6-app-env-production.md) — `closed_network` 모드 합의안
- [`docs/reports/phase-7-lan-mode.md`](reports/phase-7-lan-mode.md) — `--allow-host` 옵션 설계
- [`docs/reports/phase-8-offline-simulation.md`](reports/phase-8-offline-simulation.md) — 시뮬레이션 결과 + 실 PC 플레이북
- [`docs/reports/phase-9-docstring.md`](reports/phase-9-docstring.md) — `ensure_db_state.py` docstring 통합

### 15.4 단계별 PR/발자국 매핑

| 단계 | 커밋 | 단계 보고서 |
|---|---|---|
| 단계 8 (시뮬레이션) | `d2cec35` | `phase-8-offline-simulation.md` |
| 단계 6 (closed_network) | `f43ae04` | `phase-6-app-env-production.md` |
| 단계 7 (--allow-host) | `7a6879e` | `phase-7-lan-mode.md` |
| 단계 9 (docstring) | `2e69b4b` | `phase-9-docstring.md` |

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
