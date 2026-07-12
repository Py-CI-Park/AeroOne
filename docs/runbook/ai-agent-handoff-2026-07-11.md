# AI 에이전트 핸드오프 — v1.13.0 Task 3 검증 중단 지점과 전체 재개 절차

- 작성일: 2026-07-11
- 대상: Codex, Claude Code, GJC, 기타 coding agent, 사람 검토자
- root branch/HEAD: `1.13.0-dev@034bd03`
- hotfix worktree/HEAD: `.worktrees/1.12.3-hotfix`, local `main@d6628dd`
- 현재 milestone: Task 3 Round 4 구현 완료, 최종 검증 미완료
- 릴리스 상태: 1.12.3 미배포, 1.13.0 PR 미생성

---

## 0. 새 에이전트가 가장 먼저 알아야 할 것

1. `1.13.0-dev` root에서 바로 제품 코드를 수정하지 않는다.
2. 현재 Task 3 제품 변경은 `.worktrees/1.12.3-hotfix`의 63개 dirty 경로에 있다.
3. 이 dirty 상태는 사용자 작업이므로 reset/checkout/clean/rebase 금지다.
4. Task 3 focused 85개는 PASS했지만 backend full 최종 실행은 worker 사용량 종료로 실패 node를 잃었다.
5. Task 3이 backend/frontend/WPF/review까지 모두 PASS하기 전 Task 4 실제 credential rotation을 실행하지 않는다.
6. production `.env`, canonical DB, `%USERPROFILE%/AeroOne-secure`는 아직 건드리지 않았다.
7. 다른 worktree의 pytest/node/PowerShell process가 실행 중일 수 있으므로 경로와 parent tree를 확인하지 않고 종료하지 않는다.

---

## 1. 이번 핸드오프 문서 세트

| 문서 | 역할 | 반드시 읽는 시점 |
|---|---|---|
| [전체 계획](../../.omo/plans/v1-13-0-operator-experience-plan.md) | Task 1~27, F1~F6의 원문 acceptance/QA/commit 정책 | 시작 전 |
| [개발 상태 상세 보고서](../reports/v1-13-0-development-status-2026-07-11.md) | 완료 작업, Round 1~4 검토, 63개 변경 지도, 남은 모든 단계 | 시작 전 |
| [Task 3 current evidence](../../.omo/evidence/v1-13-0/task-3-current-status.md) | 유효/무효 테스트와 정확한 중단점 | backend 재실행 전 |
| [Task 1 evidence](../../.omo/evidence/v1-13-0/task-1.md) | 1.12.2 exact asset 봉쇄 | containment 검토 시 |
| [Task 2 evidence](../../.omo/evidence/v1-13-0/task-2.md) | historical 28 assets containment | release 검토 시 |
| [Round 1 review](../../.omo/evidence/v1-13-0/task-3-review-round-1.md) | 초기 보안 차단점 | Task 3 review 시 |
| [Round 2 review](../../.omo/evidence/v1-13-0/task-3-review-round-2.md) | crash/env/lock/docs 차단점 | Task 3 review 시 |
| [Round 3 review](../../.omo/evidence/v1-13-0/task-3-review-round-3.md) | ordinary ACL, immutable recovery, TOCTOU, clipboard 차단점 | Task 3 review 시 |
| `docs/runbook/credential-rotation.md` | hotfix worktree에 미커밋으로 존재하는 운영자용 회전/복구/viewer 계약 | 실제 Task 4 전 |
| [`AGENTS.md`](../../AGENTS.md) | 저장소 위험 신호, commit/PR/release 규칙 | 모든 변경 전 |

2026-07-09 핸드오프는 1.13.0 제품 구현 전 상태를 설명하는 과거 이력이다. 현재 재개에는 이 문서를 사용한다.

---

## 2. 현재 Git/worktree 상태

| 위치 | branch/HEAD | 상태 |
|---|---|---|
| root | `1.13.0-dev@034bd03` | origin과 동기화. `.omo` plan/evidence/ledger와 최신 문서가 dirty |
| hotfix | local `main@18b4ba9` | origin/main보다 4 commit 앞섬, Round 4 커밋 완료(dirty 0). push 안 함 |
| review-r3 | detached `d6628dd` | Round 3 review 흔적 |
| qa-r3 | detached `d6628dd` | Round 3 runtime QA 흔적 |
| dashboard-enhancements | 별도 feature | unrelated, 건드리지 않음 |
| release-1.7.0 | detached | unrelated, 건드리지 않음 |

hotfix의 네 commit:

1. `ca9ce3e` — 노출 가능 자격증명을 DB 기준으로 일괄 회전
2. `2259fdc` — recovery/integrity 경계 보강
3. `d6628dd` — 중단 안전 운영 경계 보강
4. `18b4ba9` — 복원-가드·멱등 재개·journal v2 토폴로지로 Round 4 완성 (2026-07-12 커밋)

Round 4는 `18b4ba9`로 커밋됐다. 남은 유일 산출물은 자율 수행 불가한 WPF viewer 인터랙티브 desktop 시각 QA이며, 그 사람 QA 뒤 Task 3 최종 sign-off → Task 4 순서다. 상세: [Round 4 게이트 결과](../../.omo/evidence/v1-13-0/task-3-round4-gate-results.md).

---

## 3. 지금까지 완료된 작업

| Task | 결과 |
|---:|---|
| 1 | 1.12.2 unsafe ZIP/SHA exact pair 제거, release/tag/body 보존, old URL 404 |
| 2 | 46 release/15 ZIP 중앙-directory-only 감사, 사용자 승인 후 historical 14 pairs/28 assets 삭제, 12 warnings |
| 3 구현 | ordinary-user ACL, atomic replace, runtime-relative provenance, optional root env, immutable recovery, maintenance gate, restore writer lock, clipboard 보안, bounded timeout, neutral artifact names, topology repair, LOC refactor 완료 |

Task 3 상세 RED→GREEN과 파일 목록은 [상태 보고서 §6~§8](../reports/v1-13-0-development-status-2026-07-11.md)에 있다.

---

## 4. 정확한 중단 지점

| Gate | 상태 |
|---|---|
| Task 3 static quality | PASS — Ruff, basedpyright 0/0, compile/import, PS AST, LOC, links, secret/stale scan |
| focused credential rotation | PASS — 85 passed, 3 warnings, 1979.95s |
| backend full first run | 367 passed, 2 failed — 두 worktree fixture 수정으로 superseded |
| fixture 단독 | PASS — 2 passed, 20.27s |
| backend full final run | 약 25분에 failure marker 1, worker usage limit 종료, node/summary 없음 |
| frontend | 미완료 |
| WPF desktop QA | 미완료 |
| Round 4 review/debug audit | 미완료 |
| Task 3 commit | 미완료 |

마지막 full run을 PASS로 해석하지 않는다. node가 없으므로 처음부터 다시 실행한다.

---

## 5. 재개 절차

### 5.1 저장소 확인

```powershell
Set-Location D:/Chanil_Park/Project/Programming/AeroOne
git status --short --branch
git worktree list --porcelain

Set-Location .worktrees/1.12.3-hotfix
git status --short
git rev-list --left-right --count origin/main...HEAD
git log --oneline origin/main..HEAD
git diff --check
```

기대값은 hotfix `0 3`, 세 선행 commit, 약 63 dirty 경로다. 값이 다르면 먼저 변경 소유권과 외부 수정 여부를 진단한다.

### 5.2 backend full

```powershell
Set-Location D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/backend
$env:PYTHONPATH='.'
& 'D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe' `
  -m pytest tests -vv --tb=short -p no:cacheprovider
```

- 75분 outer timeout과 process-tree cleanup을 둔다.
- 실제 child exit code와 pytest summary를 둘 다 확인한다.
- stdout/stderr를 보존해 실패 nodeid를 잃지 않는다.
- 실패 node는 단독 RED→최소 수정→단독 GREEN→focused 85→full 순으로 재검증한다.
- unrelated worktree process를 종료하지 않는다.

### 5.3 frontend

backend 종료 뒤 순차 실행한다. hotfix에는 `node_modules`가 없으므로 root의 검증된 binary/NODE_PATH를 사용하거나 clean install을 명시적으로 수행한다. 이전 병렬 시도는 제품 실행 전 정리됐으며 vitest worker 잔류는 0이다.

필수 결과:

- Vitest full PASS
- typecheck PASS
- production build PASS
- owned node/vitest process 0

### 5.4 WPF viewer

- `computer-use` skill을 읽는다.
- synthetic masked bundle만 사용한다.
- secret 표시/복사 버튼을 누르지 않는다.
- accessibility tree, screenshot, keyboard/focus, 580-height fit을 확인한다.
- clipboard 원상복구와 창/PID/temp 0을 확인한다.

### 5.5 evidence/review/commit

1. `task-3-current-status.md`를 최종 evidence로 갱신한다.
2. goal/code/security/hands-on QA/context 5-lane review를 실행한다.
3. 3-hypothesis runtime audit를 실행한다.
4. 모든 lane이 unconditional PASS인지 확인한다.
5. debug journal/review worktree/temp/listener를 정리한다.
6. 한국어 제목·본문·7개 Lore trailer로 Round 4 commit을 만든다.
7. Task 3 plan checkbox와 boulder/ledger를 동기화한다.

Task 4는 이 절차 완료 뒤에만 시작한다.

---

## 6. Task 4 이후 실행 순서

| Wave | Tasks | 목적 |
|---|---|---|
| 0 | 4 | 실제 workspace credential/session rotation과 quarantine |
| 1 | 5~9 | public verifier/builder, Sandbox, internal bundle, Next 15.2.9, 1.12.3 release |
| merge | 10 | 1.12.3 ancestry를 dev에 no-ff merge |
| foundation | 11~15 | design, browser QA harness, backend/admin/session foundations |
| user | 16~19 | account/nav/login/activity |
| admin | 20~24 | Overview/users/sessions/module access UX |
| final | 25~27 | docs, full QA, 1.13.0 metadata |
| verification | F1~F6 | plan/code/manual/scope/security audit, dev push, PR body |

각 Task의 상세 acceptance와 Must NOT은 [상태 보고서 §4·§9](../reports/v1-13-0-development-status-2026-07-11.md)와 [계획 원문](../../.omo/plans/v1-13-0-operator-experience-plan.md)을 따른다.

---

## 7. 환경 차단점

| 차단점 | 처리 |
|---|---|
| Goal/worker usage limit | 새 세션에서 문서를 읽고 재개. 작업 파일은 보존됨 |
| Windows Sandbox absent | 관리자 PowerShell에서 feature 활성화 필요 |
| Sandbox `RestartNeeded=true` | boulder/ledger checkpoint 후 사용자 reboot 승인 필요. 자동 reboot 금지 |
| hotfix node_modules absent | backend 뒤 root verified tools 또는 clean install로 frontend 순차 검증 |
| production trust absent | Task 7의 정상 fail-closed baseline. real trust/bundle은 범위 밖 |

---

## 8. 절대 하지 말아야 할 것

- hotfix dirty 파일 reset/checkout/clean/rebase/squash
- Task 3 PASS 전 Task 4 실행
- production secret/hash/DB row/clipboard plaintext 출력
- public ZIP에 env/DB/storage/_database/agent/dev state 포함
- unrelated worktree process 종료
- 자동 host reboot
- 1.13.0 main merge/tag/release/PR 생성
- evidence 없이 테스트 실패를 pre-existing/fixture로 단정

---

## 9. 완료 보고 형식

다음 에이전트는 매 milestone마다 아래를 표로 남긴다.

| 필드 | 내용 |
|---|---|
| 기준 branch/HEAD | 검증한 정확한 revision |
| 변경 파일 | source/test/docs 구분 |
| RED | 실패 node와 원인 |
| GREEN | 명령, pass/fail count, 시간 |
| manual QA | 실제 환경과 cleanup |
| review | lane별 verdict |
| external mutation | credential/release/push 여부 |
| remaining blocker | 다음 Task를 막는 조건 |

이 형식과 전체 계획을 유지하면 다른 에이전트가 세션이 달라도 Task 3 중단점부터 안전하게 재개할 수 있다.
