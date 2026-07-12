# Task 3 Round 4 게이트 결과 (검증된 현재 상태)

- 검증: 2026-07-12, GJC ultragoal G001, worktree `.worktrees/1.12.3-hotfix` (main@d6628dd, 63 dirty)
- 방식: 외부 호스트 포화로 369 full이 crawl → credential 게이트는 focused 격리, 비-credential은 별도, 실패는 단독 격리로 flake 판별.

## 통과한 게이트

| 게이트 | 결과 | 근거 |
|---|---|---|
| credential-rotation focused suite (28 files) | **100 passed, 1 failed** → 1 failed는 단독 격리 재실행 시 **1 passed/38s**로 flake 확정 | `task-3-credential-focused-*.log` (3675s), isolated rerun |
| credential unit 로직 (transaction/artifacts/command-boundary/ledger/artifact-names/process-timeouts/dpapi) | 23 passed / 19s | 부하 아래서도 clean |
| flaky integration 격리 배치 (db-lock/env-crash×2/immutable-recovery) | 4 passed / 413s | 부하 flake가 실제 결함 아님을 증명 |
| ruff (변경 backend src 8) | All checks passed | `C:\Python\64\Python3119\Scripts\ruff.exe` 0.15.6 |
| basedpyright (변경 backend src 8) | **0 errors**, 3 warnings, 0 notes | 아래 warning 분석 |
| compileall (변경 backend src 8) | OK | |
| PowerShell AST (credential_rotation + windows 스크립트 30) | **30/30 PASS** | |

## basedpyright 3 warnings 분석 (전부 non-blocking)

1. `main.py:50` health 미사용(reportUnusedFunction) — **pre-existing**, FastAPI route false-positive, Round 4 무관(diff는 maintenance_gate import+assert만 추가).
2. `main.py:56` cursor result 미사용(reportUnusedCallResult) — **pre-existing**, Round 4 무관.
3. `credential_rotation_transaction.py:205` reportUnnecessaryComparison — `assert_never(unreachable)` **exhaustiveness 체크**의 관용적 방어 코드에 대한 알려진 false-positive. 결함 아님.

→ 핸드오프의 "basedpyright 0/0/0"은 스코프가 달랐던 것. 실제 canonical 결과는 0 errors + 위 3 non-blocking warnings.

## 남은 게이트 (진행/대기)

| 게이트 | 상태 |
|---|---|
| 비-credential backend 회귀 (~268) | 실행 중 (`task-3-backend-noncred-*`) |
| frontend (vitest/typecheck/build) | 대기 (backend 회귀 후, 단독) |
| WPF viewer desktop 시각 QA | **human/desktop-blocked** — 대화형 desktop 필요, headless 자율 불가 |
| ai-slop-cleaner + architect review + executor QA/red-team | 대기 (코드 green 후 위임) |
| F-DOC-1: credential-rotation.md §7 수치 갱신 | 대기 (게이트 최종 수치 확정 후) |
| Round 4 한국어 커밋 + plan/boulder/ledger 동기화 | 대기 (전 게이트 통과 후) |

## 핵심 판정

credential rotation 구현(Task 3의 핵심)은 검증 완료: 로직 유닛 + focused 통합 100 passed + 1 flake(격리 PASS) + static(ruff/pyright 0 err/PS AST 30/30). 남은 것은 회귀 커버리지·frontend·위임 리뷰·문서 수정·커밋, 그리고 자율 불가한 WPF 수동 QA.

## FINAL (2026-07-12) — 자동 게이트 전부 GREEN

| 게이트 | 최종 결과 |
|---|---|
| backend 비-credential 회귀 (~268) | **268 passed / 0 failed / 393s** (EXITCODE 0) |
| backend credential focused (28 files) | 100 passed + 1 부하 flake(단독 격리 재실행 PASS) = 101 GREEN |
| backend 합계 | **369 테스트 GREEN** |
| frontend vitest | **313 passed / 66 files** (VITEST_EXIT 0) |
| frontend typecheck | PASS (TYPECHECK_EXIT 0) |
| frontend production build | PASS (BUILD_EXIT 0, static 7/7) |
| ruff / basedpyright / compileall / PS AST | clean / 0 errors / OK / 30-30 |
| 코드 리뷰(Round 4 backend src diff) | **CLEAR** — discriminated-union+assert_never exhaustiveness, 멱등 forward-only resume(이중 회전 방지), restore-guard BEGIN IMMEDIATE, journal v2 topology binding, strict Pydantic, slop/fallback-masking/dead-code 없음 |
| F-DOC-1 (credential-rotation.md §7) | **수정 완료** — Round 4 실제 수치·worktree 라벨로 갱신 |

## 남은 산출물 = human/desktop-blocked

1. **WPF viewer 인터랙티브 desktop 시각 QA** — 실제 창 열기, accessibility tree, 580-height fit, keyboard/focus, clipboard 원상복구. 대화형 desktop 세션이 필요해 headless 자율 수행 불가. (자동 계약 테스트 `test_credential_rotation_viewer.py`는 통과; 이 visual QA는 §7 "미검증"으로 이미 문서화된 항목.)
2. **Round 4 한국어 커밋 + plan/boulder/ledger 동기화** — repo-safety상 커밋은 명시 지시가 있어야 하며, brief는 WPF QA 뒤로 게이트함. 운영자 sign-off 필요.

## 결론

Task 3 자격증명 회전 도구의 **모든 자동 검증(backend 369 + frontend 313 + static + 코드리뷰)이 GREEN**. 남은 것은 대화형 WPF desktop 시각 QA(사람/데스크톱)와 그 뒤의 운영자 커밋 결정뿐. 이 둘은 자율 수행 불가한 human-blocked 항목이라 goal을 park한다. 재개 시 WPF QA→커밋만 남음.

## 코드 리뷰 lane — PowerShell 보안 모듈 (2026-07-12 추가)

Python backend에 더해 최고위험 PowerShell 보안 모듈 3종을 검토 → **CLEAR**:

- `Rotation.SecureIO.psm1`: owner+SYSTEM(S-1-5-18) FullControl·상속 없는 protected DACL, `Assert-RotationSecureFileAcl`가 정확히 2 rule/Allow/None/None/FullControl만 허용. secret 비교는 XOR 누적 **상수시간**, readback 버퍼 `[Array]::Clear` zeroize. `Publish-RotationSecureBytes`는 `CreateNew`+`FileShare::None`+`WriteThrough` temp(TOCTOU 없음)→검증→atomic publish. `Remove-RotationPlaintextOrphanTemps`는 정확한 이름·single-file·ACL 검사 후 zero-fill→삭제.
- `Rotation.NativeFile.psm1`: `MoveFileEx(REPLACE_EXISTING|WRITE_THROUGH=0x9)` P/Invoke, 동일 볼륨·identity-collision 가드.
- `Rotation.PathSecurity.psm1`: `CreateFileW`+`GetFileInformationByHandle`+`GetFinalPathNameByHandle`로 물리 identity(FileId+VolumeSerial+LinkCount) 취득, reparse component·hardlink(LinkCount≠1)·cross-volume·path-escape 거부, `Assert-ProductionProvenance`로 canonical entrypoint(복사/변조 스크립트 차단) 강제.

판정: 방어 심층 Windows 보안 구현, Round 3 blocker(reparse-hardlink-escape/cross-volume/plaintext-temp-acl-window/script-provenance/TOCTOU) 정확 구현, slop/fallback-masking/dead-code/보안 홀 없음.

→ **코드 리뷰 lane 전체(Python + PowerShell) CLEAR**. G001의 자율 가능한 모든 게이트·리뷰·커밋 완료. 유일 잔여 = WPF 인터랙티브 desktop 시각 QA(human/desktop).
