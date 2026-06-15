<div align="center">

# AeroOne

**폐쇄망에서도 그대로 돌아가는 사내 뉴스레터·문서 열람 플랫폼**

이미 발행된 HTML / PDF / Markdown 뉴스레터를 한 곳에서 보고, ZIP 하나로 인터넷이 차단된 PC에 동일하게 배포할 수 있는 modular monolith 입니다.

![version](https://img.shields.io/badge/version-1.5.0-1f6feb)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![node](https://img.shields.io/badge/node-LTS-339933?logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-App%20Router-000000?logo=next.js&logoColor=white)
![Tests](https://img.shields.io/badge/tests-pytest%20%7C%20vitest-success)
![Use](https://img.shields.io/badge/use-internal%20deployment-lightgrey)

</div>

<table>
  <tr>
    <td align="center"><b>대시보드</b></td>
    <td align="center"><b>뉴스레터 (달력 + HTML 본문)</b></td>
    <td align="center"><b>다크 모드</b></td>
  </tr>
  <tr>
    <td><img src="docs/images/dashboard.png" alt="모듈 카드 대시보드" width="320"></td>
    <td><img src="docs/images/newsletter.png" alt="펼친 달력과 최신 이슈 HTML 본문 직접 렌더" width="320"></td>
    <td><img src="docs/images/newsletter-dark.png" alt="다크 모드 뉴스레터 리딩 뷰" width="320"></td>
  </tr>
</table>

<sub>디자인 시스템 적용 화면 (<code>[data-theme]</code> 라이트·다크, 시스템 폰트만). <code>docs/images/</code> 의 <code>dashboard.png</code> · <code>newsletter.png</code> · <code>newsletter-dark.png</code> 를 교체하면 자동 렌더링됩니다.</sub>

---

## 목차

- [왜 AeroOne 인가](#왜-aeroone-인가)
- [주요 기능](#주요-기능)
- [빠른 시작 — 온라인 Windows PC](#빠른-시작--온라인-windows-pc)
- [폐쇄망 배포 흐름](#폐쇄망-배포-흐름)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [환경 변수](#환경-변수)
- [개발자용 로컬 실행](#개발자용-로컬-실행)
- [검증](#검증)
- [보안과 운영 권장사항](#보안과-운영-권장사항)
- [문서](#문서)
- [사용 범위와 기여](#사용-범위와-기여)

---

## 왜 AeroOne 인가

- **폐쇄망 우선 설계** — 인터넷이 가능한 PC에서 ZIP 한 개를 만들어 옮기면, 폐쇄망 PC에서 같은 코드·같은 의존성·같은 시드 데이터로 그대로 동작합니다. wheelhouse, `node_modules`, 옵션 인스톨러까지 묶여 있습니다.
- **다중 포맷 통합 뷰어** — `newsletter_YYYYMMDD.html` 과 `Aerospace Daily News_YYYYMMDD.pdf` 처럼 한 이슈가 여러 자산을 가지는 현실 데이터를 그대로 다룹니다. `source_type` 에 따라 sandbox iframe / PDF delivery / Markdown render 로 분기합니다.
- **안전한 기본값** — production 환경에서는 기본 secret 과 admin 비밀번호가 거부되고, setup 시 매번 랜덤 값이 생성됩니다. 정적 노출 범위는 `storage/thumbnails` 하위로 한정하고, `_debug.html` 은 import 와 공개 목록에서 모두 제외됩니다.
- **확장 가능한 구조** — 뉴스레터 외 announcement, schedule, document publishing, admin tools 등 사내 모듈을 같은 저장소 안에서 modular monolith 로 붙일 수 있도록 설계했습니다.

---

## 주요 기능

| 영역 | 내용 |
|---|---|
| 사용자 화면 | 대시보드 모듈 카드(뉴스레터·민간항공기 보고서·문서 보관소 등), 뉴스레터 리딩 뷰(최신·선택 이슈 HTML 직접 렌더), 기본 펼친 달력으로 이슈 전환, 민간항공기 규격 카탈로그(/reports/civil-aircraft, 달력 없음), 문서 보관소(/documents, `_database/document` HTML 을 폴더 트리로 열람), `[data-theme]` 라이트·다크 테마 토글 |
| AeroAI 어시스턴트 (1.5) | 대시보드 AeroAI 섹션의 `/ai` — 사내 폐쇄망 문서(Document/Civil/NSA)를 **근거로 답하는** RAG 챗. 대화 영속화·인용(citation) 근거연결·3분할 워크스페이스·프롬프트 프리셋. backend-only Ollama(`gemma4:12b`), same-origin 프록시 |
| Open Notebook 동거 배포 (1.5) | NotebookLM 대안(MIT)을 **코드 병합 없이 나란히(co-deploy)** — 대시보드 Notebook 카드 → `:8502`. 분리 번들(airgap) + 공유 Ollama + 무인 자동 프로비저닝(모델 자동등록). 상세: [`docs/runbook/closed-network-install-manual.md`](docs/runbook/closed-network-install-manual.md) |
| 콘텐츠 분기 | HTML(sandbox iframe + sanitize + CSP), PDF(direct delivery), Markdown(서버 렌더) |
| 관리자 화면 | 로그인, 메타데이터 CRUD, 카테고리·태그 관리, 썸네일 업로드, `_database/newsletter` import / sync |
| 인증 | signed HttpOnly session cookie + SameSite=Lax + CSRF 토큰, 단일 시드 관리자 |
| 데이터 모델 | `users / categories / tags / newsletters / newsletter_tags / newsletter_assets` 로 다중 자산 페어링 |
| 운영 모드 | `development` / `test` / `closed_network` / `production` 4 모드. `closed_network` 는 HTTP 폐쇄망에서 secret 강도 검증을 강제하면서 secure cookie 는 끔 |
| 기본 LAN / loopback | 1.0.22+ 기본은 LAN(`0.0.0.0`, 이 PC 의 LAN IP 자동 감지) — backend·frontend·CORS·NEXT_PUBLIC_API·자동 오픈 URL 5자리 일괄 적용. 이 PC 전용은 `--local`, 호스트 고정은 `--allow-host=<IP>` |
| 검증 | backend pytest + httpx (162 passed), frontend Vitest + Testing Library (179 passed, 46 파일), `tsc --noEmit` exit 0, `next build` 성공, Windows 실행 스모크 |
| 배포 | Docker Compose (개발), Windows 배치 스크립트 (운영/폐쇄망) |
| 폐쇄망 오픈소스 도입 | 검증된 vendoring·airgap 번들·자동 프로비저닝 프로세스로 외부 오픈소스를 폐쇄망에 도입 — 재사용 플레이북: [`docs/closed-network-oss-adoption-process.md`](docs/closed-network-oss-adoption-process.md) |

---

## 빠른 시작 — 온라인 Windows PC

```cmd
:: 1) 초기 설치 (가상환경, 의존성, DB, 시드, frontend npm install)
setup.bat

:: 2) 백엔드/프런트 실행 + 브라우저 자동 오픈
start.bat
```

| 화면 | URL |
|---|---|
| 공개 목록 | http://localhost:29501/newsletters |
| 관리자 로그인 | http://localhost:29501/login |
| 헬스체크 | http://localhost:18437/api/v1/health |

관리자 계정은 `setup.bat` 이 매번 랜덤 비밀번호로 생성합니다. 설치 직후에는 `backend/.env` 의 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 를 확인하세요.

추가 옵션:

```cmd
setup.bat --dry-run     :: 실제 설치 없이 단계만 출력
setup.bat --no-pause    :: 완료 후 창을 멈추지 않음
```

---

## 폐쇄망 배포 흐름

```
[온라인 PC]                              [폐쇄망 PC]
 setup.bat                               ─┐
 start.bat (선택, 동작 검증)               │
 offline_package.bat ───── ZIP ─────►    setup_offline.bat
                                          start_offline.bat
```

1. **온라인 PC**

   ```cmd
   setup.bat
   start.bat            :: 동작 확인 후 닫기
   offline_package.bat  :: dist\AeroOne-offline-YYYYMMDD-HHMMSS.zip 생성
   ```

   ZIP 안에 들어가는 것:

   - 저장소 소스 (`.git`, `.venv`, `node_modules`, `dist`, `backend/data` 등은 제외)
   - `_database/newsletter/` 의 HTML/PDF 원본 (패키징 시점 스냅샷, `newsletter_YYYYMMDD.html` 형식)
   - `frontend/node_modules` (오프라인용 별도 복사본)
   - Python wheelhouse (`offline_assets/python-wheels/`)
   - 선택적으로 `offline_installers/` 에 미리 둔 Python·Node 설치파일 → `offline_assets/installers/`
     - 예: `python-3.12.7-amd64.exe`, `node-v20.18.0-x64.msi`
     - 폐쇄망 PC에 Python 3.12 또는 Node.js LTS 가 없는 경우 반드시 동봉

2. **폐쇄망 PC**

   - 권장 압축 해제 위치: `D:\AeroOne\` 또는 `C:\Programs\AeroOne\` 등 **사용자 쓰기 권한이 있는 절대 경로** (`Program Files` 같은 권한 제한 폴더 / 한글 경로 / 공백 경로 회피)
   - `Python 3.12` 와 `Node.js LTS` 가 PC에 없으면 ZIP 안 `offline_assets\installers\` 의 설치 파일을 먼저 실행

   **기본 = LAN (1.0.22+)** — 옵션 없이 실행하면 이 PC 의 LAN IPv4 를 자동 감지해 `0.0.0.0` 으로 띄웁니다. 같은 PC 와 LAN 의 다른 PC 모두 `http://<IP>:29501/` 로 접속 가능 (LAN IPv4 미감지 시 localhost 로 폴백).

   ```cmd
   setup_offline.bat    :: 사전 점검 + .env 재작성 + 가상환경 + 오프라인 pip install + DB + build (기본 LAN)
   start_offline.bat    :: 백엔드/프런트 실행 + 브라우저 자동 오픈 (기본 LAN, 0.0.0.0 바인딩)
   ```

   **이 PC 에서만 (`--local`)** — LAN 노출 없이 localhost 전용

   ```cmd
   setup_offline.bat --local
   start_offline.bat --local    :: 모두 127.0.0.1 바인딩
   ```

   **특정 IP 고정 (`--allow-host=<IP>`)** — 자동 감지가 틀리거나 호스트를 명시하고 싶을 때

   ```cmd
   setup_offline.bat --allow-host=192.168.1.10
   start_offline.bat --allow-host=192.168.1.10
   ```

   환경 변수 `AEROONE_ALLOW_HOST` 도 동일하게 받습니다(`auto` 도 가능). **1.0.22+ 부터 기본이 LAN** 이므로 옵션 없이 실행해도 IP 로 접속됩니다 — 명시 IP 고정이 필요할 때만 `--allow-host=<IP>` 를 쓰세요. LAN 으로 접속할 땐 자기 PC 도 `http://<IP>:29501/` 로 들어가야 쿠키 격리를 피할 수 있습니다(`start_offline.bat` 가 자동 오픈하는 URL 을 그대로 사용). **LAN 의 다른 PC** 에서 접속하려면 이 PC 에서 `scripts\allow_lan_firewall.cmd` 를 관리자 권한으로 한 번 실행해 방화벽 인바운드(`18437`/`29501`, 로컬 서브넷 한정)를 허용하세요 (`--remove` 로 원복). 인터넷 노출 차단을 위해 두 포트의 LAN 외부 차단 규칙도 함께 두세요. LAN 노출 없이 이 PC 에서만 쓰려면 `--local`.

   `setup_offline.bat` 는 폐쇄망 PC 에서 `APP_ENV=closed_network` 로 부팅하고 `JWT_SECRET_KEY` 와 `ADMIN_PASSWORD` 를 새 랜덤 값으로 다시 생성합니다 (기존 `.env` 는 `.bak` 로 자동 백업). `closed_network` 모드는 HTTP 폐쇄망에서 secure cookie 는 끄고 secret 강도 검증은 켜는 전용 모드입니다. 설치 직후 `backend\.env` 의 `ADMIN_PASSWORD` 를 확인해 두세요.

3. **신규 뉴스레터 추가 (운영 PC에서 반복 작업)**

   - `_database\newsletter\` 폴더에 새 HTML / PDF 파일을 추가 (파일명: `newsletter_YYYYMMDD.html`)
   - **별도 조작 없이** `/newsletters` 페이지를 새로고침하면 새 발행호가 자동 반영됩니다 (서버 재시작 불필요). 공개 읽기 요청이 들어올 때 폴더 변경(파일명·크기·수정시각)을 감지해 DB 를 자동 동기화합니다.
   - 관리자 페이지 (`/login` 로그인 → `/admin/newsletters`) 의 **Import / Sync** 버튼은 즉시 강제 동기화하는 수동 폴백으로 남아 있습니다.

4. **백업 (정기 작업)**

   - DB: `backend\data\aeroone.db` 한 파일 복사
   - 사용자 콘텐츠: `storage\markdown\` 와 `storage\thumbnails\` 폴더 백업
   - 원본: `_database\newsletter\` 폴더 백업
   - 위 세 경로만 보관하면 동일 PC 또는 다른 폐쇄망 PC에서 복원 가능합니다.

- 종합 가이드 (사람·AI 모두 위한 단일 진입점, 9단계 진행 체크리스트 포함): [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md)
- 자세한 절차·FAQ·트러블슈팅: [`docs/runbook/windows-offline.md`](docs/runbook/windows-offline.md)

---

## 기술 스택

| 계층 | 사용 기술 |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Backend | FastAPI, Pydantic, SQLAlchemy 2.x, Alembic |
| Auth | signed HttpOnly session cookie, CSRF 토큰 |
| Data | SQLite (운영 시작점) → PostgreSQL 전환 가능 |
| Storage | 로컬 파일시스템 + `StorageService` 추상화 (MinIO/S3 전환 여지) |
| Test | pytest, pytest-asyncio, httpx / Vitest, Testing Library |
| Infra | Docker Compose, Windows 배치 스크립트 |

---

## 프로젝트 구조

```
AeroOne/
├─ backend/              FastAPI 앱, Alembic 마이그레이션, 시드 스크립트
├─ frontend/             Next.js 앱
├─ _database/newsletter/ 뉴스레터 HTML/PDF 원본 (newsletter_YYYYMMDD.html 형식, import root)
├─ _database/civil_aircraft/ 민간항공기 규격 정적 HTML 보고서
├─ _database/document/   문서 보관소 HTML (하위 폴더로 분류 가능, /documents 에서 폴더 트리로 열람)
├─ storage/              Markdown / 썸네일 / 첨부 (앱 관리)
├─ docs/                 개발 계획, 런북, 설계 문서
├─ infra/                Dockerfile / compose 자원
├─ scripts/              런처 보조 스크립트 (브라우저 오픈 등)
├─ setup.bat             온라인 PC 초기 설치
├─ start.bat             온라인 PC 실행
├─ offline_package.bat   폐쇄망용 ZIP 패키지 생성
├─ setup_offline.bat     폐쇄망 PC 초기 설치
├─ start_offline.bat     폐쇄망 PC 실행
└─ docker-compose.yml    개발용 컨테이너 실행
```

---

## 환경 변수

기본값과 의미만 발췌했습니다. 전체 키는 [`.env.example`](.env.example) 참고.

| 키 | 의미 | 기본값 / 비고 |
|---|---|---|
| `APP_ENV` | 실행 모드 | `development` (`setup.bat`) / `test` / `closed_network` (`setup_offline.bat`) / `production`. `closed_network` 와 `production` 은 기본 secret 거부 |
| `BACKEND_PORT` / `FRONTEND_PORT` | 서비스 포트 | `18437` / `29501` |
| `DATABASE_URL` | DB 연결 문자열 | SQLite 기본, PostgreSQL 가능 |
| `JWT_SECRET_KEY` | 세션 서명 키 | setup 시 랜덤 생성 (64자 hex) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 단일 시드 관리자 | setup 시 비밀번호 랜덤 생성 (48자 hex) |
| `ADMIN_SESSION_COOKIE_NAME` | 관리자 세션 쿠키 이름 | `admin_session` |
| `CSRF_COOKIE_NAME` | CSRF 토큰 쿠키 이름 | 프런트와 동일 값 사용 |
| `NEWSLETTER_IMPORT_ROOT_HOST` / `_CONTAINER` | 원본 폴더 호스트/컨테이너 경로 | 컨테이너 실행 시 양쪽 사용 |
| `STORAGE_ROOT` | 앱 storage 루트 | 정적 노출은 `thumbnails` 하위만 |
| `CORS_ORIGINS` | 프런트 origin 화이트리스트 | `http://localhost:29501` (LAN 모드면 두 origin) |
| `NEXT_PUBLIC_API_BASE_URL` | 브라우저가 호출할 backend 베이스 | loopback 시 `http://localhost:18437`, LAN 모드 시 `http://<host>:18437` |
| `SERVER_API_BASE_URL` | Next.js SSR 이 호출할 backend 베이스 | 항상 IPv4 loopback (`http://127.0.0.1:18437`) |
| `LAN_HOST` | (옵션) `setup_offline.bat --allow-host` 가 .env 에 남기는 메타 | LAN 모드 운영 중인 호스트 표시용 |
| `AEROONE_ALLOW_HOST` | LAN 모드 호스트 (옵션 인자 대신 환경 변수로 지정) | `setup_offline.bat` / `start_offline.bat` 모두 인식 |
| `AI_FEATURES_ENABLED` | 대시보드 AI 기능 on/off | `true` (`setup.bat` / `setup_offline.bat`) |
| `OLLAMA_BASE_URL` | 백엔드가 호출할 Ollama API | 기본 `http://127.0.0.1:11434`; 다른 폐쇄망 PC면 `http://<ollama-ip>:11434` |
| `OLLAMA_DEFAULT_MODEL` | AI 채팅 기본 모델 | `gemma4:12b` |

---

## 개발자용 로컬 실행

Linux / macOS / WSL:

```bash
cp .env.example .env

cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
PYTHONPATH=. python scripts/seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 18437

# 다른 터미널
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

`git worktree` 환경에서 `.venv` / `node_modules` / `backend/data` / `_database/newsletter` 가 비어 보이는 케이스 등 운영자 주의사항은 [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) 에 정리되어 있습니다.

---

## 검증

```bash
# backend
cd backend && . .venv/bin/activate
python -m pytest

# frontend
cd frontend
npm run test
npm run typecheck
npm run build
```

릴리스 1.5.0 기준 backend `pytest tests` 결과 **162 passed** (실패 0), frontend Vitest **179 passed** (46 파일), `tsc --noEmit` exit 0, `next build` 성공. 회귀 발생 시 [`docs/INDEX.md`](docs/INDEX.md) §7 테스트 인벤토리와 [`docs/reports/INDEX.md`](docs/reports/INDEX.md) 의 단계별 보고서를 거꾸로 읽어 어느 단계의 회귀인지 진단합니다.

---

## 보안과 운영 권장사항

- 운영 모드는 `APP_ENV` 로 4 가지 — `development` (개발자 로컬), `test` (pytest 픽스처), `closed_network` (폐쇄망 HTTP, secret 강도 검증 ON / secure cookie OFF), `production` (인터넷 노출 HTTPS, 둘 다 ON). `closed_network` 와 `production` 은 `change-me` 또는 짧은 secret 을 부팅 시 거부합니다.
- HTTPS 종단을 두면 `production` 에서 `secure cookie` 가 자동 활성화됩니다. HTTP-only 폐쇄망은 `closed_network` 로 둬야 쿠키가 살아 있으면서 검증도 켜집니다.
- **1.0.22+ 기본이 LAN** 이라 backend / frontend 를 `0.0.0.0` 으로 노출합니다(이 PC 의 LAN IP 자동 감지). **반드시 신뢰할 수 있는 폐쇄망 LAN** 안에서만 사용하세요. LAN 노출을 원치 않으면 `--local` 로 localhost 전용 실행이 가능합니다. 다른 PC 접속은 `scripts\allow_lan_firewall.cmd`(관리자, 로컬 서브넷 한정)로 허용하고, Windows 방화벽에서 `18437` / `29501` 두 포트의 LAN **외부** 차단 규칙을 함께 두세요. 인터넷 노출 production 으로 사용 금지.
- `_database/newsletter` 와 `storage/` 는 운영 PC에 한정해 두고, 백업·접근 권한은 사내 정책에 맞춰 분리하세요.
- 관리자 비밀번호 노출이 의심되면 `setup.bat` 또는 `setup_offline.bat` 을 다시 실행하세요. 새 랜덤 값으로 교체되며 기존 `.env` 는 `.bak` 로 자동 백업됩니다.
- 관리자 인증은 `/admin/*` 모든 mutation/sync 엔드포인트의 신뢰 경계입니다. 정책 배경: [`docs/runbook/admin-auth.md`](docs/runbook/admin-auth.md)

---

## 문서

전체 문서 색인은 [`docs/INDEX.md`](docs/INDEX.md) 입니다. 자주 찾는 자리만 추리면 다음과 같습니다.

| 분류 | 위치 |
|---|---|
| 폐쇄망 운영 종합 가이드 | [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) (18장 + 부록, Open Notebook co-deploy §18) |
| **폐쇄망 상세 설치·사용 매뉴얼 (AeroOne + Open Notebook)** | [`docs/runbook/closed-network-install-manual.md`](docs/runbook/closed-network-install-manual.md) |
| Open Notebook 동거 배포 런북 | [`docs/runbook/open-notebook-airgap.md`](docs/runbook/open-notebook-airgap.md) |
| 폐쇄망 오픈소스 도입 프로세스 (재사용 플레이북) | [`docs/closed-network-oss-adoption-process.md`](docs/closed-network-oss-adoption-process.md) |
| 폐쇄망 실행 런북 | [`docs/runbook/windows-offline.md`](docs/runbook/windows-offline.md) (가장 깊은 세부) |
| 로컬 개발 런북 | [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) |
| 관리자 인증 정책 | [`docs/runbook/admin-auth.md`](docs/runbook/admin-auth.md) |
| 단계별 변경 보고서 (closed_network / --allow-host / 시뮬레이션 / docstring) | [`docs/reports/INDEX.md`](docs/reports/INDEX.md) |
| 설계 산출물 (plan + spec) | [`docs/superpowers/INDEX.md`](docs/superpowers/INDEX.md) |
| 개발 계획 (MVP) | [`docs/dev_plan/20260327_newsletter_platform_mvp.md`](docs/dev_plan/20260327_newsletter_platform_mvp.md) |
| AI 에이전트 / 협업자 진입점 | [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) |

---

## 사용 범위와 기여

- AeroOne 은 사내 폐쇄망 운영을 일차 목적으로 하는 운영 소프트웨어입니다. 외부 환경에 그대로 노출하기 전에는 최소한 다음을 점검하세요.
  - `APP_ENV=production` 강제와 secret/비밀번호 정책
  - HTTPS 종단과 `secure cookie` 보장
  - `_database/newsletter` 와 `storage/` 의 접근 권한
  - CORS / 리버스 프록시 / 방화벽 구성
- 커밋 메시지는 한국어 제목 + 한국어 본문 + Lore trailer 규칙을 따릅니다. 자세한 규칙: [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), [`CONTRIBUTING.md`](CONTRIBUTING.md).
- 라이선스는 [`LICENSE`](LICENSE) (All Rights Reserved) — 사내 사용을 일차 목적으로 합니다. 외부 사용·재배포·라이선스 예외 / 보안 신고는 LICENSE 의 연락처로 직접 연락하세요.
