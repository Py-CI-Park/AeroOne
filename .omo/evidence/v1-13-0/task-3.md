# Task 3 — 데이터베이스 기준 자격증명 일괄 회전

## 결과

- 상태: 완료
- 실제 운영 환경 파일과 데이터베이스: 변경하지 않음
- 검증 대상: synthetic 임시 작업공간과 임시 SQLite 데이터베이스
- 비밀값·암호 해시·원문 환경값 출력: 0건

## 구현 계약

- 모든 사용자 암호를 CSPRNG 자격증명 번들에서 회전하고 `password_changed_at`을 갱신한다.
- 각 사용자의 `session_version`은 정확히 1 증가시키며 역할, 활성 상태, 사용자 수는 보존한다.
- 모든 `UserSessionActivity` 행을 같은 데이터베이스 트랜잭션에서 제거한다.
- 동일 회전 번들의 재실행은 사용자 상태를 다시 변경하지 않는다.
- 루트와 backend 환경 파일의 허용 키 및 일치 여부, canonical SQLite 경로를 엄격하게 검사한다.
- current-user DPAPI로 recovery, journal, pending 환경 파일, 자격증명 번들을 보호한다.
- pending 환경 파일을 원자적으로 승격하고 이전 환경 파일은 제한 ACL의 quarantine과 manifest로 보존한다.
- `before_db_commit`, `after_db_commit`, `after_root_env_promote`, `before_credentials_promote` failpoint에서 중단한 뒤 forward-only 방식으로 재개한다.

## TDD 및 자동 검증

- 핵심 회전 코어 RED: 의도한 미구현 실패 1건 확인
- DPAPI 경계 RED: 의도한 미구현 실패 1건 확인
- PowerShell 오케스트레이터 RED: 초기 비정상 종료 확인
- focused 회전 테스트: 17 passed
- backend 전체 회귀 테스트: 285 passed
- Ruff: 통과
- basedpyright 오류 게이트: 0 errors, 0 warnings, 0 notes
- basedpyright 전체 경고 감사: 0 errors, 50 warnings
- no-excuse 검사: 위반 0건
- Python compileall: 통과
- PowerShell parser: 오류 0건
- git diff check: 통과

## Synthetic 수동 QA

- dry-run 반환 코드: 0
- 최초 실행 반환 코드: 0
- 동일 번들 재실행 반환 코드: 0
- dry-run, 실행, 재실행 상태 검증: 모두 성공
- 금지 출력 탐지: 0건
- 임시 환경 정리: 성공
- 잔존 회전 프로세스: 0
- 생성된 listener: 0

## 보안 및 복구 검증

- current-user DPAPI 왕복 복호화 성공
- 새 관리자 자격증명으로 HTTP 로그인 성공
- 이전 관리자 암호로 HTTP 로그인 거부
- 이전 JWT 서명 검증 거부
- 읽기 전용 데이터베이스 및 행 수 drift에서 환경 파일 변경 전 중단
- 허용되지 않은 비밀 키, 작업공간 루트, 옵션 및 failpoint 거부
- 제한 ACL이 손상된 pending 파일의 재개 거부
- quarantine manifest 항목 수와 보존 만료 시각 검증
- 출력 경계 및 파일 대상 비밀 노출 검사 통과

## 의도적으로 수행하지 않은 항목

- 실제 운영 자격증명 회전은 Task 4에서 서비스를 중지한 뒤 수행한다.
- 별도 Windows 사용자 계정에서의 DPAPI 복호화는 수행하지 않았다. current-user 범위의 성공과 보호 경계는 검증했다.

## Round 1 차단점 교정 후 최종 재검증

최초 완료 판정 뒤 독립 검토에서 확인된 15개 차단점은 [`task-3-review-fix.md`](task-3-review-fix.md)의 RED→GREEN 근거로 교정했습니다.

- focused: 56 passed, 3 warnings
- backend 전체: 324 passed, 3 warnings
- frontend credential literal 회귀: 313 passed / 66 files, typecheck와 production build PASS
- Ruff: PASS
- basedpyright production+새 migration test: 0 errors, 0 warnings, 0 notes
- PowerShell: 13개 ps1/psm1 AST PASS, 함수 최대 43줄, main 432줄
- 문서 상대 링크 11개 PASS, 공개 고정 credential literal과 JWT-like literal 0건
- 실제 운영 환경/DB는 회전하지 않았으며 production 기본 경로를 실행하지 않았다.

375px 실제 렌더의 부분 증거와 미완료 visual gate는 [`task-3-visual-qa/README.md`](task-3-visual-qa/README.md)에 별도로 기록했습니다.
