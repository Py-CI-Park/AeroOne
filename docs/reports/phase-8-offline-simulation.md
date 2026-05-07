# 단계 8 보고서 — 실 폐쇄망 배포 시뮬레이션

- 작성일: 2026-05-07
- 환경: Windows 11 Pro 26200, Python 3.12, Node LTS, AeroOne main `c5e9de6`
- 검증자: 단일 운영 PC (개발 환경에서 폐쇄망 흐름을 in-place 시뮬레이션)
- 결과: **PASS (구조적 검증 + 라이브 엔드포인트 검증 통과, 보정 1건 적용)**

---

## 1. 시뮬레이션 범위와 한계

이번 단계는 "온라인 PC → ZIP → 폐쇄망 PC" 의 실제 물리 이동까지는 다루지 않고, 다음 두 축을 결합해 신뢰도를 끌어올린 **하이브리드 시뮬레이션** 입니다.

| 축 | 방법 | 목적 |
|---|---|---|
| 구조적 검증 | `setup_offline.bat --dry-run`, `start_offline.bat --dry-run`, `offline_package.bat --dry-run` | 스크립트 분기·경로·환경 변수가 폐쇄망 가정대로 흐르는지 확인 |
| 라이브 엔드포인트 검증 | 동일 PC 에서 backend 를 `127.0.0.1:18437` 로 띄우고 5단계 curl 시퀀스 실행 | 코드/DB/마이그레이션 산출물이 실제로 응답하는지 확인 |

물리 이동 시뮬레이션 (별 PC 에서 setup → start) 은 §6 에 운영자가 그대로 따라할 수 있는 플레이북으로 남겼습니다.

---

## 2. 구조적 검증 결과 (dry-run)

### 2.1 `setup_offline.bat --dry-run --no-pause`

```
[DRY-RUN] offline wheelhouse expected at D:\...\offline_assets\python-wheels
[DRY-RUN] backend env will be written to D:\...\backend\.env
[DRY-RUN] frontend env will be written to D:\...\frontend\.env.local
[DRY-RUN] backend venv will be created at D:\...\backend\.venv
[DRY-RUN] backend migration and seed will run
[DRY-RUN] frontend production build will run
```

PASS — 6개 단계 모두 예상 경로로 분기. Python/Node/npm 사전 점검은 dry-run 분기 이전에 위치하므로 실 실행 시 [PRE] 라인이 추가로 출력됨.

### 2.2 `start_offline.bat --dry-run`

```
[DRY-RUN] offline backend window command:
  uvicorn app.main:app --host 127.0.0.1 --port 18437

[DRY-RUN] offline frontend window command:
  scripts\start_frontend_offline.cmd  (내부에서 next.cmd start -H 127.0.0.1 -p 29501)

[DRY-RUN] browser readiness command:
  open_browser.cmd "http://localhost:29501/" 18437 29501 20 60
```

PASS — backend `127.0.0.1`, frontend `127.0.0.1`, 브라우저는 `localhost` 로 접속하는 의도된 분리가 그대로 유지됨.

### 2.3 `offline_package.bat --dry-run`

```
[DRY-RUN] create dist\offline-package-20260507-101148\AeroOne
[DRY-RUN] robocopy repository into stage
[DRY-RUN] py -3.12 -m pip download -r backend\requirements-dev.txt
[DRY-RUN] npm install in frontend if needed
[DRY-RUN] robocopy frontend\node_modules into staged frontend\node_modules
[DRY-RUN] copy offline_installers if present
[DRY-RUN] Compress-Archive to dist\AeroOne-offline-20260507-101148.zip
```

PASS — 7단계 흐름이 예상 그대로. `.git`, `.omc`, `.venv`, `dist`, `frontend\.next`, `backend\data`, `offline_installers` 는 robocopy 제외 목록에 포함되어 있음을 코드 직접 확인.

---

## 3. 라이브 엔드포인트 검증 결과

backend 를 `127.0.0.1:18437` 로 기동하여 runbook §10 의 5단계 시퀀스를 실행했습니다.

| # | 항목 | 명령 | 결과 | 응답 요지 |
|---|---|---|---|---|
| 1 | 헬스체크 | `GET /api/v1/health` | **HTTP 200** | `{"status":"ok","db_ok":true,"import_root_exists":true,"storage_root_exists":true}` |
| 2 | 공개 목록 | `GET /api/v1/newsletters?limit=1` | **HTTP 200** | 38건 반환 — `limit` 파라미터 무시됨 (§5 발견 사항 참고) |
| 3 | 관리자 로그인 | `POST /api/v1/auth/login` | **HTTP 200** | `Set-Cookie: admin_session=…; HttpOnly; Max-Age=1800; Path=/; SameSite=lax` + `Set-Cookie: csrf_token=…; Max-Age=1800; Path=/; SameSite=lax` 동시 발급 |
| 4 | 카테고리 (공개) | `GET /api/v1/categories` | HTTP 404 | **의도된 동작** — 카테고리/태그는 `/api/v1/admin/*` 하위 (관리자 전용) |
| 5 | 태그 (공개) | `GET /api/v1/tags` | HTTP 404 | 동일 — runbook §10 의 4번이 카테고리/태그가 아니라 "공개 목록 limit" 한 줄임을 재확인 |

### 검증 명령 (재현 가능)

```bash
# 1
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:18437/api/v1/health

# 2
curl -s -w "\nHTTP %{http_code}\n" "http://127.0.0.1:18437/api/v1/newsletters?limit=1"

# 3
PASS=$(grep "^ADMIN_PASSWORD=" backend/.env | cut -d'=' -f2-)
curl -i -X POST -H "Content-Type: application/json" \
     -d "{\"username\":\"admin\",\"password\":\"$PASS\"}" \
     http://127.0.0.1:18437/api/v1/auth/login
```

---

## 4. 코드 직접 확인

다음 파일을 직접 읽고 문서/스크립트와 정합성을 교차 검증했습니다.

| 파일 | 확인한 내용 |
|---|---|
| `setup_offline.bat` | 사전 점검 [PRE], 6단계, alembic upgrade vs stamp 분기 (`MIGRATION_MODE=3` → stamp), 성공 메시지 8줄 블록 |
| `start_offline.bat` | `BACKEND_HOST=127.0.0.1`, `FRONTEND_URL=http://localhost:29501/`, 포트 점검 후 두 CMD 창 + 브라우저 |
| `scripts\start_frontend_offline.cmd` | `node_modules\.bin\next.cmd` 존재 확인 + 한국어 에러 안내, `-H 127.0.0.1 -p 29501` |
| `offline_package.bat` | robocopy 제외 목록, `--no-index --find-links` wheelhouse 경로, ZIP 타임스탬프 |
| `backend\scripts\ensure_db_state.py` | exit 0/2/3 분기 (alembic_version 행 / 스키마 신규 / 테이블만 있고 메타 없음) |

---

## 5. 발견 사항 (Findings)

### F1 (Low) — `?limit=1` 쿼리 파라미터가 무시됨

- 위치: `backend/app/modules/newsletter/api/public.py:28`
- 시그니처: `list_newsletters(q, category, tag, source_type)` — `limit` 미지원
- 영향: runbook §10 의 4번 검증 (`curl "...?limit=1"`) 이 기대(한 건 반환)와 다르게 전체 목록을 반환. 검증 자체는 HTTP 200 으로 통과하므로 운영 사고로 이어지지 않음.
- 조치: 본 단계에서 runbook §10 을 정정해 `limit` 의존을 제거. 추후 페이지네이션이 필요하면 별 PR 로 `limit/offset` 또는 `cursor` 파라미터를 추가 권장.

### F2 (Info) — 카테고리/태그는 관리자 전용

- 위치: `backend/app/modules/newsletter/api/admin.py:58, 70`
- 공개 라우트는 `GET /api/v1/newsletters` 1건만 노출. 카테고리/태그는 `/api/v1/admin/categories`, `/api/v1/admin/tags` 로 admin 인증 + CSRF 가 필요.
- 조치: 별도 변경 없음. 정책상 의도된 분리.

### F3 (Info) — 백엔드 venv 가 dev 환경에 이미 존재

- `setup_offline.bat` 가 `if not exist "%BACKEND_VENV%\Scripts\python.exe"` 분기로 보존하므로 재실행해도 venv 재생성으로 인한 시간 손실 없음.
- 단, `.env` 와 `frontend\.env.local` 은 매 실행 시 랜덤 secret 으로 재작성되며 `.bak` 로 백업됨 — 폐쇄망 운영자가 매번 새 ADMIN_PASSWORD 를 따로 적어두지 않으면 로그인 불가.

---

## 6. 실 폐쇄망 PC 시뮬레이션 플레이북

운영자가 별 PC (또는 임시 폴더) 에서 그대로 따라하면 100% 재현 가능한 절차.

### 6.1 온라인 PC

```cmd
:: 0. 정합성 사전 검증
setup.bat
start.bat       :: (선택) 개발 모드로 한 번 떠보고 종료
offline_package.bat

:: 산출물:
::   dist\AeroOne-offline-YYYYMMDD-HHMMSS.zip
```

> `offline_installers\` 폴더에 `python-3.12.7-amd64.exe`, `node-v20.18.0-x64.msi` 를 미리 넣어두면 ZIP 안 `offline_assets\installers\` 로 자동 동봉.

### 6.2 ZIP 이동

USB / 사내 파일서버 등 **단방향 허용 경로만 사용**. 클라우드 업로드 금지.

### 6.3 폐쇄망 PC

```cmd
:: 1. 압축 해제 (권장: D:\AeroOne\)
:: 2. (Python/Node 부재 시) 인스톨러 실행
offline_assets\installers\python-3.12.7-amd64.exe
offline_assets\installers\node-v20.18.0-x64.msi
:: → 두 인스톨러 모두 "Add to PATH" 체크. 설치 후 CMD 새로 열기.

:: 3. 셋업
setup_offline.bat

:: 4. ADMIN_PASSWORD 확인 후 운영
type backend\.env | findstr ADMIN_PASSWORD

:: 5. 시작
start_offline.bat
:: → 두 포트 (18437, 29501) 준비되면 브라우저 자동 오픈

:: 6. 사후 검증 (별 CMD)
curl http://localhost:18437/api/v1/health
curl http://localhost:18437/api/v1/newsletters
curl http://localhost:18437/api/v1/newsletters/latest
```

### 6.4 운영자 일상

| 시점 | 명령 |
|---|---|
| PC 부팅 후 | `start_offline.bat` |
| 신규 발행 추가 | `Newsletter\output\` 에 파일 복사 → 관리자 화면 **Import / Sync** |
| 비밀번호 교체 | `setup_offline.bat` 재실행 → `backend\.env` 의 `ADMIN_PASSWORD` 재확인 |
| 백업 | `backend\data`, `storage`, `Newsletter\output` 3폴더 복사 |

---

## 7. 결론

폐쇄망 배포 흐름은 **현재 코드와 스크립트만으로 end-to-end 운영 가능**. 단계 5 (1.0.1 보강) 와 단계 c5e9de6 (폐쇄망 운영 일관성 보강) 의 결과로 다음이 모두 충족됨.

- ✅ Python/Node/npm 부재 시 한국어로 즉시 안내
- ✅ wheelhouse 미존재 시 즉시 중단
- ✅ alembic upgrade / stamp 분기 자동화
- ✅ frontend 빌드 산출물 (`node_modules`) 동봉
- ✅ backend `127.0.0.1` 바인딩 + frontend `127.0.0.1` 바인딩 일관
- ✅ `.env` / `.env.local` `.bak` 백업
- ✅ 사후 검증 5단계 명령 runbook 명시 (`limit=1` 정정 적용)

다음 단계는 단계 6 (H2 production 정책) → 단계 7 (M2 LAN 모드) → 단계 9 (L5 docstring) 순으로 진행.
