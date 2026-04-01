# 2026-03-27 뉴스레터 플랫폼 MVP 개발 계획

## 1. 프로젝트 목표
- 폐쇄망 환경에서 동작하는 사내 웹 플랫폼의 첫 모듈로 뉴스레터/문서형 서비스를 구축한다.
- 현재 존재하는 `Newsletter/output` 내 HTML/PDF 파일을 즉시 활용할 수 있는 MVP를 우선 완성한다.
- 향후 announcement / information delivery / schedule / document publishing / admin tools 모듈을 같은 저장소 안에서 확장 가능한 modular monolith 구조로 설계한다.
- Markdown 원본은 아직 없지만, Markdown 콘텐츠 저장/렌더링/관리 구조를 이번 MVP부터 포함한다.

## 2. 범위
### 포함 범위
- Next.js + TypeScript + Tailwind CSS 기반 사용자/관리자 UI
- FastAPI + SQLAlchemy + Alembic + SQLite 기반 API/메타데이터 저장소
- `Newsletter/output` HTML/PDF 스캔 및 DB 동기화
- 뉴스레터 목록/상세/검색/태그/카테고리/썸네일 표시
- 관리자 로그인, 메타데이터 CRUD, import/sync 실행
- HTML/PDF/Markdown 3종 source_type을 수용하고, 한 뉴스레터 이슈에 여러 자산(HTML/PDF/Markdown)을 연결할 수 있는 데이터 모델
- Docker Compose 기반 로컬/사내 서버 실행 구조

### 제외 범위(후속 과제)
- 다중 관리자 권한 체계 세분화
- PDF 썸네일 자동 생성
- Markdown WYSIWYG 에디터
- AI 요약/추천 기능
- 캘린더/공지/문서 발행 등 후속 도메인 실제 구현

## 3. 기술 스택
### 프론트엔드
- Next.js App Router
- TypeScript
- Tailwind CSS
- 서버 컴포넌트 + 클라이언트 폼 컴포넌트 혼합

### 백엔드
- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy 2.x
- Alembic

### 데이터베이스
- 초기: SQLite
- 이후 전환 대상: PostgreSQL
- DB 연결 문자열은 `.env` 로 관리

### 파일/스토리지
- 원본 HTML/PDF: 로컬 파일시스템 읽기 전용 import root
- Markdown/썸네일/첨부: 프로젝트 내부 `storage/` 관리
- `StorageService` 추상화로 MinIO/S3 전환 여지 확보
- `storage/import/newsletters` 는 향후 관리자 업로드/스테이징용 내부 경로이며, 현재 운영 원본 루트는 `Newsletter/output` 으로 고정한다.

### 인증/보안 기본 선택
- 관리자 인증은 **signed HttpOnly session cookie + SameSite=Lax + 관리자 mutation API용 CSRF 토큰** 조합으로 고정한다.
- HTML 렌더링은 **backend sanitization + CSP 헤더 + iframe sandbox(스크립트 미허용)** 조합을 기본 전략으로 채택한다.
- `_debug.html` 파일은 운영 공개 목록에서 제외하고 import 대상에서도 기본 제외한다.

### 테스트(TDD)
- Backend: pytest, pytest-asyncio, httpx 기반 API/service 테스트
- Frontend: Vitest, Testing Library 기반 컴포넌트/페이지 테스트
- Compose smoke test: docker compose up 후 health check/manual smoke

## 4. 구현 단계

### 단계 1. 아키텍처 및 프로젝트 구조
**목표**
- 향후 다중 내부 서비스 확장을 고려한 lean modular monolith 골격 확정

**주요 작업**
- 상위 디렉토리 생성: `frontend/`, `backend/`, `storage/`, `infra/`, `docs/`
- 백엔드 모듈 경계 정의: `modules/auth`, `modules/newsletter`, `modules/shared`
- 프론트엔드 페이지 구조 정의: public / admin 구분
- `.env.example`, Docker volume/mount 기준 정의

**완료 기준**
- 디렉토리 구조와 책임이 문서화되어 있다.
- 향후 newsletter 외 announcement/schedule/admin 도메인 추가 경로가 설명되어 있다.

### 단계 2. 데이터베이스 및 API 설계
**목표**
- HTML/PDF/Markdown 통합 콘텐츠 모델과 관리자 운영 API 계약 고정

**주요 작업**
- `users`, `categories`, `tags`, `newsletters`, `newsletter_tags`, `newsletter_assets` 스키마 정의
- `newsletter_YYYYMMDD.html` + `Aerospace Daily News_YYYYMMDD.pdf` 를 한 이슈로 묶는 asset pairing 규칙 설계
- source_type enum(`html`, `pdf`, `markdown`) 은 newsletter 기본 렌더링 타입으로 사용하고, 실제 파일은 asset 테이블에서 관리
- 공개 API/관리자 API/인증 API 명세 확정
- Alembic 초기 마이그레이션 설계

**완료 기준**
- ERD 수준의 관계와 주요 필드가 정리되어 있다.
- API 요청/응답 예시와 인증 경계가 정의되어 있다.

### 단계 3. 백엔드 코드(TDD)
**목표**
- 파일 기반 뉴스레터 import/sync 와 public/admin API 구현

**주요 작업**
- 테스트 먼저 작성: 경로 검증, 파일 스캔, import/sync, 목록/상세, 관리자 인증
- FastAPI 앱/설정/DB 세션/ORM 모델/리포지토리/서비스/라우터 구현
- `_debug.html` 파일은 import 대상에서 제외하는 정책을 고정
- 관리자 인증 방식은 `signed HttpOnly session cookie + CSRF + 단일 시드 관리자` 로 우선 고정
- `file_discovery_service`, `newsletter_import_service`, `html_render_service`, `pdf_delivery_service`, `markdown_render_service`, `storage_service` 구현
- path traversal 방지 및 허용 루트 검증

**완료 기준**
- 테스트가 Red → Green → Refactor 순서로 통과한다.
- HTML/PDF/Markdown 컨텐츠 조회 API와 관리자 CRUD/import API가 동작한다.

### 단계 4. 프론트엔드 코드(TDD)
**목표**
- 문서형 UI의 public/admin 화면 구현

**주요 작업**
- 테스트 먼저 작성: 목록 렌더링, 상세 렌더링 분기, 로그인 폼, 관리자 수정 폼, sync 액션
- public 목록/상세, login, admin 목록/등록/수정/import 페이지 구현
- HTML/PDF/Markdown 전용 viewer 컴포넌트 구현
- 검색/태그/카테고리 필터 UI 구현

**완료 기준**
- 사용자와 관리자가 핵심 시나리오를 수행할 수 있다.
- source_type 별로 상세 화면이 올바르게 분기된다.

### 단계 5. Docker 설정
**목표**
- Windows 경로와 컨테이너 내부 경로 차이를 흡수하는 실행 환경 제공

**주요 작업**
- `docker-compose.yml` 작성
- `infra/backend/Dockerfile`, `infra/frontend/Dockerfile` 작성
- `NEWSLETTER_IMPORT_ROOT_HOST` → 컨테이너 마운트 경로 매핑 정의
- healthcheck, volume, env_file 설정

**완료 기준**
- `docker compose up --build` 로 backend/frontend 가 함께 올라온다.
- backend 가 import root 를 읽을 수 있다.

### 단계 6. 샘플 데이터 및 실행 방법
**목표**
- 개발자/운영자가 즉시 기동하고 import 결과를 검증 가능하게 한다.

**주요 작업**
- 샘플 Markdown 파일 추가
- seed 스크립트로 관리자 계정/기본 카테고리/태그 생성
- import/sync 예시 명령 및 API 예시 작성
- 로컬 실행/도커 실행/SQLite→PostgreSQL 전환 포인트 문서화

**완료 기준**
- 샘플 Markdown + seed 데이터 + 실행 절차가 문서화되어 있다.
- 신규 개발자가 README/문서만 보고 기동 가능하다.

## 5. TDD 운영 원칙
1. 서비스/라우터 구현 전에 테스트 파일부터 만든다.
2. 파일 스캔/경로 검증/렌더링 분기/로그인/관리자 CRUD 를 우선 Red 상태로 고정한다.
3. 최소 구현으로 Green 을 만든 뒤, 공통 로직 정리와 모듈 경계 리팩터링을 진행한다.
4. 각 페이즈 종료 시 lint, typecheck, unit/integration test, smoke test 를 수행한다.

## 6. 리스크
- 현재 실데이터는 Markdown이 아니라 HTML/PDF임.
- Markdown은 향후 도입 예정이나 아직 원본이 없음.
- 초기 운영은 파일 기반 import/rendering 중심임.
- HTML 렌더링 보안 이슈 존재.
- Windows 경로와 Docker 마운트 경로 차이 존재.
- 뉴스레터 전용 구조로 굳어질 위험 존재.

### 리스크 대응
- HTML/PDF 를 raw content source 로 두고 DB 는 메타데이터 인덱스로 사용한다.
- Markdown 은 `source_type` / `markdown_file_path` / 렌더링 서비스로 미리 수용한다.
- import root 검증 및 `Path.resolve()` 기반 안전 경로 체크를 강제한다.
- HTML 은 백엔드 sanitization + CSP 헤더 + 프론트 sandbox iframe 조합을 사용하고, 상대 자산/원격 스크립트는 차단한다.
- Docker 는 호스트 경로를 `.env` 로 분리하고 컨테이너 내부 경로는 고정한다.
- 공통 계층(auth/storage/db/config)은 도메인 중립 이름으로 작성한다.
- `_debug.html` 와 운영용 HTML 을 명시적으로 분리하여 디버그 산출물이 public 콘텐츠로 노출되지 않게 한다.

## 7. 후속 과제
- PDF 썸네일 추출 파이프라인
- 관리자 Markdown CRUD UI
- 문서 첨부파일 업로드/다운로드 정책
- read_history / favorites / audit_logs 추가
- announcement / schedule 모듈 추가 시 공통 navigation/admin shell 재사용

## 8. 권장 커밋 페이즈
### Phase 1
- 제목: **개발 계획 문서와 합의형 PRD·테스트 명세를 추가하여 뉴스레터 플랫폼 MVP 착수 기준을 고정**
- 본문 포함 항목:
  - 작업 배경: HTML/PDF 실데이터 중심 MVP 와 Markdown 확장 요구 동시 반영
  - 변경 목적: 구현 전 구조·범위·완료 기준·리스크를 문서로 고정
  - 주요 변경 내용: dev plan, PRD, test spec 작성
  - 영향 범위: 문서/계획 산출물
  - 테스트/검증: brownfield 파일 구조 확인, 계획 리뷰

### Phase 2
- 제목: **FastAPI 기반 모듈형 백엔드 골격과 DB·Alembic 초기 구성을 도입하여 확장 가능한 서버 기반을 마련**
- 본문 포함 항목:
  - 공통 계층(core/db/shared)과 도메인 계층(modules/auth, modules/newsletter) 분리 이유
  - SQLite 시작 및 PostgreSQL 이전 대비 설계 포인트
  - 초기 마이그레이션 및 설정 파일 추가 내역
  - 테스트: 설정 로딩, DB 세션, 마이그레이션 smoke

### Phase 3
- 제목: **HTML·PDF 파일 자산 페어링과 안전한 import·sync 로직을 구현하여 실데이터 연동 기준을 확정**
- 본문 포함 항목:
  - `newsletter_assets` 도입 배경
  - `_debug.html` 제외 정책
  - 경로 검증과 checksum 기반 동기화 전략
  - 테스트: file discovery, pairing, sync API, path traversal 방지

### Phase 4
- 제목: **공개 뉴스레터 조회 API와 HTML·PDF·Markdown 렌더링 분기를 구현하여 사용자 열람 기능을 완성**
- 본문 포함 항목:
  - 목록/상세 API 책임 분리
  - source_type 기본 렌더링 방식과 대체 자산 노출 방식
  - HTML sanitize / PDF delivery / Markdown render 전략
  - 테스트: public API, content endpoint, viewer 분기

### Phase 5
- 제목: **관리자 인증과 메타데이터 운영 API를 구현하여 사내 운영자가 콘텐츠를 관리할 수 있게 함**
- 본문 포함 항목:
  - signed HttpOnly session cookie + CSRF 기반 단일 관리자 인증 선택 이유
  - 카테고리/태그/썸네일/활성화 상태 관리 범위
  - sync 실행 권한과 audit 포인트
  - 테스트: auth, admin CRUD, thumbnail upload

### Phase 6
- 제목: **Next.js 기반 public/admin UI를 추가하여 문서형 내부 서비스 화면과 운영 화면을 연결**
- 본문 포함 항목:
  - public 목록/상세, admin 목록/등록/수정/import 화면 구성 이유
  - 업무형 UI 원칙과 source_type 탭/뷰어 분기 전략
  - 테스트: component/page render, form submit, auth guard

### Phase 7
- 제목: **Docker Compose, seed 데이터, 샘플 Markdown, 실행 문서를 정리하여 폐쇄망 실행 경로를 마무리**
- 본문 포함 항목:
  - Windows host path 와 container path 매핑 설명
  - seed 관리자/카테고리/태그/샘플 Markdown 구성
  - 실행 절차와 smoke 검증 결과
  - 테스트: compose up, health, sync, public/admin 흐름

## 9. 문서형 커밋 템플릿(한글 + Lore trailer)

### 페이즈 1 — 계획 문서
```markdown
뉴스레터 플랫폼 MVP의 구현 범위와 검증 기준을 문서로 고정하여 실행 착수 리스크를 줄임

작업 배경
- 현재 저장소에는 실데이터(HTML/PDF)만 존재하고 앱 구조가 비어 있어 구현 전에 계획 합의가 필요했다.

변경 목적
- 개발 범위, 리스크, TDD 순서, 향후 확장 경계를 문서로 고정해 구현 중 추측 비용을 줄인다.

주요 변경 내용
- dev_plan 문서 추가
- PRD 추가
- 테스트 명세 추가

영향 범위
- 이후 모든 구현 작업의 기준 문서

후속 작업 필요사항
- 문서 기준으로 backend → frontend → docker → seed 순으로 구현

Constraint: 현재 실데이터는 Markdown이 아니라 HTML/PDF 파일이다
Rejected: 즉시 구현부터 시작 | 범위와 보안 경계가 고정되지 않아 재작업 위험이 큼
Confidence: high
Scope-risk: narrow
Directive: 문서에 없는 예외 정책을 구현에 임의로 추가하지 말고 먼저 계획에 반영할 것
Tested: 문서 상호 검토 및 산출물 경로 확인
Not-tested: 실제 코드 실행 검증은 아직 수행하지 않음
```

### 페이즈 3 — import/sync
```markdown
실데이터 HTML/PDF를 안전하게 동기화하여 운영 가능한 콘텐츠 인덱스를 확보

작업 배경
- 운영 시작점은 Markdown이 아니라 `Newsletter/output` 의 파일 세트다.

변경 목적
- 파일 스캔, `_debug.html` 제외, checksum 기반 동기화, 경로 검증을 통해 안전한 콘텐츠 인입 경로를 만든다.

주요 변경 내용
- file discovery service 추가
- import/sync service 추가
- path traversal 방지 로직 추가
- 관련 TDD 테스트 추가

영향 범위
- 관리자 import 기능
- public 목록 데이터 정확성

후속 작업 필요사항
- public 상세 렌더링 API 연결

Constraint: 허용 루트 밖 파일 접근은 절대 허용할 수 없다
Rejected: 파일 경로를 DB에 절대경로 그대로 저장 | 환경 이동성과 보안성이 떨어짐
Confidence: high
Scope-risk: moderate
Directive: `_debug.html` 제외 정책을 변경하려면 공개 노출 영향과 테스트를 함께 수정할 것
Tested: unit/import integration 테스트
Not-tested: 대용량 파일셋 성능 최적화
```
