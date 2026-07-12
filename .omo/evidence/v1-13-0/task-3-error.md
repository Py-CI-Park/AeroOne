# Task 3 — 실패 경로 증적

## 기대 실패 검증

- 읽기 전용 데이터베이스: 비정상 종료, 환경 승격 없음
- 사용자 행 수 drift: 데이터베이스 트랜잭션 롤백, 환경 승격 없음
- 알 수 없는 비밀성 환경 키: 준비 단계에서 거부
- 허용되지 않은 작업공간 루트: 실행 전 거부
- 공개되지 않은 옵션 및 failpoint: 매개변수 바인딩 단계에서 거부
- 제한 ACL이 손상된 pending 파일: 재개 전 거부, 환경 승격 없음
- `before_db_commit`: 데이터베이스 commit 전 중단, 재개 후 1회만 회전
- 나머지 세 failpoint: 각 영속 단계 이후 중단, 재개 후 중복 회전 없이 완료

## 구현 중 발견하고 해결한 실패

- Windows PowerShell 5.1의 표준 입력 BOM 때문에 JSON 경계가 거부되던 문제를 입력 경계에서 정확히 제거했다.
- DPAPI 형식 로딩 누락으로 보호 호출이 실패하던 문제를 필요한 런타임 어셈블리 로딩으로 해결했다.
- manifest의 두 번째 원자 갱신이 백업 없이 실패하던 문제를 제한 ACL의 이전 버전 백업을 유지하도록 해결했다.
- ACL 손상 재개가 환경 파일 격리 뒤에 거부되던 순서를 모든 승격·격리 전 검증으로 이동했다.
- synthetic QA의 ACL 검사 대상 전달 오류를 테스트 전용 환경 경계로 교정했다.

## 미해결 오류

- 없음

## 민감정보 원칙

- 본 증적에는 암호, JWT 비밀, 암호 해시, 환경 파일 원문, DPAPI payload 또는 실제 운영 데이터가 포함되지 않는다.

## Round 1 독립 검토 이후 상태 — superseded

위의 “미해결 오류 없음”은 최초 구현 commit `ca9ce3e`의 자체 검증 시점 기록입니다. 이후 독립 `task-3-review-round-1.md`가 corrupt pending resume 시 active `.env`를 먼저 격리하는 P0와 15개 차단 범위를 재현했으므로 최초 판정은 승인 근거로 사용하지 않습니다.

후속 교정은 [`task-3-review-fix.md`](task-3-review-fix.md)에 blocker별 RED→GREEN 근거로 기록했습니다. 최종 상태는 다음과 같습니다.

- Task3 focused: 56 passed, 실패 0
- backend 전체: 324 passed, 실패 0
- production changed Python: Ruff PASS, basedpyright 0 errors / 0 warnings
- PowerShell: 13개 파일 AST PASS, 함수 최대 43줄
- 공개 고정 credential literal: 저장소 전체 0건
- 실제 운영 `.env`, `backend\.env`, `backend\data\aeroone.db`: 작업 시작 이전 수정시각 유지
- visual QA: 375px 부분 증거만 확보했으며 1280px·console zero·dual reviewer는 미완료로 명시
