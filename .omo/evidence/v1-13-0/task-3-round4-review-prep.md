# Task 3 Round 4 리뷰 준비 노트

- 작성: 2026-07-12, GJC ultragoal G001
- 목적: backend/frontend 게이트 대기 중 확보한 리뷰 surface·발견 사항. Round 4 5-lane review와 커밋 전 수정 목록의 근거.

## 변경 표면 (hotfix `.worktrees/1.12.3-hotfix`, 63 dirty)

| 구분 | 개수 | 비고 |
|---|---|---|
| backend-src | 8 | 수정 5: credential_rotation_transaction.py, main.py, credential_rotation_artifacts.py, credential_rotation_ledger.py, sqlite_recovery.py / 신규 3: core/maintenance_gate.py, core/maintenance_gate_bootstrap.py, operations/sqlite_recovery_snapshot.py |
| backend-test | 24 | credential_rotation_* integration/unit 다수 |
| scripts | 25 | Rotation.*.psm1 모듈(수정 10 + 신규 11), rotate/view 스크립트, setup/start .bat, windows/*maintenance_gate* 신규 2 |
| docs | 6 | README.md, CLOSED_NETWORK_GUIDE.md, INDEX.md, phase-22, phase-8, runbook/credential-rotation.md |

## 신규 backend 소스 구조 파악

- `core/maintenance_gate.py`: `acquire_backend_maintenance_gate(workspace_root)`가 subprocess lease(PowerShell hold gate)로 회전과 backend 부팅을 interlock. 테스트 fixture(bypass/probe) 분기, `atexit`로 lease 해제. probe workspace는 `resolve(strict=True)`로 검증.
- `core/maintenance_gate_bootstrap.py`: import 시 `acquire_backend_maintenance_gate()`를 호출하는 3줄 부트스트랩. main.py가 config/DB import 전에 먼저 import(§app-entry gate 테스트 대응).
- `operations/sqlite_recovery_snapshot.py`: `snapshot_connection`/`snapshot_bytes`가 read-only URI(`mode=ro`)로 SQLite를 in-memory 직렬화하고 bytearray를 zeroize. `RecoveryErrorCode` StrEnum + `SqliteRecoveryError`.

## 발견 사항 (커밋 전 처리 필요)

### F-DOC-1 (blocking): credential-rotation.md §7 검증 근거 수치 stale
- 현재 문서: `backend full 347 passed, credential focused 79 passed, frontend 313 passed / 66 files`.
- Round 4 실제: focused **85 passed**, backend full **369 tests** 기준. 347/79는 Round 4 이전 라운드 수치.
- 조치: backend full + frontend 게이트 최종 수치 확정 후, §7을 Round 4 최종 counts로 갱신하고 커밋에 포함. Round 2 리뷰의 documentation-drift 재발 방지.
- 주의: §7 "1.13.0-dev" 라벨도 실제 검증 worktree(1.12.3-hotfix/main)와 표기 정합성 재확인.

## 리뷰 레인 계획 (게이트 green 후)

1. targeted verification: backend full(단독) + frontend(단독) exit code/summary 회수.
2. ai-slop-cleaner: 63 changed files 대상 read-only 스윕. blocking 발견은 executor로 수정.
3. architect review: maintenance gate interlock(부팅/회전 경계), DPAPI purpose 분리, SQLite recovery lock 순서, ordinary-user ACL, atomic replace, clipboard 보안.
4. executor QA/red-team: credential rotation 크래시/재개/lock/quarantine 경계 adversarial 재현. surface=cli/native(PowerShell + pytest). GUI(WPF)는 desktop 수동 QA로 별도.
5. 최종 code review 접기 → 한국어 Round 4 커밋 + Lore trailer, plan/boulder/ledger 동기화.
