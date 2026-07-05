# 단계 25 — 관리자 콘솔 UX/UI 개선 (권한 이해·감사 로그·세션/목록 인체공학·전역 폴리시) (1.12.0)

## 변경 배경

1.11.0 에서 `/admin` 이 탭형 콘솔로 재설계되고 same-origin 프록시로 인증/관리 표면이 안정화되었습니다. 그러나 실제 운영 관점에서 몇 가지 사용성 부담이 남아 있었습니다.

- 권한은 `admin.rbac.manage` 처럼 원시 키로만 노출돼, 각 권한이 무엇을 의미하는지 운영자가 직관적으로 알기 어려웠습니다.
- 감사 로그는 백업 탭 하단에 최근 몇 건만 보여, 특정 작업자·기간·상태로 이벤트를 추적하거나 근거 자료로 내보내기 어려웠습니다.
- 접속자/세션 대시보드는 절대시간만 표기해 "얼마나 최근인지" 감이 오지 않았고, 최신 상태를 보려면 전체 새로고침으로 15개 관리자 엔드포인트를 모두 다시 불러와야 했으며, 로그인 이벤트가 쌓이면 스크롤만 길어졌습니다.
- 탭 이동은 마우스/화살표 키에 의존했고, 각 탭이 무엇을 하는지 안내가 없었습니다.

## 선택한 접근

100% 프론트엔드 전용 개선으로, 백엔드 인가 정본·스키마·마이그레이션을 전혀 건드리지 않고 이미 클라이언트가 보유한 데이터(권한 목록, RBAC 매트릭스, 감사 이벤트, 접속자 정보)만으로 UX 를 개선했습니다.

- 권한 이해 레이어: `frontend/lib/permission-catalog.ts` 에 30개 권한 키의 한국어 라벨·설명·카테고리 카탈로그와 미지 키 안전 fallback 을 정의하고, 권한 체크박스 그리드·리소스 권한 부여 select·RBAC 매트릭스가 이를 사용해 사람이 읽는 언어로 권한을 표시합니다. RBAC 매트릭스는 배지형 pill 과 "유효 권한 N개 · 관리자 권한 보유/없음" 요약을 덧붙였습니다.
- 감사 로그 전용 탭: 9번째 `감사` 탭과 `admin-audit-section` 을 신설해 작업자·역할·액션·대상·상태·IP 검색, 상태 select, 기간(created_at) 필터, 결정론적 정렬, 필터된 뷰 CSV 내보내기(순수 `buildAuditCsv`, RFC 이스케이프)를 제공합니다. 백업 탭에서는 중복 감사 목록을 제거하고 감사 탭으로의 안내만 남겼습니다.
- 세션/목록 인체공학: `frontend/lib/relative-time.ts` 로 상대시간을 표기하고, `list-filter.tsx` 에 기존 시그니처를 건드리지 않는 opt-in `paginate()`/`ListPagination` 을 추가했습니다. 세션 탭에는 기본 꺼짐 자동 새로고침 토글(켜면 15초마다 `refresh(['connectedUsers'])` 로 접속자 슬라이스만 갱신, 끄거나 언마운트 시 interval 정리)과 로그인 이벤트 페이지네이션을 더했습니다.
- 전역 폴리시: 콘솔 포커스 상태에서 숫자 키 1~9 로 탭을 전환(입력 필드 포커스 시 제외)하고, 각 탭의 역할을 설명하는 접이식 도움말을 상단에 추가했습니다.

## 고려한 제약

- 백엔드/alembic/스키마 무변경. backend `pytest tests` 는 265 passed 그대로, alembic head 는 `0007` 그대로 유지되어야 했습니다. 새 API 를 만들지 않고 기존 refresh 경로/데이터만 사용했습니다.
- 백엔드가 인가 정본이라는 불변식 유지. 카탈로그는 표시 전용이며 shadow 인가원이 되지 않고, 리소스 권한 부여 폼은 여전히 전역 `admin.*` 키를 grant 로 만들 수 없습니다(collection 전용 안전 allowlist + 백엔드 방어선 불변).
- 자동 새로고침은 전체 15개 엔드포인트 fanout 대신 접속자 슬라이스만 스코프 갱신해 폐쇄망 백엔드 부하를 억제했습니다.
- 기존 위젯(list-filter, confirm-dialog, toast-stack 등)과 관리자 콘솔의 slate 팔레트 컨벤션을 재사용하고 병렬 컨벤션을 만들지 않았습니다.

## 제외한 대안

- 백엔드 권한 스키마에 설명 컬럼을 추가하는 방식은 제외했습니다. 표시 전용 개선에 마이그레이션/스키마 변경은 과했고 폐쇄망 회귀 표면을 늘립니다.
- 백엔드 CSV 스트리밍 엔드포인트는 제외했습니다. 프론트-only/새 API 금지 불변식을 위반하고 인증/프록시/백엔드 테스트 표면을 늘립니다.
- 관리자 콘솔 전체를 디자인 토큰으로 다크 테마화하는 작업은 이번 범위에서 제외했습니다. 신규 코드만 토큰으로 바꾸면 기존 8개 섹션의 slate 팔레트와 병렬 컨벤션이 생기므로, 반응형 정리와 팔레트 일관성만 유지하고 전면 토큰 마이그레이션은 별도 후속으로 남겼습니다.
- ListFilter 에 페이지네이션을 강제 병합하는 방식은 제외했습니다. 기존 8개 호출부의 회귀 표면을 키우므로 opt-in 별도 컴포넌트로 분리했습니다.

## 검증 결과

- backend: `pytest tests` **265 passed** (백엔드 로직 무변경, 버전 문자열/대시보드 테스트 단언만 1.12.0 으로 갱신).
- frontend: Vitest **310 passed / 65 files**.
- typecheck: `tsc --noEmit` 성공.
- build: `next build` 성공.
- alembic head: `0007` (스키마 변경 없음).
- 스토리별 architect 리뷰: G001~G004 모두 3레인(아키텍처/제품/코드) CLEAR + APPROVE. G002 는 1회 반복(코드 WATCH 2 LOW 테스트 정밀 → 강화 → 재검토 APPROVE).
- executor red-team: 권한 카탈로그 fallback·grant select authz 경계, 감사 CSV 이스케이프·필터 조합·백업 중복 제거, paginate 클램핑·상대시간 경계·자동 새로고침 스코프/cleanup·로그인 페이지네이션, 탭 숫자 단축키/온보딩을 대상으로 통과.
- QA artifacts: `artifacts/qa/1.12.0-admin-ux/`.

## 영향 범위

- backend: 버전 문자열(`config.py`)과 대시보드 버전 테스트 단언만. 인가/스키마/마이그레이션 무변경.
- frontend: `frontend/lib/{permission-catalog,relative-time,changelog}.ts`, `frontend/components/admin/admin-console-tabs.tsx`, `frontend/components/admin/sections/{admin-audit,admin-rbac,admin-sessions,admin-backups}-section.tsx`, `frontend/components/admin/widgets/{permission-checkbox-grid,resource-grant-form,list-filter}.tsx`.
- 운영 문서: `README.md`, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/admin-auth.md`, `docs/reports/INDEX.md`.
- 버전 표기: `backend/app/core/config.py`, `frontend/lib/changelog.ts`, 헤더 버전 테스트.

## 후속

- 관리자 콘솔 전체의 다크 테마 디자인 토큰 마이그레이션(신규/기존 섹션 일괄)을 별도 스토리로 검토합니다.
- 페이지네이션이 필요한 대용량 목록(예: 사용자·백업)이 늘면 동일 `paginate`/`ListPagination` 을 재사용해 확장합니다.
- 감사 CSV 외에 서버측 대용량 감사 export 가 필요해지면 same-origin 프록시 경계를 유지한 채 별도 검토합니다.
