# 단계 22 — 관리자 전용 노출·헤더 정리·모듈 DB 관리 강화·비밀번호 변경 (1.9.0)

## 변경 배경

1.8.0 에서 관리자 콘솔과 `service_modules` DB 대시보드를 도입한 뒤, 운영자가 다음을 요청했다.

- 헤더의 `Admin` 메뉴를 다크 토글 옆으로 옮기고 순서를 **다크 · 사용법 · Admin** 으로 정리.
- `개발중` 섹션 라벨을 영어로 통일.
- 일반 사용자 대시보드에서 **개발중(Development)·Coming soon 카드와 Admin 메뉴를 숨기고**, 서버 실행자(관리자)에게만 노출.
- 관리자 콘솔에서 위 노출과 대시보드 모듈을 직접 관리(추가·삭제 포함).
- 당시 배포의 초기 관리자 자격은 보안상 원문을 남기지 않고, 콘솔에서 직접 변경.
- 실행 중이던 대시보드/뉴스레터의 500 오류 해결.

또한 운영 중 다음 두 500 오류가 보고되었다.

- `GET /api/v1/newsletters/calendar` → 500
- `GET /api/v1/admin/service-modules/public` → 500 (대시보드가 fallback 목록 표시)

## 진단 — 두 500 오류의 실제 원인

실행 DB(`backend/data/aeroone.db`)가 마이그레이션 `20260703_0004` 이전(`20260613_0003`)에 멈춰 있었다. 즉 `service_modules` 테이블과 `newsletters.status`/`is_active` 관련 컬럼이 없어 모든 관련 쿼리가 500 이었다. `start_offline.bat` 은 마이그레이션을 돌리지 않기 때문에, 코드만 갱신하고 `setup_offline.bat` 재실행을 건너뛰면 재현된다.

즉시 조치로 실행 DB 를 백업 후 `alembic upgrade head` 로 올려 두 오류를 해소했고, 재발 방지를 위해 `start_offline.bat` 에 마이그레이션 preflight 를 추가했다.

## 선택한 접근

### 노출 대상(visibility) 모델

`service_modules` 에 `visibility`(`public`|`admin`) 컬럼을 추가했다. 공개 열람 서비스(newsletter/civil-aircraft/document/nsa)는 `public`, 개발중·Coming soon 모듈은 `admin` 으로 시드한다.

- `GET /api/v1/admin/service-modules/public` 은 optional 세션을 확인해 관리자면 전체, 아니면 `public` + 활성 모듈만 반환한다.
- 대시보드 SSR(`frontend/app/page.tsx`)은 `resolveIsAdmin()` 으로 서버에서 관리자 여부를 판단해 fallback 경로에서도 `admin` 전용 카드를 노출하지 않는다.
- 헤더의 `Admin` 링크는 클라이언트 섬 `AdminNavLink` 가 `/api/v1/auth/me` 로 세션을 확인해 관리자에게만 렌더한다. `AppShell` 은 서버 컴포넌트로 유지(테스트/렌더 호환).

### 헤더 순서

`AppShell` 우측 클러스터를 **테마 토글 → 사용법 → Admin** 순서로 정리하고, `Admin` 을 주 네비게이션에서 제거했다.

### 모듈 DB 관리 강화

- `POST /admin/service-modules`(생성), `DELETE /admin/service-modules/{id}`(삭제)를 permission + CSRF + same-transaction audit 로 추가.
- 관리자 콘솔에서 카드별 `visibility` 선택, 신규 모듈 추가 폼, 삭제 버튼을 제공.

### 관리자 비밀번호 변경

`POST /api/v1/auth/change-password`(현재 비밀번호 확인 + 8자 이상 새 비밀번호)를 추가했다. 변경 시 `session_version` 을 증가시켜 다른 세션을 무효화하고, 현재 세션은 새 쿠키를 재발급해 유지한다. 콘솔에 **관리자 계정 / 비밀번호** 섹션을 추가했다. 당시 배포의 초기 자격 원문은 보안상 redaction했으며, 노출 사고 대응은 [`../runbook/credential-rotation.md`](../runbook/credential-rotation.md)를 따른다.

### start_offline 마이그레이션 preflight

`start_offline.bat` 이 백엔드 기동 전에 `ensure_db_state.py` 분기 → `alembic upgrade head`(또는 `stamp head`)를 수행한다. `DATABASE_URL` 을 명시적으로 넘기고 `setlocal` 로 서브루틴에 가둬 실행 창에 새지 않게 했다. 이미 head 면 no-op 이라 안전하다.

## 고려한 제약

- AeroOne 폐쇄망 Windows/SQLite modular monolith, same-origin proxy 원칙 유지.
- `APP_ENV`/`ensure_db_state` 종료 코드/LAN 기본 바인딩/packaging 제외 목록 위험 신호를 건드리지 않음.
- 관리자 mutation 은 permission + CSRF + same-transaction audit 유지.
- 당시 고정 초기 비밀번호는 8자였기 때문에 `closed_network` 의 `ADMIN_PASSWORD` 강도 검증(≥12)과 별개였다. 원문은 보안상 redaction했으며 콘솔 변경은 자체 최소 길이(8)만 강제한다.

## 제외한 대안

- `AppShell` 을 async 서버 컴포넌트로 만들어 관리자 여부를 자체 확인 → React Testing Library 가 async 서버 컴포넌트를 렌더하지 못해 폐기하고, 클라이언트 섬 `AdminNavLink` 로 분리.
- 노출을 `status`/`section` 으로 유추 → 관리자가 직접 조정 가능한 명시 `visibility` 컬럼 채택.

## 검증 결과

- `alembic upgrade head`(sqlite in-memory, `20260703_0005` 포함) 통과.
- backend `pytest tests -q` → **181 passed** (경고 3). 신규: 익명 공개 노출, 관리자 전체 노출, 모듈 생성/삭제, 자가 비밀번호 변경.
- frontend `tsc --noEmit` 통과, Vitest **206 passed / 47 files**, `next build` 통과.
- 라이브 스모크(재기동 후): 익명 `/service-modules/public` → 4개(`newsletter,civil-aircraft,document,nsa`), 당시 관리자 자격 로그인 → 200, 관리자 `/service-modules/public` → 10개. 브라우저 익명 대시보드에 `Admin`·개발중·Coming soon 미노출 확인.

## 영향 범위

Backend auth/admin API + Alembic 스키마, frontend 헤더/대시보드/관리자 콘솔/help, `start_offline.bat`, 운영·릴리즈 문서. `APP_ENV`, `ensure_db_state` 종료 코드, LAN 기본 바인딩, `offline_package.bat` 제외 목록은 변경하지 않았다.

## 후속 작업

- `closed_network` 신규 설치는 `setup_offline.bat`이 초기 시드용 랜덤 `ADMIN_PASSWORD`를 환경 파일에 발급하므로 설치 직후 확인. 기존 DB의 비밀번호 해시·세션은 setup 재실행으로 교체되지 않으며 자격 증명 회전 런북을 사용.
- 물리 폐쇄망 PC 에서 ZIP 설치 + `start_offline.bat` preflight 실동작 확인은 운영자 게이트로 남김.
