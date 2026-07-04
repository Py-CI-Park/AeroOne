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

개발 환경의 자격 증명은 `backend/.env` 에서 읽어옵니다.

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

> `change-me` 같은 기본값은 `production` 또는 `closed_network` 모드에서 부팅 시 즉시 거부됩니다. 자세한 분기는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) §11.2 참고.

`/admin/*` 경로의 모든 mutation 과 sync 기능을 다른 신뢰 경계 뒤로 이동시키지 않은 채 인증을 제거하지 마세요. 이 정책을 우회하거나 완화하는 변경은 [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §6 보안 관련 변경 시 추가 절차를 따릅니다.


## 1.10.0 운영 메모

- **NSA 권한 부여**: `/nsa` 는 더 이상 `0000` 비밀번호 가림막을 쓰지 않습니다. 대상 사용자 또는 그룹에 `collections.nsa.read` 권한을 부여하고, 같은 대상에 `collection:nsa` ResourceGrant 를 추가해야 목록·본문·AI 검색이 열립니다.
- **모듈 활성화**: `service_modules.required_permission` 이 설정된 카드는 로그인 사용자의 유효 권한에 따라 노출됩니다. 카드가 보이지 않으면 active/visibility 뿐 아니라 required_permission 과 그룹 권한을 함께 확인합니다.
- **자산 진단**: 관리자 콘솔의 자산/config-health 는 `_database`, storage, 썸네일, DB/마이그레이션 상태를 확인하는 1차 점검표입니다. 누락 경로는 배포 ZIP 또는 운영 백업에서 복구합니다.
- **접속자 보존/purge**: 접속자 대시보드는 로그인/세션 활동과 익명 IP 읽음 추적만 metadata-only 로 보존합니다. purge 는 감사 로그를 남기고, 현장 개인정보 보존 정책에 맞춰 주기적으로 실행합니다.
