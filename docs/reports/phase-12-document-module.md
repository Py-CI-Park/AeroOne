# 단계 12 — 문서(Document) 보관소 모듈

- 분류: **minor (`1.3.0`)** — 신규 읽기 전용 모듈
- dev 브랜치: `1.3.0-dev`
- 진입점: 대시보드 → "Document" 카드 / 헤더 네비 "Document" → `/documents`

---

## 1. 배경

대시보드의 `Document` 카드는 1.2.0 까지 placeholder("Coming soon", 비활성)로만 존재했다. 운영자 요구는 명확했다 — `_database/document/` 폴더에 HTML 문서를 떨궈 두면 **서버 재시작 없이** 화면에서 골라 볼 수 있어야 하고, 문서가 여러 개면 목록으로 고르며, **하위 폴더로 분류해 넣으면 그 폴더 구조를 인식해 트리로 구분**해야 한다. 즉 단일 보고서인 민간 항공기(civil_aircraft)와 달리, 다수 문서 + 폴더 구분 + 선택이라는 차원이 더해진다.

## 2. 선택한 접근

신규 `documents` 모듈을 두고, civil_aircraft 의 단일 엔드포인트를 **목록 API + 콘텐츠 API 두 개로 확장**했다. `GET /api/v1/documents/list` 가 `_database/document` 를 `rglob('*.html')` 로 재귀 수집해 `{path, name, folder}` 목록을 주고(폐쇄망 정책대로 `_debug.html` 제외, `(folder, name)` 안정 정렬), `GET /api/v1/documents/content/html?path=<rel>` 가 선택한 1개를 **뉴스레터/보고서와 똑같은 `HtmlRenderService` sanitize**(외부 `<link>`/외부 `src` 차단, 인라인 스크립트 보존)로 렌더한다. 경로는 `StorageService.resolve_external_relative_path`(= `ensure_within_root` path-guard)로 `_database/document` 밖 접근을 차단하고, `.html` 아님/`_debug`/디렉토리 이탈을 각각 404/404/400 으로 막는다.

프런트는 `/documents` 페이지(`force-dynamic` SSR)가 목록을 받아 클라이언트 `DocumentsWorkspace` 로 넘기고, 좌측에 **접을 수 있는 폴더 트리**(중첩 폴더 = 재귀 렌더, 기본 전체 펼침) + 우측에 `HtmlViewer`(샌드박스 iframe)를 둔다. 첫 문서를 자동 선택하고, 선택이 바뀌면 콘텐츠만 브라우저 fetch 로 즉시 교체(풀 페이지 리로드 회피)한다. 대시보드 카드를 active 로 전환하고 헤더 네비에 "Document" 항목을 추가했다(상단 active/coming 카운트는 `MODULES` 파생이라 자동 갱신). `document_root` 는 기본값(`./_database/document`)을 가진 신규 `.env` 키라 기존 `.env` 와 호환된다.

## 3. 검토하고 제외한 대안

- **(a) civil_aircraft 모듈에 문서 기능을 끼워넣기** — civil 은 "최신 단일 보고서" 시맨틱이고 document 는 "다수 + 폴더 선택" 이라 엔드포인트 계약이 달라 별도 모듈로 분리.
- **(b) 콘텐츠를 `?path=` 쿼리로 서버 렌더(SSR)** — 선택마다 풀 페이지 내비가 일어나 트리 펼침 상태가 초기화된다. 트리 상태 보존 + 즉시 교체를 위해 콘텐츠만 브라우저 fetch 로 분리.
- **(c) 폴더를 평면 그룹 헤딩으로만 표시** — 운영자가 "폴더 트리" 를 명시 선택했고 중첩 폴더 접기/펼치기가 필요해 재귀 트리로 구현.
- **(d) 목록까지 한 번에 콘텐츠 동봉** — 문서가 늘면 응답이 비대해지고 첫 로드가 느려져, 목록은 메타만/콘텐츠는 선택 시 별도 요청으로 분리.

## 4. 코드 (진실 원천)

| 영역 | 위치 |
|---|---|
| document 설정 | `backend/app/core/config.py` (`document_root='./_database/document'`, `document_root_path`) |
| 목록/콘텐츠 엔드포인트 | `backend/app/modules/documents/api/public.py` (`/list` `_discover_documents`, `/content/html` path-guard + `HtmlRenderService` 재사용 + 404/400 가드) |
| 라우터 등록 | `backend/app/main.py` (`/api/v1/documents`) |
| 프런트 페이지 | `frontend/app/documents/page.tsx`(목록 fetch + 빈상태 폴백) |
| 폴더 트리 + 뷰어 | `frontend/components/documents/documents-workspace.tsx`(`'use client'`, 재귀 트리 + `HtmlViewer`) |
| 서버/브라우저 fetch | `frontend/lib/api.ts` (`fetchDocumentList`, `fetchDocumentContent`), 타입 `frontend/lib/types.ts`(`DocumentListItem`) |
| 대시보드 카드 / 네비 | `frontend/app/page.tsx`(active 카드 + 파생 카운트), `frontend/components/layout/app-shell.tsx`(네비 항목) |
| 배치 와이어링 | `setup.bat` / `setup_offline.bat`(`DOCUMENT_ROOT=` env + `_database\document` mkdir) |

## 5. 회귀 방지

- 백엔드: `backend/tests/integration/test_documents_api.py` (하위폴더 포함·`_debug` 제외·정렬 / 빈 목록 / sanitize+CSP / 404 / traversal 400 — 5건), `backend/tests/conftest.py` (tmp `document_root` 격리 — 실 폴더 미접근), `backend/tests/unit/shared/test_windows_batch_scripts.py` (setup 이 `_database/document` 생성 + `DOCUMENT_ROOT=` env 기록 단언).
- 프런트: `frontend/tests/app/documents-page.test.tsx` (워크스페이스 렌더 / 빈상태 / 실패 폴백 3건), `frontend/tests/components/documents-workspace.test.tsx` (트리 렌더 / 자동선택 로드 / 선택 교체 / 폴더 접기 4건), `frontend/tests/app/home-page.test.tsx` (Document active 카드 + 파생 카운트 `3 active · 2 coming soon`).

## 6. 검증 게이트

- backend `pytest tests`: **104 passed**
- frontend Vitest: **88 passed**
- `tsc --noEmit`: exit 0
- 라이브 HTTP(127.0.0.1, 실 샘플 3건 — 루트 2 + `항공/` 1): `/documents/list` 폴더 그룹·정렬 정확, `/content/html` 200+CSP, 미존재 404 / 비-html 404 / `.html` 디렉토리 이탈 400. SSR `/documents` 에 트리(folder/doc testid)·네비·대시보드 active 카드(`3 active · 2 coming soon`) 확인.

## 7. 후속 / 연관

- 폴더가 비어 있으면(문서 0) `/documents` 는 "표시할 문서가 없습니다" 폴백과 함께 `_database/document` 안내를 보여준다 — civil_aircraft 의 빈상태 패턴과 동일.
- 문서 sanitize/격리는 뉴스레터([단계 11](phase-11-civil-aircraft-report.md))와 같은 `HtmlRenderService` + 샌드박스 iframe 한 자리에 모여 있어, 폐쇄망 순도 정책이 세 모듈(newsletter/reports/documents)에 단일 원천으로 적용된다.
