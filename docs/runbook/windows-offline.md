# Windows / 폐쇄망 운영 런북

이 문서는 AeroOne 을 인터넷이 차단된 사내 Windows PC에 배포하고 운영하는 전 과정을 다룹니다. README 의 [폐쇄망 배포 흐름](../../README.md#폐쇄망-배포-흐름) 섹션이 빠른 참고용 요약이라면, 이 문서는 실제 작업자가 각 단계를 그대로 따라할 수 있도록 풀어 적은 운영 매뉴얼입니다.

---

## 1. 배치 파일 구성

| 파일 | 위치 | 용도 |
|---|---|---|
| `setup.bat` | 온라인 PC | 개발/사전 설치 (가상환경, pip install, DB seed, npm install) |
| `start.bat` | 온라인 PC | 백엔드/프런트 동시 실행 (개발용 dev 서버) |
| `offline_package.bat` | 온라인 PC | 현재 리포 + Python wheelhouse + frontend node_modules + 동봉 인스톨러를 ZIP 으로 패키징 |
| `setup_offline.bat` | 폐쇄망 PC | Python/Node 사전 점검, `.env` 재작성, 오프라인 pip install, DB, frontend production 빌드 |
| `start_offline.bat` | 폐쇄망 PC | 운영 모드 실행 (`next start` + uvicorn, 두 서비스 모두 `127.0.0.1` 바인딩) |

각 배치 파일 모두 `--dry-run` 과 `--no-pause` 옵션을 지원합니다.

---

## 2. 권장 순서 (E2E)

```
[온라인 PC]                                      [폐쇄망 PC]
setup.bat              ─┐
start.bat (선택, 검증)  │
offline_package.bat    ─┘──→ ZIP 복사 ──→  압축 해제
                                            setup_offline.bat
                                            start_offline.bat
                                            (관리자에서 Import / Sync)
```

1. 온라인 PC 에서 `setup.bat` 으로 의존성과 DB 시드 완료
2. 필요 시 `start.bat` 으로 동작 검증
3. `offline_package.bat` 으로 ZIP 생성 (`dist\AeroOne-offline-YYYYMMDD-HHMMSS.zip`)
4. ZIP 을 USB / 사내 파일서버 등 허용된 경로로 전달
5. 폐쇄망 PC 에서 압축 해제 (권장 위치는 §4 참고)
6. `setup_offline.bat` 실행 — 사전 점검 통과 후 자동 설치 진행
7. `start_offline.bat` 실행 — 두 포트 준비 시 브라우저 자동 오픈
8. 신규 발행 시 `Newsletter\output\` 에 파일 추가 후 관리자 페이지의 Import / Sync 버튼 클릭

---

## 3. 폐쇄망 PC 사전 요건

`setup_offline.bat` 첫 단계에서 자동으로 점검하지만, 사전에 알고 있으면 설치 시간을 크게 줄일 수 있습니다.

| 항목 | 요구 사항 | 부재 시 동작 |
|---|---|---|
| Python | 3.12 (3.x 도 시도) | `[ERROR] Python (py 또는 python)을 찾을 수 없습니다.` 출력 후 즉시 중단 |
| Node.js | LTS (16+ 권장, 20+ 검증) | `[ERROR] Node.js 를 찾을 수 없습니다.` |
| npm | Node 와 함께 설치됨 | `[ERROR] npm 을 찾을 수 없습니다.` |
| PowerShell | Windows 기본 | 포트 점검·랜덤 secret 생성에 사용 |

### 인스톨러 동봉 방법

폐쇄망 PC 에 Python / Node 가 없는 경우, 온라인 PC 의 저장소 루트에 `offline_installers\` 폴더를 만들고 다음 파일을 넣어 둔 뒤 `offline_package.bat` 을 실행하세요. ZIP 안 `offline_assets\installers\` 로 복사됩니다.

| 파일 (예시) | 출처 |
|---|---|
| `python-3.12.7-amd64.exe` | https://www.python.org/downloads/windows/ |
| `node-v20.18.0-x64.msi` | https://nodejs.org/en/download |

폐쇄망 PC 에서 압축 해제 후 다음 두 파일을 먼저 실행하면 `setup_offline.bat` 사전 점검을 통과합니다.

```cmd
offline_assets\installers\python-3.12.7-amd64.exe
offline_assets\installers\node-v20.18.0-x64.msi
```

> 두 인스톨러 모두 "Add to PATH" 옵션을 체크해 설치하세요. 설치 후에는 PowerShell / CMD 창을 닫고 새로 열어야 PATH 가 갱신됩니다.

---

## 4. 권장 압축 해제 위치

다음 조건을 만족하는 경로를 권장합니다.

- 사용자 쓰기 권한이 있는 절대 경로
- 한글·공백이 포함되지 않음
- 드라이브 루트에 가까운 짧은 경로 (Windows 의 260자 path limit 회피)

권장 예시:

```
D:\AeroOne\
C:\Programs\AeroOne\
C:\Users\<유저명>\AeroOne\
```

피해야 하는 위치:

- `C:\Program Files\` / `C:\Program Files (x86)\` (관리자 권한 필요, setup 실패 가능)
- `C:\Windows\`, `C:\Users\<유저명>\Desktop\` (path limit 도달 위험, `.next` 빌드 산출물이 깊은 경로에 생성됨)
- 한글 또는 공백 포함 경로 (Python/Node 일부 도구가 비ASCII 경로를 잘못 처리할 수 있음)

---

## 5. 실행 시 동작

### 5.1 `start.bat` / `start_offline.bat` 공통

- 백엔드와 프런트 CMD 창을 각각 열고, 두 포트 (`18437`, `29501`) 가 준비되면 브라우저를 자동으로 띄웁니다.
- 두 포트 중 하나라도 이미 사용 중이면 브라우저를 열지 않고 즉시 안내 메시지를 출력한 뒤 종료합니다.
- 포트 준비 점검은 PowerShell 의 TCP 리스너 조회를 사용합니다.

### 5.2 바인딩 호스트

| 서비스 | 호스트 | 포트 |
|---|---|---|
| Backend uvicorn | `127.0.0.1` | `18437` |
| Frontend next start (offline) | `127.0.0.1` | `29501` |
| Frontend next dev (online) | Next.js 기본 | `29501` |

> 두 서비스 모두 loopback 바인딩이라 같은 PC 의 브라우저에서만 접속됩니다. LAN 내 다른 PC 에서 접근해야 한다면 §11 트러블슈팅을 참고하세요.

---

## 6. setup_offline.bat 동작 단계

```
[PRE  ] Python / Node / npm 사전 요건 점검
[1   ] backend\.env, frontend\.env.local 재작성 (랜덤 secret/admin 비밀번호)
[2   ] backend\.venv 생성 또는 재사용
[3   ] pip install --no-index --find-links offline_assets\python-wheels -r requirements-dev.txt
[4   ] backend\data\aeroone.db 점검 → alembic upgrade head 또는 stamp head
[5   ] python scripts\seed.py (관리자 / 카테고리 / 태그 / 샘플 Markdown / Newsletter import-sync)
[6   ] frontend\node_modules 존재 확인 후 npm run build (프로덕션 빌드)
[OK  ] 다음 단계 안내
```

### 6.1 alembic upgrade vs stamp

`backend\scripts\ensure_db_state.py` 의 종료 코드로 분기됩니다.

| 종료 코드 | 의미 | 다음 단계 |
|---|---|---|
| 0 | DB 와 alembic_version 정상 | `alembic upgrade head` (이미 head 면 no-op) |
| 2 | DB 가 없거나 비어 있음 | `alembic upgrade head` (스키마 신규 생성) |
| 3 | DB 에 테이블은 있지만 alembic_version 비어 있음 | `alembic stamp head` (메타데이터만 표시) |

수동 초기화가 필요하면 `backend\data\aeroone.db` 파일을 삭제한 뒤 다시 실행하세요. 코드 0, 2, 3 어느 경로든 안전하게 빈 DB 부터 다시 만듭니다.

### 6.2 seed 결과 확인

`seed complete (external sync: created=N, updated=N, deactivated=N, skipped=N, issues=N)` 라인이 보이면 `Newsletter\output\` 의 HTML/PDF 가 DB 에 인덱싱된 것입니다. `import root not found` 가 보이면 폴더가 비어 있는 상태이며, 이후 `Newsletter\output\` 에 파일을 채우고 관리자 페이지의 Import / Sync 를 실행해야 합니다.

---

## 7. 운영자 일상 작업

### 7.1 신규 발행 추가

1. 새 HTML / PDF 파일을 `Newsletter\output\` 에 복사
2. 관리자 (`http://localhost:29501/login`) 로 로그인
3. `관리자 뉴스레터 목록` 화면에서 **Import / Sync** 클릭
4. 신규 행이 `활성` 상태로 추가되었는지 확인

### 7.2 메타데이터 수정

- 제목 / 요약 / 카테고리 / 태그 / 활성 여부: `편집` 버튼
- 썸네일: 편집 화면에서 업로드
- Markdown 신규 작성: 화면 우측 상단의 `새 Markdown` 버튼

### 7.3 관리자 비밀번호 교체

`setup_offline.bat` 또는 `setup.bat` 을 다시 실행하면 새 랜덤 값으로 교체됩니다. 기존 `.env` 는 `.bak` 로 자동 백업됩니다.

```cmd
setup_offline.bat
type backend\.env | findstr ADMIN_PASSWORD
```

---

## 8. 백업 / 복원

### 8.1 백업 대상

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

### 8.2 복원

같은 PC 또는 다른 폐쇄망 PC 에 새로 압축 해제한 뒤, 위 세 경로를 그대로 덮어쓰고 `setup_offline.bat` 을 실행합니다. `ensure_db_state.py` 가 기존 DB 를 감지해 `alembic stamp head` 로 진행하므로 데이터가 손실되지 않습니다.

---

## 9. 보안 기본값

- `JWT_SECRET_KEY`, `ADMIN_PASSWORD` 는 setup 시 랜덤 생성. `change-me` 같은 기본값은 production 환경에서 거부됩니다.
- 두 서비스 모두 `127.0.0.1` 바인딩 → 동일 PC 의 브라우저에서만 접속 가능.
- 정적 파일 노출 범위는 `storage\thumbnails\` 하위로 제한.
- HTML 미리보기는 백엔드 sanitize + CSP + sandbox iframe 조합. `_debug.html` 은 import / 공개 모두에서 제외.
- 관리자 모든 mutation 과 sync 는 CSRF 토큰을 요구.

> `setup_offline.bat` 는 폐쇄망 PC 의 `APP_ENV` 을 기본 `development` 로 둡니다. HTTP-only 폐쇄망 환경에서 `secure cookie` 동작을 일시적으로 끄기 위함입니다. HTTPS 환경으로 운영하려면 `backend\.env` 의 `APP_ENV=production` 으로 바꾸고, 동시에 secure cookie 를 받을 수 있도록 리버스 프록시 / 인증서를 준비해야 합니다.

---

## 10. 사후 검증 체크리스트

설치 직후 한 번 돌려 두면 90% 의 운영 사고를 예방할 수 있습니다.

```cmd
:: 1. 사전 점검 dry-run
setup_offline.bat --dry-run

:: 2. 시작 dry-run
start_offline.bat --dry-run

:: 3. 헬스체크
curl http://localhost:18437/api/v1/health

:: 4. 공개 목록 (전체 반환 — 페이지네이션 미지원, HTTP 200 만 확인)
curl http://localhost:18437/api/v1/newsletters

:: 4-1. 단건 조회 (최신 발행 1건)
curl http://localhost:18437/api/v1/newsletters/latest

:: 5. 관리자 로그인 (admin_session + csrf_token 두 쿠키 확인)
curl -i -X POST -H "Content-Type: application/json" ^
     -d "{\"username\":\"admin\",\"password\":\"<backend\.env 의 ADMIN_PASSWORD>\"}" ^
     http://localhost:18437/api/v1/auth/login
```

> 4번 응답이 길어서 부담스러우면 PowerShell 에서 `... | ConvertFrom-Json | Select-Object -First 1` 로 한 건만 보거나, 4-1 의 `/latest` 단건 조회로 대체하세요. 카테고리·태그 라우트는 관리자 전용 (`/api/v1/admin/categories`, `/api/v1/admin/tags`) 이라 5번 로그인 후 쿠키를 첨부해야 응답을 받을 수 있습니다.

위 다섯 단계가 모두 정상이면 폐쇄망 운영 준비가 끝난 것입니다.

---

## 11. 트러블슈팅

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| `setup_offline.bat` 가 사전 점검에서 `[ERROR] Python` 출력 후 종료 | Python 미설치 또는 PATH 누락 | `offline_assets\installers\python-*.exe` 실행 후 PowerShell 재시작 |
| 같은 자리에서 `[ERROR] Node.js` | Node 미설치 또는 PATH 누락 | `offline_assets\installers\node-*.msi` 실행 후 재시작 |
| 사전 점검은 통과하지만 wheelhouse 단계에서 실패 | wheel 파일 일부 누락 (온라인 PC 에서 transitive dep 누락) | 온라인 PC 에서 `offline_package.bat --dry-run` 으로 wheelhouse 재수집 후 재패키징 |
| 포트 충돌 (`port 18437/29501 is already in use`) | 다른 프로세스가 점유 | `netstat -ano | findstr 18437` 로 PID 확인 후 종료, 또는 `.env` 의 포트 변경 (CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL 도 함께 수정) |
| 페이지 로딩 후 `Failed to fetch` | 페이지 호스트와 API 호스트가 다름 (`127.0.0.1` vs `localhost` 쿠키 격리) | 브라우저 주소를 `http://localhost:29501/...` 로 통일 |
| LAN 내 다른 PC 에서 접근 불가 | `127.0.0.1` 바인딩 | 두 서비스 모두 외부 호스트 바인딩으로 바꾸려면 `start_offline.bat` 의 backend 호스트와 `scripts\start_frontend_offline.cmd` 의 `-H` 인자, `backend\.env` 의 `CORS_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`, `SERVER_API_BASE_URL` 을 모두 동일한 외부 IP / 호스트명으로 맞춰야 합니다 |
| 관리자 화면에 `Failed to fetch` | 로그인 후 admin_session 쿠키 미적용 | 로그인 직후 페이지 새로고침. 그래도 실패하면 `backend\.env` 의 `ADMIN_SESSION_COOKIE_NAME`/`CSRF_COOKIE_NAME` 과 `frontend\.env.local` 의 `NEXT_PUBLIC_CSRF_COOKIE_NAME` 이 일치하는지 확인 |
| `start_offline.bat` 가 브라우저를 열지 않음 | frontend 빌드 미완료 또는 `.next` 누락 | `setup_offline.bat` 를 다시 실행해 `npm run build` 까지 완료 |
| `Newsletter/output` 에 파일을 넣었는데 목록에 안 보임 | sync 미실행 | 관리자 페이지의 **Import / Sync** 버튼 클릭, 또는 `setup_offline.bat` 재실행 (seed 가 sync 까지 수행) |

---

## 12. 자주 묻는 질문

- **Q. 폐쇄망 PC 에서 새 wheel 이나 npm 패키지가 필요해지면?**
  A. 온라인 PC 에서 의존성을 추가하고 `offline_package.bat` 을 다시 실행해 ZIP 을 새로 만들어 옮기세요. 폐쇄망 PC 에서는 `pip install --no-index --find-links` 가 항상 동봉된 wheelhouse 만 참조합니다.

- **Q. 동일 폐쇄망 PC 에 이미 설치되어 있는데 다시 `setup_offline.bat` 을 돌려도 되는가?**
  A. 네. `JWT_SECRET_KEY` 와 `ADMIN_PASSWORD` 가 새 랜덤 값으로 다시 생성되며 기존 값은 `.bak` 파일로 백업됩니다. DB 는 유지됩니다 (alembic stamp head 분기).

- **Q. 운영 PC 가 잠시 꺼지거나 재부팅된 뒤 다시 켜졌을 때 어떻게 띄우나?**
  A. `start_offline.bat` 한 번이면 됩니다. 데이터는 `backend\data\aeroone.db` 에 그대로 있습니다.

- **Q. dist\offline-package-* 가 누적되어 디스크를 차지합니다.**
  A. 운영 PC 에서는 어차피 ZIP 만 받기 때문에 누적되지 않습니다. 온라인 PC 의 `dist\` 폴더는 수동으로 정리해도 됩니다.

- **Q. SQLite 대신 PostgreSQL 을 쓰고 싶다.**
  A. `backend\.env` 의 `DATABASE_URL` 을 PostgreSQL 연결 문자열로 바꾸고 alembic 을 새로 돌리세요. 코드는 SQLAlchemy 추상화로 작성되어 있어 마이그레이션만 통과하면 동작합니다. 폐쇄망 환경이라면 PostgreSQL 도 별도 오프라인 인스톨러로 준비해야 합니다.

---

## 13. 관련 문서

- [README.md](../../README.md) — 시스템 정체성과 빠른 시작
- [docs/runbook/local-dev.md](local-dev.md) — 개발자 로컬 실행 가이드
- [docs/runbook/admin-auth.md](admin-auth.md) — 관리자 인증 정책
- [docs/dev_plan/20260327_newsletter_platform_mvp.md](../dev_plan/20260327_newsletter_platform_mvp.md) — MVP 개발 계획 원본
