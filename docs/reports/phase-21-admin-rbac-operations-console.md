# Phase 21 — 관리자 RBAC·운영 콘솔·DB 관리 기반 (1.8.0)

## 배경

운영자가 대시보드 카드 재분류, Coming soon 비활성화, 뉴스레터 다운로드/자산 상태 확인 같은 변경을 코드 릴리즈 없이 처리할 수 있어야 했다. Open WebUI 벤치마크에서 확인한 `admin/user/pending` 역할, additive permissions/groups, 관리자 설정, 사용량/피드백 분석 패턴 중 AeroOne 폐쇄망 문서 열람 시스템에 맞는 부분만 채택했다.

## 핵심 변경

- `users` 를 `admin/user/pending` 역할과 `session_version` 기반 세션 무효화로 확장하고, `groups`, `user_permissions`, `group_permissions`, `resource_grants` 를 추가했다.
- 관리자 mutation 은 `require_permission(...)` + `require_csrf` 조합으로 보호한다. 감사 대상 변경은 같은 SQLAlchemy transaction 안에 `admin_audit_events` 를 기록하며, 비밀번호·토큰·CSRF·AI prompt/answer/snippet 은 저장하지 않는다.
- `service_modules` 를 대시보드 카드의 DB 원천으로 추가하고 현재 카드 10개를 그대로 seed 했다. DB/table 오류 시 프런트는 내장 fallback 목록과 visible degraded banner 를 표시한다.
- `/admin` 홈 콘솔은 버전/모드, DB, 최신 뉴스레터, 자산 상태, 읽음 요약, AI 상태, 최근 감사 로그, 사용자/RBAC 생성·수정, 그룹 권한, 대시보드 모듈 편집, 카테고리/태그 정렬·비활성화, 통합 검색, 백업 생성·검증을 한 화면에서 제공한다.
- 뉴스레터 운영은 `draft/scheduled/published/archived` 상태, 자산 health, 검색/상태 필터, 일괄 게시/보관, Sync 권한·CSRF·감사로 확장했다.
- 백업은 `storage/admin_backups` 아래 manifest+sha256 ZIP 으로 생성·검증하며 public/static root 에 두지 않는다. 파일명은 microsecond timestamp + random suffix 로 충돌을 피하고, 임시 ZIP 작성 후 검증 가능한 최종 경로로 이동한다. 복원 실행은 비범위지만 `/restore/dry-run` 으로 manifest/schema/checksum 기반 사전 점검만 제공한다.
- AI 운영 로그는 `ai_request_logs` 에 metadata-only 로 남긴다. 질문/답변/문서 snippet/citation 원문은 로그에 저장하지 않는다.

## 코드 위치

- Backend RBAC/Audit/API: `backend/app/modules/admin/`, `backend/app/modules/auth/dependencies.py`
- Migration: `backend/alembic/versions/20260703_0004_admin_rbac_operations.py`
- Dashboard DB source: `backend/app/modules/admin/api.py` (`/service-modules/public`), `frontend/app/page.tsx`
- Admin UI: `frontend/app/admin/page.tsx`, `frontend/components/admin/admin-home-console.tsx`, `frontend/components/admin/admin-newsletter-list.tsx`
- Newsletter status/assets/bulk: `backend/app/modules/newsletter/`, `frontend/components/admin/newsletter-form.tsx`

## 검증

- Backend: `pytest tests -q` → **177 passed** (경고 3, 실패 0)
- Frontend: `npm test` → **205 passed** (47 files)
- Frontend typecheck: `npm run typecheck` → exit 0
- Frontend build: `npm run build` → Next.js production build 성공
- Browser smoke: production dashboard `v1.8.0`, 8 active/2 coming soon, `/admin` 콘솔, 백업 생성·검증·감사 로그 확인

## 비범위

- OAuth/LDAP/SCIM, Open WebUI plugin/tool/code-execution, 개인 API key, broad admin chat-body access 는 제외한다.
- Restore 실행은 제외한다. 1.8.0 에서는 백업 생성·검증·다운로드와 dry-run 사전 점검까지만 제공한다.
