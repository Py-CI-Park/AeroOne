# 관리자 인증 정책

공개 뉴스레터 열람은 로그인이 필요하지 않습니다.

관리자 로그인이 반드시 필요한 이유는 관리자 화면이 다음과 같이 로컬 뉴스레터 데이터와 운영 설정을 변경할 수 있기 때문입니다.

- Import / Sync
- 뉴스레터 신규 생성·수정·게시 상태 변경·일괄 게시/보관
- soft delete / 비활성 상태 변경
- 썸네일 업로드
- 카테고리·태그 mutation
- 대시보드 `service_modules` 카드 상태·링크·정렬 변경
- 사용자/RBAC 권한 변경과 비밀번호 재설정
- 읽음 기록 purge
- 백업 생성·검증·다운로드

1.8.0 부터 서버 권한 경계는 단일 관리자 여부가 아니라 `admin/user/pending` 역할과 권한 키 조합으로 판단합니다. 새 관리자 API 는 `require_permission(...)` 과 `require_csrf` 를 분리해 조합하며, 감사 대상 mutation 은 같은 DB transaction 안에 `admin_audit_events` 를 남깁니다. 감사 로그에는 비밀번호, 토큰, CSRF, AI prompt/answer/snippet 을 저장하지 않습니다.

개발 환경의 자격 증명은 `backend/.env` 에서 읽어옵니다. 시드 또는 서버 시작 전에 setup마다 고유한 관리자 비밀번호를 생성합니다.

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<setup별로 생성한 고유 랜덤 값>
```

> `setup.bat` 과 `setup_offline.bat` 은 실행할 때마다 새 48자 hexadecimal 관리자 비밀번호를 생성하고 기존 `.env` 는 `.bak` 으로 보관합니다. 수동 개발 setup은 [`local-dev.md`](local-dev.md)의 생성 절차를 사용하며, 기존 `ADMIN_PASSWORD`를 덮어쓰지 않도록 거부합니다.
>
> 빈 값과 퇴역한 공용 기본값은 유효한 bootstrap 비밀번호가 아닙니다. `production` 또는 `closed_network` 모드는 부팅 시 이를 거부합니다. 기존 DB에서 설정된 관리자 계정의 hash가 그 퇴역값과 일치하면, 유효한 setup별 bootstrap 비밀번호가 있을 때 로그인 검증 전에 새 값으로 교체하고 `session_version`을 올려 기존 세션을 무효화합니다. 유효한 bootstrap 비밀번호가 없으면 해당 legacy 로그인을 거부합니다. 자세한 모드 분기는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) §11.2 참고.

`/admin/*` 경로의 모든 mutation 과 sync 기능을 다른 신뢰 경계 뒤로 이동시키지 않은 채 인증을 제거하지 마세요. 이 정책을 우회하거나 완화하는 변경은 [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §6 보안 관련 변경 시 추가 절차를 따릅니다.


## 1.11.0 운영 메모

- **같은 origin 으로 접속**: 운영자와 사용자는 로그인과 관리자 콘솔을 모두 frontend 주소 `http://<host>:29501` 에서 엽니다. LAN 클라이언트도 브라우저에 backend 주소(`:18437`)를 직접 넣지 않습니다.
- **same-origin relay**: 브라우저의 인증/관리자 호출은 `/api/frontend/auth/*`, `/api/frontend/admin/*` 로 들어오고, frontend 서버가 backend 로 relay 합니다. 이 구조가 폐쇄망 LAN 의 cross-origin cookie/CORS 취약 지점을 줄입니다.
- **탭형 관리자 콘솔**: `/admin` 은 모듈, 사용자, RBAC, 세션, 시스템, 분류, 검색, 백업, 감사 탭으로 나뉩니다. RBAC 탭에서 권한 체크박스, ResourceGrant 드롭다운, `NSA 열람권 부여` 프리셋, 사용자/그룹 선택기를 사용합니다.
- **통합 검색**: 관리자 콘솔 검색 탭은 same-origin `/api/frontend/search/unified` 경로를 사용합니다.

## 1.12.1 운영 메모

- **헤더 신원/로그아웃**: 로그인 후 헤더에는 `로그인: <username>` 과 `로그아웃` 버튼이 표시됩니다. 로그아웃은 쿠키를 제거하고 `login_events.status='logout'` 행을 남기며, 현재 토큰의 `user_session_activity` 행을 제거합니다(과거 세션 행은 보존 정책/purge 대상).
- **계정 등록 UX**: 사용자 생성은 접속 아이디(`username`)와 임시 비밀번호만 필수입니다. 이름(`display_name`)과 사용자 이메일은 선택 정보이며, `users.display_name` 은 Alembic `20260707_0008_user_display_name` 에서 nullable 컬럼으로 추가됩니다.
- **사용자별 권한 수정**: 사용자 탭은 계정을 목록으로 보여주고 각 행의 **권한 수정** 버튼을 눌렀을 때 직접 권한 체크박스를 펼칩니다. 저장하면 해당 사용자 `session_version` 이 올라가 stale 권한 세션이 만료됩니다.
- **감사/세션 가독성**: 감사 로그는 페이지 단위로 나뉘고 필터 초기화·현재 결과 CSV 내보내기를 제공합니다. 세션 탭은 로그인/로그아웃 이벤트, 마지막 갱신 시각, `자동 새로고침(15초)` 를 명시합니다.

## 1.12.0 운영 메모

- **권한 이해 카탈로그**: 권한 체크박스·리소스 권한 부여 select·RBAC 매트릭스가 `admin.rbac.manage` 같은 원시 키 대신 한국어 라벨·설명·카테고리를 함께 보여줍니다. 표시 전용이며 백엔드 인가가 정본입니다 — 리소스 권한 부여는 여전히 collection 안전 키만 허용하고 전역 `admin.*` 는 부여할 수 없습니다.
- **감사 탭**: 감사 로그는 백업 탭이 아니라 전용 `감사` 탭에서 작업자·액션·상태·기간으로 검색·필터하고 CSV 로 내보냅니다.
- **세션 자동 새로고침**: 세션 탭의 `자동 새로고침` 토글은 기본 꺼짐이며, 켜면 15초마다 접속자 정보만 갱신합니다(전체 콘솔을 다시 부르지 않음). 시간 표기는 상대+절대 병기이고 로그인 이벤트 목록은 페이지 단위로 나뉩니다.
- **탭 단축키/도움말**: 입력 필드가 아닌 곳에서 숫자 키 1~9 로 탭을 전환하고, 콘솔 상단 접이식 도움말에서 각 탭의 역할을 확인합니다.

## 1.10.0 운영 메모

- **NSA 권한 부여**: `/nsa` 는 더 이상 `0000` 비밀번호 가림막을 쓰지 않습니다. 서버는 관리자이거나, 대상 사용자/그룹에 전역 `collections.nsa.read`(또는 legacy `search.nsa.read`) 권한이나 `collection:nsa` ResourceGrant 중 하나가 있으면 목록·본문·AI 검색을 엽니다.
- **모듈 활성화**: `service_modules.required_permission` 이 설정된 카드는 로그인 사용자의 유효 권한에 따라 노출됩니다. 카드가 보이지 않으면 active/visibility 뿐 아니라 required_permission 과 그룹 권한을 함께 확인합니다.
- **자산 진단**: 관리자 콘솔의 자산/config-health 는 `_database`, storage, 썸네일, DB/마이그레이션 상태를 확인하는 1차 점검표입니다. 누락 경로는 배포 ZIP 또는 운영 백업에서 복구합니다.
- **접속자 보존/purge**: 접속자 대시보드는 로그인/세션 활동과 익명 IP 읽음 추적만 metadata-only 로 보존합니다. purge 는 감사 로그를 남기고, 현장 개인정보 보존 정책에 맞춰 주기적으로 실행합니다.
