# PRD — AeroOne Newsletter / Document Platform MVP

## 문서 메타
- 작성일: 2026-03-27
- 상태: Draft for consensus review
- 범위: 폐쇄망 사내 웹 플랫폼의 첫 모듈(뉴스레터/문서형 서비스 MVP)
- 구현 방식: Lean modular monolith

## RALPLAN-DR Summary

### Principles
1. **Lean modular monolith first**: 배포와 운영은 단순하게 유지하되, 코드 경계는 모듈별로 분리한다.
2. **Filesystem is the raw content source**: 현재 운영 실데이터인 HTML/PDF 파일을 그대로 활용하고 DB 는 메타데이터 인덱스 역할을 맡는다.
3. **Security at every file boundary**: 허용 루트, 경로 정규화, source_type 분기, 렌더링 보호를 기본 정책으로 둔다.
4. **TDD before service growth**: import/sync, 인증, 렌더링, 관리자 흐름은 테스트로 먼저 고정한다.
5. **Domain-neutral shared layers**: auth, storage, db, config, admin shell 은 newsletter 외 모듈도 재사용 가능하게 설계한다.

### Decision Drivers (Top 3)
1. **기존 HTML/PDF 실데이터를 즉시 운영에 연결해야 한다.**
2. **폐쇄망 환경에서 낮은 운영 복잡도로 설치/실행 가능해야 한다.**
3. **향후 다른 내부 서비스 모듈을 추가할 때 구조 변경 비용이 낮아야 한다.**

### Viable Options
#### Option A — 분리된 Next.js + FastAPI 의 단일 저장소 modular monolith (채택)
- 접근: frontend 와 backend 를 분리된 앱으로 두되, 하나의 repo / compose 스택으로 운영한다. 원본 파일은 filesystem 에 두고 DB 는 metadata/search/admin 상태 저장에 사용한다.
- 장점:
  - 사용자 요구 스택과 정확히 일치한다.
  - public/admin UI 와 file import/security 로직의 책임이 명확하다.
  - SQLite 로 시작하고 PostgreSQL 로 이전하기 쉽다.
- 단점:
  - Next.js 와 FastAPI 두 런타임을 관리해야 한다.
  - 초기 설정 파일 수가 늘어난다.

#### Option B — Next.js 를 BFF 로 사용하고 렌더링/파일 접근을 프론트와 백엔드가 함께 담당
- 접근: Next.js 가 서버 컴포넌트에서 backend API 뿐 아니라 일부 content proxy 역할까지 수행한다.
- 장점:
  - UI 레이어에서 렌더링 제어를 유연하게 할 수 있다.
  - 일부 화면 응답 최적화가 쉽다.
- 단점:
  - 파일 접근 권한/보안 검증이 프론트와 백엔드에 분산될 위험이 있다.
  - backend service 경계가 흐려져 장기 확장성이 떨어진다.

#### Option C — import/auth/rendering 을 분리한 다중 서비스 구조
- 접근: ingest service, content service, auth service, frontend 를 개별 배포 단위로 분리한다.
- 장점:
  - 장기적으로 서비스 분리가 쉽다.
  - 독립적 스케일링이 가능하다.
- 단점:
  - 현재 MVP 범위 대비 과도하게 무겁다.
  - 폐쇄망 운영/배포 복잡도가 올라간다.

### Why Option A Wins
- 현재 가장 중요한 것은 `Newsletter/output` 의 HTML/PDF 를 안전하고 빠르게 노출하는 것이다.
- Option A 는 요구 스택을 그대로 따르면서도, 공통 계층을 중립적으로 유지하여 후속 모듈 확장을 허용한다.
- Option B 는 보안 책임이 분산되고, Option C 는 MVP 단계에 비해 과도하다.

### Invalidated Alternatives
- Option B 기각: 파일 검증과 렌더링 책임이 분산되어 추후 유지보수와 보안 관리가 어려워진다.
- Option C 기각: 현재 운영 환경(폐쇄망, 소규모 MVP, SQLite 시작)에서 서비스 분리 비용이 가치보다 크다.

## 요구사항 요약
- `Newsletter/output` 아래 HTML/PDF 파일을 스캔하고, 같은 발행일의 HTML/PDF 를 하나의 뉴스레터 이슈로 묶어 DB 메타데이터와 동기화한다.
- 사용자 UI 에서 뉴스레터 목록/검색/상세를 제공한다.
- 상세에서 source_type 에 따라 HTML / PDF / Markdown 렌더링을 분기한다.
- 관리자 UI/API 에서 로그인, 메타데이터 CRUD, 태그/카테고리, 썸네일, import/sync 를 수행한다.
- Markdown 원본이 아직 없어도 데이터 모델/렌더러/스토리지 구조는 미리 포함한다.
- 향후 newsletter 외 모듈을 추가할 수 있도록 공통 계층과 디렉토리 구조를 설계한다.

## 시스템 아키텍처 설명

### 아키텍처 선택
- 배포 형태: `frontend + backend + sqlite volume + storage volume` 의 단일 compose 스택
- 백엔드 구조: `core / db / modules` 기반 modular monolith
- 프론트엔드 구조: App Router 기반 public/admin 분리
- 파일 접근 정책: 컨테이너 내부 고정 경로(`/mnt/import/newsletters`) 아래 읽기 전용 마운트
- 스토리지 경계: `Newsletter/output` 는 외부 원본 mount, `storage/*` 는 앱 관리형 저장소로 분리

### 런타임 흐름
1. 관리자가 sync 실행
2. backend 의 `file_discovery_service` 가 import root 스캔
3. `newsletter_import_service` 가 파일명을 기준으로 이슈 키(예: `20260326`)를 추출해 HTML/PDF 자산을 하나의 newsletter 로 병합하고 checksum/mtime 기준으로 upsert
4. `_debug.html` 은 import 대상에서 제외
5. public API 가 metadata 와 `available_assets` 를 조회
6. detail 조회 시 기본 `source_type` 을 우선 렌더링하고, 사용자가 다른 asset type(HTML/PDF/Markdown) 으로 전환 가능
7. frontend 는 적절한 viewer 컴포넌트로 렌더링

### 모듈/서비스 책임 경계
- `modules/*`: 도메인 경계. 각 모듈은 자신의 `api / schemas / models / repositories / services` 를 소유한다.
- `services/*`: 모듈 내부 유스케이스와 비즈니스 규칙을 조합한다. router 에 비즈니스 로직을 직접 두지 않는다.
- `modules/shared/*`: storage, pagination, 공통 예외, 파일 경로 정책 같은 도메인 중립 기능만 둔다.
- `core/*`: 설정, 보안, 로깅, 앱 라이프사이클 같은 횡단 관심사를 담당한다.

## 상세 기술 스택 설명

### Frontend
- Next.js App Router
- TypeScript strict mode
- Tailwind CSS
- 서버 컴포넌트로 목록/상세 데이터 fetch
- 클라이언트 컴포넌트로 로그인 폼, 관리자 편집 폼, sync 액션 처리

### Backend
- FastAPI + Uvicorn
- Pydantic v2 schemas
- SQLAlchemy 2.x ORM + Alembic migration
- password hashing + **`admin_session` 이름의 signed HttpOnly short-lived JWT cookie(SameSite=Lax) + CSRF 토큰** 기반 관리자 인증
- 로컬 파일시스템 기반 storage abstraction

### Database
- `DATABASE_URL=sqlite:///...` 기본값
- PostgreSQL 전환 대비: SQLAlchemy 공통 타입, JSON/ARRAY/SQLite 특화 기능 최소화

## 프로젝트 디렉토리 구조

```text
AeroOne/
├─ backend/
│  ├─ alembic.ini
│  ├─ alembic/
│  │  ├─ env.py
│  │  └─ versions/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ security.py
│  │  │  └─ logging.py
│  │  ├─ db/
│  │  │  ├─ base.py
│  │  │  └─ session.py
│  │  └─ modules/
│  │     ├─ auth/
│  │     │  ├─ api.py
│  │     │  ├─ models.py
│  │     │  ├─ repositories.py
│  │     │  ├─ schemas.py
│  │     │  └─ services.py
│  │     ├─ newsletter/
│  │     │  ├─ api/
│  │     │  │  ├─ public.py
│  │     │  │  ├─ admin.py
│  │     │  │  └─ imports.py
│  │     │  ├─ models/
│  │     │  ├─ repositories/
│  │     │  ├─ schemas/
│  │     │  └─ services/
│  │     └─ shared/
│  │        └─ storage/
│  └─ tests/
├─ frontend/
│  ├─ app/
│  │  ├─ (public)/newsletters/page.tsx
│  │  ├─ (public)/newsletters/[slug]/page.tsx
│  │  ├─ login/page.tsx
│  │  └─ admin/
│  ├─ components/
│  ├─ lib/
│  └─ tests/
├─ storage/
│  ├─ import/newsletters/
│  ├─ markdown/newsletters/
│  ├─ thumbnails/
│  └─ attachments/
├─ infra/
│  ├─ backend/Dockerfile
│  └─ frontend/Dockerfile
├─ docs/
│  └─ dev_plan/
└─ Newsletter/output/
```

### 폴더 역할
- `frontend/`: 사용자/관리자 웹 UI
- `backend/`: API, 인증, DB, import/sync, 렌더링 서비스
- `storage/`: 앱 관리형 Markdown/썸네일/첨부 보관소
- `storage/import/newsletters/`: 향후 관리자 업로드/스테이징용 내부 경로(현재 운영 원본 루트는 아님)
- `infra/`: Dockerfile, 배포용 설정
- `docs/`: 개발 계획, 운영 문서, 마이그레이션 메모

## DB 스키마 설계

### 1) users
- `id` (PK)
- `username` (unique)
- `email` (unique, nullable)
- `password_hash`
- `role` (`admin` 기본)
- `is_active`
- `last_login_at`
- `created_at`
- `updated_at`

### 2) categories
- `id`
- `name`
- `slug`
- `description`
- `created_at`
- `updated_at`

### 3) tags
- `id`
- `name`
- `slug`
- `created_at`
- `updated_at`

### 4) newsletters
- `id`
- `title`
- `slug`
- `description`
- `source_type` (`html`, `pdf`, `markdown`) — 기본 렌더링 타입
- `source_file_path` (기본 자산 상대 경로; 호환성 유지용)
- `markdown_file_path` (기본 Markdown 자산 상대 경로; 호환성 유지용)
- `thumbnail_path`
- `published_at`
- `created_at`
- `updated_at`
- `category_id` (FK)
- `is_active`
- `source_identifier` (발행일 기반 issue key 또는 관리 식별자)
- `source_checksum` (기본 자산 변경 감지)
- `source_mtime`
- `summary`

### 5) newsletter_assets
- `id`
- `newsletter_id`
- `asset_type` (`html`, `pdf`, `markdown`)
- `file_path`
- `checksum`
- `file_size`
- `is_primary`
- `created_at`
- `updated_at`

### 6) newsletter_tags
- `newsletter_id`
- `tag_id`

### 후속 확장 엔터티
- `read_history`
- `favorites`
- `audit_logs`

## API 명세

### 공개 API
- `GET /api/v1/health`
- `GET /api/v1/newsletters`
  - query: `q`, `category`, `tag`, `source_type`, `page`, `page_size`
- `GET /api/v1/newsletters/{slug}`
  - response 에 `available_assets`, `default_asset_type` 포함
- `GET /api/v1/newsletters/{id}/content/{asset_type}`
  - `asset_type`: `html` | `pdf` | `markdown`
- `GET /api/v1/newsletters/{id}/download/{asset_type}` (선택 alias)

### 인증 API
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

### 관리자 API
- 인증 방식: `signed HttpOnly session cookie + CSRF` 기반 단일 관리자 로그인
- `GET /api/v1/admin/newsletters`
- `POST /api/v1/admin/newsletters`
- `PATCH /api/v1/admin/newsletters/{id}`
- `DELETE /api/v1/admin/newsletters/{id}`
- `POST /api/v1/admin/newsletters/sync`
- `POST /api/v1/admin/newsletters/{id}/thumbnail`
- `GET /api/v1/admin/categories`
- `POST /api/v1/admin/categories`
- `GET /api/v1/admin/tags`
- `POST /api/v1/admin/tags`

## HTML / PDF / Markdown 렌더링 전략

### HTML
- backend 가 허용 루트 하위의 HTML 파일만 읽는다.
- 파일 읽기 전 `Path.resolve()` 로 루트 이탈 여부 검사
- 위험 요소 제거 대상: `<script>`, `<iframe>`, `<object>`, `<embed>`, `<base>`, `<form>`, 이벤트 핸들러 속성(`on*`), 원격 CSS/JS 참조
- backend 응답 헤더는 `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'` 를 기본값으로 사용
- 렌더링 방식: frontend 는 **`allow-scripts` 와 `allow-same-origin` 없는** sandboxed iframe 기반 viewer 를 사용하고, 필요 시 `srcDoc` 로 주입한다
- 상대 경로 자산: MVP 에서는 상대 자산과 원격 자산을 모두 차단/제거하고, 현재 실데이터처럼 인라인 스타일 중심 HTML 에 최적화
- 외부 링크는 `rel="noopener noreferrer"` 를 강제하고 새 탭 열기만 허용한다

### PDF
- backend 는 검증된 PDF 경로만 FileResponse 로 전달
- frontend 는 브라우저 내 `<iframe>` / `<object>` 기반 viewer 와 별도 다운로드 링크 제공
- PDF 썸네일 생성은 후속 확장 포인트로 문서화

### Markdown
- `storage/markdown/newsletters/*.md` 저장
- backend `markdown_render_service` 가 Markdown → 안전 HTML 변환
- 관리자 CRUD 는 추후 추가하되, 모델/스토리지/API 확장 지점은 지금 설계에 포함

## `AeroOne\Newsletter\output` 연동 전략
- 개발 기본값: 저장소 내부 상대 경로 `./Newsletter/output`
- Docker 컨테이너 내부 고정 경로: `/mnt/import/newsletters`
- `.env` 예시:
  - `NEWSLETTER_IMPORT_ROOT_HOST=./Newsletter/output`
  - `NEWSLETTER_IMPORT_ROOT_CONTAINER=/mnt/import/newsletters`
- Windows 절대 경로가 필요하면 `D:/Chanil_Park/Project/Programming/AeroOne/Newsletter/output` 처럼 슬래시 사용
- backend 는 컨테이너 내부 경로만 신뢰하고, DB 에는 해당 루트 기준 상대 경로만 저장
- `storage/import/newsletters` 는 향후 내부 업로드 파일을 임시 적재하는 staging 영역이며, 현재 운영 원본 폴더와 혼동하지 않는다
- `_debug.html` 파일은 import discovery 단계에서 기본 제외한다

## 환경 변수 설계 (.env.example 반영 대상)
- `APP_ENV=development`
- `BACKEND_PORT=8000`
- `FRONTEND_PORT=3000`
- `DATABASE_URL=sqlite:////app/data/aeroone.db`
- `JWT_SECRET_KEY=change-me`
- `ADMIN_SESSION_COOKIE_NAME=admin_session`
- `ACCESS_TOKEN_TTL_MINUTES=30`
- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=change-me`
- `NEWSLETTER_IMPORT_ROOT_HOST=./Newsletter/output`
- `NEWSLETTER_IMPORT_ROOT_CONTAINER=/mnt/import/newsletters`
- `STORAGE_ROOT=/app/storage`
- `CORS_ORIGINS=http://localhost:3000`

## 실행 산출물 맵(사용자 요구 1~17)
1. 시스템 아키텍처 설명 → 본 문서 `시스템 아키텍처 설명`
2. 상세 기술 스택 설명 → 본 문서 `상세 기술 스택 설명`
3. 프로젝트 디렉토리 구조 → 본 문서 `프로젝트 디렉토리 구조`
4. DB 스키마 설계 → 본 문서 `DB 스키마 설계`
5. API 명세 → 본 문서 `API 명세`
6. HTML / PDF / Markdown 렌더링 전략 → 본 문서 `HTML / PDF / Markdown 렌더링 전략`
7. `AeroOne\Newsletter\output` 연동 전략 → 본 문서 `AeroOne\Newsletter\output 연동 전략`
8. `.env.example` → 구현 단계 5 산출물
9. `docker-compose.yml` → 구현 단계 5 산출물
10. backend 핵심 코드 → 구현 단계 3 산출물
11. frontend 핵심 코드 → 구현 단계 4 산출물
12. 샘플 Markdown 파일 → 구현 단계 6 산출물
13. HTML/PDF import 또는 sync 예시 → 구현 단계 6 산출물
14. seed 데이터 예시 → 구현 단계 6 산출물
15. 로컬 실행 방법 → 구현 단계 6 산출물
16. SQLite -> PostgreSQL 이전 설계 포인트 → Acceptance/ADR/후속 문서에 포함
17. 향후 다중 내부 서비스 확장 고려사항 → Principles/ADR/후속 과제에 포함

## 단계별 구현 계획 (사용자 지정 순서 고정)

### 1. 아키텍처 및 프로젝트 구조
**생성 파일/디렉토리**
- `backend/app/core/*`, `backend/app/db/*`, `backend/app/modules/*`
- `frontend/app/*`, `frontend/components/*`, `frontend/lib/*`
- `storage/markdown/newsletters`, `storage/thumbnails`, `storage/attachments`
- `infra/backend/Dockerfile`, `infra/frontend/Dockerfile`

**완료 기준**
- 공통 계층과 모듈 계층 책임이 README/문서에 명시됨
- newsletter 외 도메인 확장 예시가 문서에 있음

### 2. 데이터베이스 및 API 설계
**생성 파일**
- `backend/app/modules/newsletter/models/newsletter.py`
- `backend/app/modules/newsletter/models/newsletter_asset.py`
- `backend/app/modules/newsletter/schemas/*.py`
- `backend/alembic/versions/<initial>.py`
- `docs/api/newsletter-mvp.md` (선택)

**완료 기준**
- 초기 Alembic 마이그레이션 생성 가능
- 모든 공개/관리자 API 요청/응답 스키마가 정의됨

### 3. 백엔드 코드
**우선 테스트 작성**
- `backend/tests/unit/newsletter/test_file_discovery_service.py`
- `backend/tests/unit/newsletter/test_asset_pairing.py`
- `backend/tests/unit/newsletter/test_path_guard.py`
- `backend/tests/integration/test_newsletter_public_api.py`
- `backend/tests/integration/test_admin_newsletter_api.py`
- `backend/tests/integration/test_auth_api.py`

**구현 파일**
- `backend/app/modules/newsletter/services/file_discovery_service.py`
- `backend/app/modules/newsletter/services/newsletter_import_service.py`
- `backend/app/modules/newsletter/services/html_render_service.py`
- `backend/app/modules/newsletter/services/pdf_delivery_service.py`
- `backend/app/modules/newsletter/services/markdown_render_service.py`
- `backend/app/modules/shared/storage/service.py`
- `backend/app/modules/newsletter/api/public.py`
- `backend/app/modules/newsletter/api/admin.py`
- `backend/app/modules/newsletter/api/imports.py`

**완료 기준**
- sync 실행 시 HTML/PDF 파일 메타데이터가 DB 와 일치한다.
- 목록/상세/컨텐츠 응답이 source_type 별로 정상 동작한다.
- `_debug.html` 파일이 import 결과와 public 목록에서 제외된다.

### 4. 프론트엔드 코드
**우선 테스트 작성**
- `frontend/tests/components/newsletter-card.test.tsx`
- `frontend/tests/app/newsletters-page.test.tsx`
- `frontend/tests/app/newsletter-detail-page.test.tsx`
- `frontend/tests/app/admin-login.test.tsx`
- `frontend/tests/app/admin-newsletter-form.test.tsx`

**구현 파일**
- `frontend/app/(public)/newsletters/page.tsx`
- `frontend/app/(public)/newsletters/[slug]/page.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/admin/newsletters/page.tsx`
- `frontend/app/admin/newsletters/new/page.tsx`
- `frontend/app/admin/newsletters/[id]/edit/page.tsx`
- `frontend/app/admin/imports/page.tsx`
- `frontend/components/newsletter/html-viewer.tsx`
- `frontend/components/newsletter/pdf-viewer.tsx`
- `frontend/components/newsletter/markdown-viewer.tsx`

**완료 기준**
- public 목록/상세 + admin CRUD/sync 흐름이 동작한다.
- 내부 업무형 UI 로 읽기 쉬운 레이아웃이 적용된다.
- 관리자 로그인 후 HttpOnly session cookie 기반 보호 라우트가 동작한다.

### 5. Docker 설정
**생성 파일**
- `docker-compose.yml`
- `infra/backend/Dockerfile`
- `infra/frontend/Dockerfile`
- `.env.example`

**완료 기준**
- `docker compose up --build` 로 프론트/백엔드와 볼륨이 기동
- backend healthcheck 통과
- import root read-only mount 확인

### 6. 샘플 데이터 및 실행 방법
**생성 파일**
- `storage/markdown/newsletters/sample-welcome.md`
- `backend/scripts/seed.py`
- `docs/runbook/local-dev.md`

**완료 기준**
- seed 로 기본 관리자/카테고리/태그 생성
- 샘플 Markdown 가 목록/상세에서 보인다.

## Acceptance Criteria (testable)
1. `Newsletter/output` 내 현재 존재하는 HTML/PDF 원본을 issue 단위 뉴스레터와 asset 단위 메타데이터로 안정적으로 sync 할 수 있다(고정 파일 개수는 smoke 검증에서 동적으로 비교).
2. 목록 API 가 제목/설명/태그 기준 검색을 지원한다.
3. 상세 화면이 기본 `source_type` 으로 먼저 렌더링되고, 존재하는 다른 asset type(예: PDF 다운로드/전환)도 노출한다.
4. 관리자만 메타데이터 수정, 태그/카테고리 지정, 썸네일 업로드, sync 실행을 할 수 있다.
5. 파일 경로는 허용 루트 밖으로 벗어날 수 없다.
6. Docker Compose 로 로컬/사내 서버에서 동일한 구조로 실행 가능하다.
7. SQLite 에서 시작해도 PostgreSQL 전환 시 모델/마이그레이션 구조를 재사용할 수 있다.
8. `_debug.html` 파일은 import 와 public 노출 대상에서 제외된다.
9. HTML content 응답은 CSP 헤더와 sandbox iframe 조합으로 스크립트 실행을 차단한다.
10. 관리자 인증은 signed HttpOnly session cookie 로 통일되어 executor 가 인증 방식을 추측하지 않아도 된다.

## Risks and Mitigations
- **HTML 보안 위험** → sanitize + sandbox + 허용 태그/속성 정책 + CSP
- **Windows 경로 혼선** → host path 와 container path 를 분리한 env 변수 사용
- **Markdown 부재** → 샘플 Markdown 와 `newsletter_assets`/`markdown_file_path` 로 구조 선반영
- **뉴스레터 전용 구조 고착화** → `modules/newsletter`, `modules/auth`, `modules/shared` 로 공통/도메인 경계 분리
- **SQLite 종속성 심화** → SQLAlchemy/Alembic 패턴 통일, vendor-specific SQL 지양
- **세션/쿠키 오구성 위험** → SameSite/CORS/CSRF 조합을 계획 단계에서 단일 전략으로 확정
- **디버그 산출물 혼입 위험** → `_debug.html` 명시적 제외 정책과 테스트 추가

## Verification Steps
- backend: `pytest`
- frontend: `npm test`
- typecheck: `npm run typecheck`, backend static check(optional)
- migration: `alembic upgrade head`
- smoke: `docker compose up --build` 후 `/api/v1/health`, `/newsletters`, `/admin/newsletters`
- sync 검증: 관리자 sync 실행 후 import root 의 실파일 수와 DB 의 issue/asset 수를 동적으로 비교하고 `_debug.html` 제외가 반영됐는지 확인
- 보안 검증: HTML content endpoint 의 CSP 헤더, sandbox viewer, 원격 자산 제거 여부 확인
- 인증 검증: 로그인 응답의 Set-Cookie 속성(HttpOnly/SameSite)과 CSRF 보호 확인

## Pre-mortem (3 scenarios)
1. **HTML 파일 렌더링 시 위험한 태그나 외부 리소스가 실행된다.**
   - 대응: sanitizer, sandbox iframe, 외부 resource 차단, 보안 테스트 추가
2. **Windows 경로 마운트 오류로 Docker 내부에서 import root 를 읽지 못한다.**
   - 대응: 상대 경로 기본값, 절대 경로 예시, backend startup validation, compose 문서화
3. **초기 구조가 newsletter 에 과도하게 결합되어 후속 announcement/schedule 모듈 추가 시 대규모 리팩터링이 발생한다.**
   - 대응: modules/shared 공통화, admin shell 분리, source_type/content model 일반화

## Expanded Test Plan

### Unit
- path guard, slug 생성, checksum 계산, markdown render, HTML sanitize, `_debug.html` 제외 규칙, auth password verify, session cookie helper

### Integration
- sync API, public list/detail API, admin CRUD API, login/logout, thumbnail upload, CSP header, CSRF validation

### E2E / UI
- public 목록 → 상세 → PDF/HTML/Markdown 뷰어
- admin 로그인 → sync → 메타데이터 수정 → public 반영 확인
- public 목록에서 `_debug.html` 파생 항목이 보이지 않음을 확인

### Observability
- sync 시작/종료/변경건수 structured logging
- 파일 누락/경로오류/권한오류 에러 로그
- health endpoint 에 DB/storage path 상태 노출(민감정보 제외)

## ADR

### Decision
분리된 Next.js + FastAPI 앱을 하나의 repo/compose 스택으로 운영하는 lean modular monolith 를 채택한다. Raw content 는 filesystem 에 유지하고 DB 는 metadata/search/admin 상태 저장소로 사용한다.

### Drivers
- 기존 HTML/PDF 실데이터 즉시 활용
- 폐쇄망에서 낮은 운영 복잡도 유지
- 후속 내부 서비스 모듈 확장 가능성 확보

### Alternatives considered
- Next.js BFF 중심 구조
- 다중 서비스 분리 구조

### Why chosen
- 요구 스택과 일치하면서 보안/파일 접근 책임을 backend 에 집중할 수 있다.
- frontend 는 문서형 UX 와 admin shell 에 집중하고 backend 는 import/security/data 관리에 집중할 수 있다.

### Consequences
- 앱이 둘로 나뉘어 초기 설정은 늘어나지만, 책임 경계가 분명해진다.
- 추후 모듈 추가 시 backend `modules/*`, frontend `app/admin/*` / `app/(public)/*` 확장 패턴을 재사용할 수 있다.

### Follow-ups
- Markdown CRUD UI 추가
- PDF 썸네일 파이프라인 추가
- PostgreSQL 전환용 compose override / migration rehearsal 작성

## Available-Agent-Types Roster
- `architect`: 구조 검토, 확장성/경계 검증
- `executor`: backend/frontend 기능 구현
- `test-engineer`: TDD 테스트 설계/보강
- `debugger`: import/rendering/경로 이슈 분석
- `verifier`: 완료 증거와 smoke test 검증
- `build-fixer`: Docker/build/type 오류 복구
- `writer`: runbook/README/운영 문서 정리

## Follow-up Staffing Guidance

### Ralph 경로(순차 집중 실행)
- lane 1: `executor` high — backend 구조/DB/API
- lane 2: `executor` high — frontend public/admin
- lane 3: `test-engineer` medium — 테스트 보강
- lane 4: `verifier` high — 최종 증거 수집

### Team 경로(병렬 실행)
- worker A: backend import/auth/metadata API
- worker B: frontend public/admin UI
- worker C: test/verification lane
- worker D(필요 시): infra/docker/docs

## Launch Hints
- Ralph: `$ralph .omx/plans/prd-newsletter-platform-mvp.md 기준으로 TDD 순서대로 backend→frontend→docker→seed 구현`
- Team: `$team backend, frontend, test, infra 4개 lane 으로 .omx/plans/prd-newsletter-platform-mvp.md 실행`
- omx CLI 힌트: `omx team --plan .omx/plans/prd-newsletter-platform-mvp.md`

## Team Verification Path
1. Team 이 backend/frontend/tests/docker/seed 를 각각 완료
2. verifier lane 이 테스트/compose/smoke evidence 수집
3. Ralph 또는 leader 가 전체 스택 재검증(health, sync, public/admin flows)
4. 최종 문서와 변경 파일 목록 정리 후 종료

## 권장 문서형 커밋 페이즈
1. **개발 계획 문서와 합의형 PRD/테스트 명세를 추가하여 구현 범위와 완료 기준을 고정**
2. **FastAPI 기반 모듈형 백엔드 골격과 DB/Alembic 설정을 도입하여 확장 가능한 기반을 마련**
3. **HTML/PDF 파일 import·sync 서비스와 안전한 경로 검증 로직을 구현하여 실데이터 연동 기반을 확보**
4. **공개 뉴스레터 조회 및 HTML/PDF/Markdown 렌더링 API를 구현하여 사용자 열람 기능을 완성**
5. **관리자 인증과 메타데이터 CRUD 및 썸네일 처리 흐름을 구현하여 운영 기능을 연결**
6. **Next.js 기반 public/admin UI를 추가하여 업무형 문서 서비스 화면을 제공**
7. **Docker Compose, seed 데이터, 샘플 Markdown, 실행 문서를 정리하여 로컬/사내 배포 경로를 마무리**

## 문서형 커밋 상세 템플릿(요약)

### 커밋 1
```markdown
뉴스레터 플랫폼 MVP의 구현 범위와 검증 기준을 문서로 고정하여 실행 착수 리스크를 줄임

작업 배경
- 앱 코드가 비어 있고 실데이터만 존재하므로 구현 전에 경계와 완료 기준을 고정해야 했다.

변경 목적
- MVP의 범위, 보안 정책, TDD 순서, 확장 경계를 문서로 고정한다.

주요 변경 내용
- dev_plan 문서 추가
- PRD 추가
- test-spec 추가

영향 범위
- 이후 모든 구현/검증/커밋 기준

Constraint: 현재 운영 원본은 Markdown이 아니라 HTML/PDF 파일이다
Rejected: 코드부터 먼저 구현 | 인증/보안/파일 정책이 불명확해 재작업 가능성이 높음
Confidence: high
Scope-risk: narrow
Directive: 문서에 없는 예외 정책은 구현에서 임의 추가하지 말 것
Tested: 문서 상호 정합성 검토
Not-tested: 실제 코드 실행
```

## Consensus Changelog
- Architect/critic 예상 피드백을 반영해 `_debug.html` 제외 정책을 명문화했다.
- 관리자 인증 방식을 signed HttpOnly session cookie 로 단일화했다.
- HTML 보안 전략을 CSP + sandbox iframe + 상대/원격 자산 제거로 구체화했다.
- `storage/import/newsletters` 와 `Newsletter/output` 의 역할 차이를 명시했다.
