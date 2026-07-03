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
