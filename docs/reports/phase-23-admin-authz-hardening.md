# 단계 23 — 관리자 권한 강화·NSA 서버측 접근제어·접속자 대시보드 (1.10.0)

## 변경 배경

1.9.0 까지는 관리자 콘솔과 대시보드 노출 제어가 정리되었지만, 읽기 권한은 컬렉션별 예외와 화면 가림막에 일부 의존했습니다. 특히 `READ_PERMISSION_BY_PREFIX` 처럼 경로 prefix 에서 권한을 유추하는 방식은 새 컬렉션이 추가될 때 권한 상승 회귀를 만들 수 있어, 컬렉션 읽기 판단을 서버측 단일 정책으로 고정할 필요가 있었습니다.

이번 단계는 RBAC 모델을 사용자·그룹·리소스 권한까지 확장하고, NSA 를 클라이언트 비밀번호 가림막이 아니라 실제 서버측 접근제어 대상으로 바꾼 릴리즈입니다. 동시에 운영자가 문제를 빠르게 판단할 수 있도록 사용자별 메뉴 힌트, 자산/config-health, 접속자 대시보드를 추가했습니다.

## 선택한 접근

- `READ_PERMISSION_BY_PREFIX` 기반 예외를 제거하고 `can_read_collection` 단일 정책을 collections 목록/본문, admin-search, AI 검색 scope 에 공통 적용했습니다.
- NSA 는 `0000` 비밀번호 가림막을 제거하고 로그인 세션의 `collections.nsa.read` 권한과 `collection:nsa` ResourceGrant 를 모두 요구하도록 바꿨습니다.
- `service_modules.required_permission` 을 도입해 모듈 활성화/노출 판단이 사용자별 유효 권한과 맞물리도록 했습니다.
- 세션 응답에는 사용자별 effective-permission 힌트를 제공해 프런트 메뉴와 카드가 서버 권한 상태를 반영하게 했습니다.
- 관리자 콘솔에는 사용자/그룹/리소스 권한 CRUD, RBAC 매트릭스, session_version fanout 을 추가했습니다. 계정은 관리자 생성 흐름만 유지하며 self-registration 은 열지 않았습니다.
- 접속자 대시보드는 로그인/세션 활동과 익명 IP 읽음 추적을 metadata-only 로 집계하고, DB-level debounce 와 감사 가능한 purge 를 사용합니다.

## 고려한 제약

- 폐쇄망 운영에서는 HTTPS/외부 IdP 를 전제할 수 없으므로, 기존 세션 쿠키와 CSRF 경계를 유지했습니다.
- NSA 는 서버측 접근제어가 되었지만 암호화 비밀 저장소는 아닙니다. `_database\nsa\` 원본 HTML 은 운영 파일시스템 정책과 백업 정책의 보호를 받습니다.
- 관리자 콘솔 변경은 self-lockout, 마지막 admin 제거, 감사 로그 redaction 을 계속 fail-closed 로 유지해야 했습니다.
- 접속자 기능은 개인정보 원문 수집을 늘리지 않도록 로그인/세션 메타데이터와 익명 IP 읽음 추적만 사용했습니다.

## 제외한 대안

- 클라이언트 `0000` 비밀번호를 더 복잡하게 만드는 방식은 제외했습니다. 번들에 포함되는 값은 접근제어가 아니라 UI 가림막일 뿐이라 서버측 권한 문제를 해결하지 못합니다.
- 컬렉션별 ad-hoc 권한 분기는 제외했습니다. `can_read_collection` 하나로 모아야 collections/admin-search/AI 간 회귀를 막을 수 있습니다.
- self-registration 은 제외했습니다. 이번 릴리즈의 계정 모델은 관리자 생성 계정만 대상으로 하며, 초대/가입 플로우는 별도 정책 결정이 필요합니다.
- NSA 문서 자체 암호화는 제외했습니다. 이번 범위는 열람 API 접근제어이며, 저장 매체 암호화나 문서 DRM 은 운영 인프라 과제입니다.

## 검증 결과

- backend: `pytest tests` **248 passed**.
- frontend: Vitest **216 passed / 49 files**.
- typecheck: `tsc --noEmit` 성공.
- build: `next build` 성공.
- DB: Alembic upgrade 가 `20260704_0006_service_module_required_permission.py` 와 `20260704_0007_connected_users.py` 까지 통과했습니다.
- 단계별 architect/executor QA gate 가 RBAC escalation, NSA 서버측 403/허용 경계, 사용자별 메뉴 힌트, 자산 진단, 접속자 보존/purge 표면을 확인했습니다.

## 영향 범위

- backend: `backend/app/modules/admin/`, `backend/app/modules/auth/`, `backend/app/modules/collections/`, `backend/app/modules/ai/`, `backend/app/modules/read_tracking/`.
- DB migration: `backend/alembic/versions/20260704_0006_service_module_required_permission.py`, `backend/alembic/versions/20260704_0007_connected_users.py`.
- frontend: `/admin`, `/nsa`, `/ai`, AppShell/menu, 문서 컬렉션/AI scope UI, 접속자·권한 관리 컴포넌트.
- 운영 문서: `README.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/INDEX.md`, `docs/reports/INDEX.md`, `docs/runbook/admin-auth.md`.

## 후속

- NSA 를 암호화 저장소로 다뤄야 하는 요구가 생기면 파일 암호화, 키 보관, 백업 암호화, 운영자 복구 절차를 별도 단계로 설계합니다.
- self-registration 또는 초대 기반 가입은 현재 관리자 생성 계정 정책과 분리해 권한 승인·감사 정책을 먼저 확정합니다.
- 접속자 대시보드의 보존 기간은 현장 개인정보/감사 정책에 맞춰 주기적으로 검토합니다.
