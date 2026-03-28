# Test Specification — AeroOne Newsletter / Document Platform MVP

## 1. 목적
이 문서는 뉴스레터 플랫폼 MVP 를 TDD 방식으로 구현하기 위한 테스트 우선 명세이다. 구현 전에 실패하는 테스트를 먼저 작성하고, 최소 구현으로 통과시킨 뒤 리팩터링한다.

## 2. 테스트 원칙
1. 서비스 계층 로직은 라우터보다 먼저 단위 테스트로 고정한다.
2. 파일/경로 보안은 회귀 위험이 높으므로 unit + integration 두 레벨에서 검증한다.
3. 공개 사용자 흐름과 관리자 흐름은 각각 최소 1개 이상의 end-to-end 유사 시나리오를 가진다.
4. 테스트 데이터는 실제 `Newsletter/output` 구조를 모사하되, fixture 는 별도 임시 디렉토리로 분리한다.

## 3. 테스트 계층
- Backend Unit: 순수 함수/서비스/보안 경계
- Backend Integration: DB + API + storage interaction
- Frontend Unit/Integration: component render, form submit, route data handling
- Smoke/E2E-lite: docker compose 기반 건강 상태 및 핵심 화면 검증

## 4. 공통 테스트 데이터 전략
- fixture root: `backend/tests/fixtures/import_root/`
- 샘플 파일:
  - `newsletter_20260206.html`
  - `Aerospace Daily News_20260206.pdf`
  - `sample-welcome.md`
- 테스트용 DB: SQLite 임시 파일 또는 in-memory(마이그레이션 검증용은 파일 기반 권장)
- seed fixture: admin 사용자 1명, category 2개, tag 3개

## 5. Backend TDD 순서

### Phase A — 설정/보안/경로 검증
**대상 파일(예정)**
- `backend/tests/unit/core/test_config.py`
- `backend/tests/unit/shared/test_storage_path_guard.py`
- `backend/tests/unit/auth/test_password_service.py`

**핵심 시나리오**
- `NEWSLETTER_IMPORT_ROOT_CONTAINER` 가 비어 있으면 앱이 시작 실패한다.
- 경로 정규화 후 허용 루트 밖이면 예외를 발생시킨다.
- 관리자 비밀번호 hash/verify 가 일치한다.

**완료 기준**
- 잘못된 경로/설정 입력이 조기 실패한다.

### Phase B — 파일 탐색 및 import/sync
**대상 파일(예정)**
- `backend/tests/unit/newsletter/test_file_discovery_service.py`
- `backend/tests/unit/newsletter/test_asset_pairing.py`
- `backend/tests/unit/newsletter/test_newsletter_import_service.py`
- `backend/tests/integration/test_newsletter_sync_api.py`

**핵심 시나리오**
- html/pdf 파일만 감지하고 `_debug.html` 은 운영 import 대상에서 제외한다.
- `_debug.html` 은 **운영 import 대상에서 제외** 로 고정하고, 발견되더라도 public row 를 만들지 않는다.
- 파일명에서 기본 title 후보와 published_at 을 추출한다.
- 기존 DB 레코드가 있으면 checksum/mtime 기준으로 업데이트한다.
- 파일이 삭제되면 `is_active=false` 또는 sync status 변경 정책이 적용된다.

**완료 기준**
- sync 결과가 created/updated/skipped/deactivated 건수를 반환한다.

### Phase C — 공개 API
**대상 파일(예정)**
- `backend/tests/integration/test_newsletter_public_api.py`

**핵심 시나리오**
- 목록 API 가 page/filter/search 를 지원한다.
- 상세 API 가 slug 기반으로 metadata 와 `available_assets` 를 반환한다.
- 비활성 newsletter 는 공개 API 에 노출되지 않는다.
- HTML/PDF/Markdown 기본 source_type 과 보조 asset 목록이 detail payload 에 올바르게 포함된다.

**완료 기준**
- public API 만으로 목록/상세 UI 구성에 필요한 필드가 충족된다.

### Phase D — 콘텐츠 전달 API
**대상 파일(예정)**
- `backend/tests/unit/newsletter/test_html_render_service.py`
- `backend/tests/unit/newsletter/test_markdown_render_service.py`
- `backend/tests/integration/test_newsletter_content_api.py`
- `backend/tests/integration/test_newsletter_asset_switching_api.py`

**핵심 시나리오**
- HTML sanitize 가 `<script>` 와 `onload` 속성을 제거한다.
- 원격 script/css/resource 는 제거 또는 차단한다.
- HTML content endpoint 가 CSP 헤더를 포함하고 iframe sandbox 전략과 충돌하지 않는다.
- 상대 경로 자산(`./foo.css`, `images/x.png`)은 제거 또는 비활성화된다.
- PDF endpoint 가 `application/pdf` 로 응답한다.
- Markdown endpoint 가 heading/list/link 를 안전 HTML 로 변환한다.

**완료 기준**
- source_type 별 content endpoint 응답이 안전하고 일관된다.

### Phase E — 관리자 인증 및 CRUD
**대상 파일(예정)**
- `backend/tests/integration/test_auth_api.py`
- `backend/tests/integration/test_admin_newsletter_api.py`
- `backend/tests/integration/test_admin_taxonomy_api.py`

**핵심 시나리오**
- 로그인 성공 시 **signed HttpOnly session cookie** 발급
- 인증 없이 관리자 API 호출 시 401
- CSRF 토큰 없이 관리자 mutation API 호출 시 403
- 관리자 CRUD 로 title/description/category/tags/is_active 수정 가능
- thumbnail upload 시 허용 디렉토리에만 저장

**완료 기준**
- 관리자 기능이 public 과 분리된 인증 경계를 가진다.

## 6. Frontend TDD 순서

### Phase F — Public UI
**대상 파일(예정)**
- `frontend/tests/app/newsletters-page.test.tsx`
- `frontend/tests/app/newsletter-detail-page.test.tsx`
- `frontend/tests/components/newsletter-card.test.tsx`
- `frontend/tests/components/html-viewer.test.tsx`
- `frontend/tests/components/pdf-viewer.test.tsx`

**핵심 시나리오**
- 목록 페이지가 API 응답을 카드 목록으로 렌더링한다.
- 검색 입력이 query string 을 구성한다.
- HTML 상세는 iframe viewer, PDF 상세는 pdf viewer, Markdown 상세는 markdown viewer 를 표시한다.
- detail 화면에 존재하는 대체 asset type 전환/다운로드 UI 가 표시된다.
- 썸네일이 없을 때 fallback UI 표시
- `_debug.html` 에서 파생된 항목은 목록에 보이지 않는다.

### Phase G — Admin UI
**대상 파일(예정)**
- `frontend/tests/app/login-page.test.tsx`
- `frontend/tests/app/admin-newsletters-page.test.tsx`
- `frontend/tests/app/admin-newsletter-form.test.tsx`
- `frontend/tests/app/admin-imports-page.test.tsx`

**핵심 시나리오**
- 로그인 폼이 API 호출 후 admin 페이지로 이동
- 관리자 목록에서 편집 링크/상태 표시
- 등록/수정 폼이 category/tag/source_type/is_active 를 처리
- sync 버튼이 결과 통계를 표시

## 7. Smoke / Compose 검증
**대상 절차**
- `docker compose up --build`
- backend health endpoint 확인
- frontend 목록 페이지 접근
- 관리자 로그인 및 sync 1회 실행

**필수 확인 항목**
- backend 가 `/mnt/import/newsletters` 를 읽는다.
- DB 파일과 storage 폴더가 volume 으로 유지된다.
- public/admin 기본 흐름이 브라우저에서 동작한다.
- HTML 상세 응답에 CSP 가 존재하고 iframe sandbox 에 `allow-scripts` 가 없다.

## 8. 관측성과 로그 검증
- sync 시작/종료 로그에 scan root, created/updated/skipped 수치 포함
- path traversal 시도는 warning/error 로 남김
- health endpoint 는 DB 연결, storage root 접근, import root 접근 가능 여부를 반환

## 9. 수용 테스트 시나리오
1. seed 후 public 목록에서 최소 1개의 HTML/PDF/Markdown 항목이 보인다.
2. HTML 상세가 문서처럼 렌더링되고, PDF 상세는 브라우저 뷰어와 다운로드 링크를 제공한다.
3. admin 로그인 후 특정 newsletter 제목/설명을 수정하면 public 상세에 반영된다.
4. import root 에 신규 파일 추가 후 sync 하면 목록에 새 항목이 나타난다.
5. `_debug.html` 파일만 추가된 경우 sync 결과에 public 콘텐츠가 생성되지 않는다.

## 10. 실패 기준
- 허용 루트 밖 파일 접근 가능
- 인증 없는 관리자 수정 가능
- HTML source_type 가 raw script 를 실행함
- source_type 분기 오류로 잘못된 viewer 렌더링
- Docker 환경에서 import root 를 읽지 못함

## 11. 권장 실행 명령(구현 후)
- Backend: `pytest`
- Frontend: `npm test`
- Typecheck: `npm run typecheck`
- Compose smoke: `docker compose up --build`

## 12. 완료 정의
- 핵심 unit/integration/frontend 테스트가 모두 통과한다.
- 수동 smoke 시나리오가 문서화되어 있다.
- 새 기능 추가 전에 대응 테스트 파일이 먼저 존재한다.
