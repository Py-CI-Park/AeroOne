# 단계 24 — 관리자 콘솔 UX 재설계·same-origin 인증/관리 프록시 통합 (1.11.0)

## 변경 배경

1.10.0 에서 RBAC/NSA 서버측 접근제어와 사용자별 메뉴 힌트가 정리되었지만, 브라우저의 로그인·관리자 API 호출은 여전히 배포 환경에 따라 frontend origin 과 backend origin 사이의 쿠키/CORS 경계에 민감했습니다. 폐쇄망 LAN 에서는 사용자가 `http://<host>:29501` 로 접속하는 것이 자연스러운데, 브라우저가 backend origin 을 직접 향하면 SameSite/cookie/CORS 조합이 흔들릴 수 있었습니다.

동시에 관리자 콘솔은 기능이 빠르게 늘면서 사용자, 그룹, 권한, 세션, 백업, 검색, 분류, 모듈 관리가 한 화면에 밀집했습니다. 운영자는 더 많은 권한 작업을 수행해야 하므로 탭 구조, 입력 위젯, 목록 상태, 접근성, 실패 상태 회복력을 함께 정리해야 했습니다.

## 선택한 접근

- 브라우저 로그인과 관리자 CRUD 를 same-origin `/api/frontend/auth/*`, `/api/frontend/admin/*` 경로로 통일했습니다. 사용자는 로그인과 `/admin` 을 모두 같은 frontend origin(`http://<host>:29501`) 으로 열고, Next.js route handler 가 backend loopback/API origin 으로 relay 합니다.
- 통합 검색은 관리자 API 와 충돌하지 않도록 전용 `/api/frontend/search/unified` 경로로 분리했습니다.
- backend ResourceGrant 검증은 defense-in-depth 로 강화해 global, unknown, malformed key 를 거부합니다. 1.10.0 의 backend/API authority 와 기존 권한 불변식은 유지했습니다.
- `/admin` 을 모듈/사용자/RBAC/세션/시스템/분류/검색/백업 탭으로 분리하고, 각 섹션 컴포넌트가 자기 목록 상태와 입력 상태를 담당하도록 정리했습니다.
- RBAC UI 에 권한 체크박스 그리드, 리소스 권한 드롭다운 폼, `NSA 열람권 부여` 프리셋, 사용자/그룹 선택기를 추가했습니다.
- 모듈 관리는 정의된 값 기반 select 와 validation 을 사용하고, 성공/실패 피드백은 toast 로 표준화했습니다.
- 관리자 목록 전반에 검색, 정렬, 결과 수, 빈 상태, 로딩 상태, 오류 상태를 일관되게 적용했습니다.
- 탭은 ARIA Tabs 패턴과 키보드 이동을 지원하도록 구현했습니다.
- 로그인 진입은 backend/config 일부가 degraded 인 상황에서도 운영자가 원인을 확인하고 다시 시도할 수 있도록 회복력을 보강했습니다.

## 고려한 제약

- 폐쇄망 기본 사용자는 backend origin 을 외우거나 브라우저에 직접 입력하지 않아야 합니다. 운영 안내와 코드 모두 `http://<host>:29501` 단일 frontend origin 을 기준으로 맞췄습니다.
- SameSite=Lax, HttpOnly session cookie, CSRF, 관리자 권한 요구 조건은 완화하지 않았습니다.
- 관리자 콘솔은 기능이 많아졌지만 새 외부 UI 의존성을 추가하지 않고 기존 디자인 토큰과 Testing Library 기반 검증 패턴을 유지했습니다.
- 1.10.0 의 ResourceGrant/NSA 접근제어 정책은 권한 모델의 기준선이므로, 이번 단계는 UX/proxy 안정화와 입력 방어 보강으로 제한했습니다.

## 제외한 대안

- 브라우저가 backend origin(`http://<host>:18437`) 을 직접 호출하도록 운영 가이드를 강제하는 방식은 제외했습니다. LAN 클라이언트와 쿠키 경계를 계속 운영자 실수에 노출합니다.
- CORS 허용 범위를 넓혀 우회하는 방식은 제외했습니다. same-origin BFF 프록시가 폐쇄망 배포의 더 단순하고 안전한 경계입니다.
- 관리자 기능별로 별도 페이지를 흩뿌리는 방식은 제외했습니다. 운영자는 `/admin` 한 곳에서 탭으로 이동하는 구조가 더 예측 가능합니다.
- ResourceGrant 의 느슨한 문자열 허용은 제외했습니다. unknown/malformed key 를 early reject 해야 권한 상승 회귀를 줄일 수 있습니다.

## 검증 결과

- backend: `pytest tests` **265 passed**.
- frontend: Vitest **265 passed / 56 files**.
- typecheck: `tsc --noEmit` 성공.
- build: `next build` 성공.
- 단계별 architect 리뷰: same-origin admin/auth 프록시와 ResourceGrant 방어선에 대해 CLEAR.
- executor red-team: `/api/frontend/auth/*`, `/api/frontend/admin/*`, `/api/frontend/search/unified`, 관리자 탭 키보드 이동, RBAC/ResourceGrant 입력, 목록 상태, degraded login 진입을 대상으로 통과.
- QA artifacts: `artifacts/qa/1.11.0-admin-proxy/`.

## 영향 범위

- backend: ResourceGrant key 검증과 관리자/API 권한 방어선.
- frontend: `/admin` 탭형 콘솔, 관리자 섹션 컴포넌트, RBAC 입력 위젯, same-origin auth/admin/search 프록시 route, degraded login entry.
- 운영 문서: `README.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/INDEX.md`, `docs/reports/INDEX.md`, `docs/runbook/admin-auth.md`.
- 버전 표기: `backend/app/core/config.py`, `frontend/lib/changelog.ts`, 헤더 버전 테스트.

## 후속

- 관리자 탭별 사용 빈도와 실패 toast 를 운영 로그/현장 피드백으로 관찰해 기본 정렬과 help copy 를 조정합니다.
- 권한 프리셋이 NSA 외 컬렉션에도 필요해지면 ResourceGrant 정책을 유지한 채 preset 목록만 확장합니다.
- 외부 IdP 또는 HTTPS 종단이 도입되면 same-origin BFF 경계를 유지하면서 쿠키 secure 정책 전환만 별도 검토합니다.
