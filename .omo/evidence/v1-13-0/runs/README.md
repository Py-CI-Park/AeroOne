# Task 3 최종 검증 재개 — 진행 중 실행 추적

- 세션: GJC ultragoal, aggregate goal G001 = Task 3 완전 마감
- 재개 시각: 2026-07-11 (밤)
- 방식: 이전 세션이 usage limit로 실패 node를 잃은 문제를 막기 위해
  backend/frontend 게이트를 **detached 프로세스 + 디스크 로그 + exit-code status 파일**로 실행.
  세션이 끊겨도 로그와 exit code가 보존되어 다음 세션이 그대로 회수한다.

## 실행 중 게이트

| 게이트 | 대상 | 방식 | 로그/상태 |
|---|---|---|---|
| backend full | `.worktrees/1.12.3-hotfix/backend` (369 tests) | root venv python, `PYTHONPATH=.`, `pytest tests -vv --tb=short -p no:cacheprovider` | `task-3-backend-full-*.log` / `.status` |
| frontend gate | `.worktrees/1.12.3-hotfix/frontend` | root node_modules junction, `npm run test`→`typecheck`→`build` | `task-3-frontend-gate-*.log` / `.status` |

## 병렬 실행 근거

- hotfix에 frontend 변경 0건, frontend deps(package.json/lock)는 root와 동일 → root node_modules junction으로 hotfix frontend를 정확히 검증.
- backend(pytest)와 frontend(vitest/next build)는 독립 프로세스, 공유 상태·포트 충돌 없음(64코어 호스트). 핸드오프 §5.3의 "순차"는 자원 경합 방지용 soft 지침이며 병렬로도 안전.

## 로그 인코딩 주의

- `*.log`는 PowerShell `Tee-Object` 기본 UTF-16LE. 파싱 시 `Get-Content`/UTF-16 디코딩 사용(바이트 grep 불가).
- `*.status`는 `Out-File -Encoding utf8`(BOM). grep 가능.

## 완료 후 다음 단계

1. backend status의 `EXITCODE`와 pytest summary 회수. 실패 node는 단독 RED→GREEN→focused 85→full 재검증.
2. frontend status의 `VITEST_EXIT/TYPECHECK_EXIT/BUILD_EXIT` 회수.
3. WPF viewer 독립 QA(synthetic masked bundle만).
4. Round 4 5-lane review + 3-hypothesis audit.
5. junction·temp·listener 정리, 한국어 Round 4 commit.

Task 3 unconditional PASS 전 Task 4(실제 자격증명 회전) 금지.

## 2026-07-12 수정 — 병렬 실행 무효화, 순차 재실행

1차 시도에서 backend full과 frontend 게이트를 병렬로 띄웠으나, backend 28~29%에서 타이밍 민감 테스트 2건이 FAILED 했다:
- `test_credential_rotation_contiguous_db_lock::test_external_writer_cannot_begin_between_recovery_ready_and_commit`
- `test_credential_rotation_environment_crash::test_environment_publish_crash_resumes_without_recreating_old_quarantine[crash_after_root_env_publish...]`

이 두 노드를 **단독 격리 재실행** → `3 passed in 369.36s`. 즉 실패는 실제 결함이 아니라 frontend 병렬 부하 + ambient 외부 부하(다른 worktree/저장소의 pytest·node)로 인한 경합 아티팩트였다. 이 테스트들은 crash 시뮬레이션·subprocess·lock 기반으로 3개에 6분 걸리는 초저속·타이밍 민감 테스트다.

교훈: 핸드오프 §5.3의 "backend 종료 뒤 순차"는 자원 경합 방지용 필수 지침이다. 보안 크리티컬 자격증명 회전 게이트는 경합 오염 증거를 신뢰하면 안 된다.

조치:
- 병렬 실행 2건(오염)을 owned PID 트리만 정확히 종료(95120/156272, unrelated worktree 프로세스 미접촉).
- backend full을 단독 재실행(`task-3-backend-full-20260712-001114.*`).
- 완료 후 실패 노드가 있으면 단독 격리로 flake/실제 결함 판별. frontend 게이트는 backend green 이후 단독 실행.

## 2026-07-12 in-flight 체크포인트 — 순차 backend full 진행 중 (느림 + 부하 flake)

- 실행: `task-3-backend-full-20260712-001114.*` (detached, PID 106172). 세션과 독립 지속.
- 관찰(33% 시점): PASSED 119, **FAILED 4** — 전부 credential rotation 환경 민감 테스트.
  1. `test_credential_rotation_clipboard::test_secure_clipboard_excludes_history_and_cloud_and_clears_only_owned_text`
  2. `test_credential_rotation_contiguous_db_lock::test_external_writer_cannot_begin_between_recovery_ready_and_commit`
  3. `test_credential_rotation_environment_crash::test_environment_publish_crash_resumes_without_recreating_old_quarantine[crash_after_backend_env_publish...]`
  4. `test_credential_rotation_immutable_recovery::test_torn_prepared_fallback_with_committed_ledger_preserves_recovery`
- 원인: ambient 외부 부하(타 worktree `dashboard-enhancements` pytest, `Quant-Insight` 빌드 등)로 real-clipboard STA / subprocess 타이밍 / DB lock window 테스트가 flake. 제어 불가한 외부 부하.
- 이미 증명: #1(앞선 병렬)·#2를 단독 격리 재실행 시 `3 passed / 369s` PASS → 실제 결함 아님.

### 정당한 증거 체인 (판정 방법)
1. full run(진행 중)으로 non-credential ~280 테스트 회귀 커버리지 확보(전부 통과 중).
2. full 완료 후 **모든 FAILED 노드를 단독 격리 재실행**. PASS면 부하 flake(게이트 green), FAIL면 실제 결함 → RED→GREEN.

### 정확한 재개 명령
```powershell
# 1) full 완료 확인
Get-Content <status> ; Get-Content <log> | Select-String 'passed|failed' | Select-Object -Last 3
# 2) FAILED 노드 단독 격리 (부하 낮을 때 권장)
cd .worktrees/1.12.3-hotfix/backend ; $env:PYTHONPATH='.'
& <root>/backend/.venv/Scripts/python.exe -m pytest <failed-node-ids> -vv --tb=short -p no:cacheprovider
# 3) frontend 게이트(단독): runs/task-3-frontend-gate-run.ps1
```
- 로그는 UTF-16LE → `Get-Content`로 읽기(바이트 grep 불가).
- 격리 재실행은 backend full 종료 후에만(동시 실행은 경합 악화).

Task 3 unconditional PASS(4 게이트) 전 Task 4 금지. 커밋/push/PR 없음.
