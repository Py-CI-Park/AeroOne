# v1.13.0 개발 상태·검토·잔여 작업 상세 기록

- 기록일: 2026-07-11
- 대상 브랜치: `1.13.0-dev`
- dev 기준 HEAD: `034bd0324af9f69268d25ae605d9be0fd5c632fb`
- Task 3 작업 worktree: `D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix`
- Task 3 worktree HEAD: `d6628dd4679fe004ad68a62bf07789365d51a2dc`
- 문서 성격: 작업 중간 상태 기록. 릴리스 완료 보고서가 아님
- 후속 핸드오프: [`ai-agent-handoff-2026-07-11.md`](../runbook/ai-agent-handoff-2026-07-11.md)
- 전체 결정 완료 계획: [`.omo/plans/v1-13-0-operator-experience-plan.md`](../../.omo/plans/v1-13-0-operator-experience-plan.md)

---

## 0. 한눈에 보는 결론

| 질문 | 현재 답 |
|---|---|
| v1.13.0 개발은 완료됐는가? | 아니오. 정식 계획 기준 Task 1~2만 완료됐고 Task 3은 구현이 거의 끝났지만 최종 검증·Round 4 리뷰·커밋이 남았다. |
| 개발을 자의적으로 멈췄는가? | 아니오. 장기 backend 재검증 중 담당 Goal/worker 사용량 한도에 도달했다. |
| 현재 제품 변경은 어디에 있는가? | `1.13.0-dev`가 아니라 별도 `1.12.3-hotfix` worktree의 로컬 `main@d6628dd` 위 63개 미커밋 경로에 있다. |
| Task 4 실제 자격증명 회전을 실행했는가? | 아니오. production `.env`, canonical DB, `%USERPROFILE%/AeroOne-secure`는 의도적으로 건드리지 않았다. |
| Task 3 focused 검증은? | 최종 `85 passed, 3 warnings`, 실패 0. |
| backend 전체 검증은? | 1차 `367 passed, 2 failed`; 두 실패는 worktree-비독립 batch fixture였고 단독 `2 passed`로 수정했다. 최종 전체 재실행은 약 25분 시점에 실패 1건이 찍힌 상태에서 worker 사용량 한도로 중단되어 node/trace가 남지 않았다. 따라서 PASS가 아니다. |
| frontend/WPF/5-lane Round 4 리뷰는? | frontend 313 passed/66 + typecheck + production build 완료, 코드리뷰 lane(Python backend + PowerShell 보안모듈) CLEAR. WPF 인터랙티브 desktop 시각 QA만 미완(human/desktop). |
| 커밋·push·PR은? | Round 4는 `18b4ba9`로 커밋(hotfix origin/main 대비 0 4, dirty 0). push/PR/tag/release는 수행하지 않았다. |
| 안전한 다음 행동은? | WPF 인터랙티브 desktop 시각 QA(사람)로 Task 3 최종 sign-off 후, 운영자 명시 승인 하에 Task 4를 실행한다. sign-off 전 Task 4 금지. |

정식 계획 진척은 `2/27`이며, Task 3은 자동 검증(backend 369·frontend 313·static·코드리뷰 CLEAR)과 Round 4 커밋(18b4ba9)까지 완료해 WPF 시각 QA만 남은 사실상 완료 단계다. 두 수치를 섞어 전체 개발이 거의 끝났다고 표현하면 안 된다.

---

## 1. 진실 원천과 읽기 순서

다음 순서를 기준으로 충돌을 해결한다.

1. [`AGENTS.md`](../../AGENTS.md) — 저장소 위험 신호, 한국어 커밋·PR, 릴리스 규칙
2. [전체 v1.13.0 계획](../../.omo/plans/v1-13-0-operator-experience-plan.md) — Task 1~27와 F1~F6의 acceptance/QA/의존성
3. [2026-07-11 최신 핸드오프](../runbook/ai-agent-handoff-2026-07-11.md) — 실제 재개 순서
4. 본 문서 — 지금까지 한 작업, 검토 이력, 현재 중단 지점, 남은 작업 상세
5. Task별 evidence
   - [Task 1](../../.omo/evidence/v1-13-0/task-1.md)
   - [Task 2](../../.omo/evidence/v1-13-0/task-2.md)
   - [Task 3 Round 1](../../.omo/evidence/v1-13-0/task-3-review-round-1.md)
   - [Task 3 Round 2](../../.omo/evidence/v1-13-0/task-3-review-round-2.md)
   - [Task 3 Round 3](../../.omo/evidence/v1-13-0/task-3-review-round-3.md)
   - [Task 3 현재 checkpoint](../../.omo/evidence/v1-13-0/task-3-current-status.md)
6. 운영 계약
   - `docs/runbook/credential-rotation.md` — hotfix worktree의 미커밋 운영 계약
   - [`CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
   - [`windows-offline.md`](../runbook/windows-offline.md)

2026-07-09 핸드오프는 당시에는 유효했지만 현재는 Task 1~3 진행 전 상태를 설명한다. 최신 상태 판단에는 사용하지 말고 이력으로만 읽는다.

---

## 2. 저장소·worktree·원격 상태

| 구분 | 값 | 의미 |
|---|---|---|
| root worktree | `D:/Chanil_Park/Project/Programming/AeroOne` | 계획·evidence·handoff를 보존하는 `1.13.0-dev` worktree |
| root branch/HEAD | `1.13.0-dev@034bd03` | `origin/1.13.0-dev`와 동일한 마지막 push 지점 |
| root dirty | `.omo` plan/draft/boulder/ledger/evidence + 이번 문서 | 제품 코드와 섞지 말고 Task 10에서 의도적으로 보존할 상태 |
| hotfix worktree | `.worktrees/1.12.3-hotfix` | Task 3 제품 구현과 이후 Task 4~9의 주 작업 장소 |
| hotfix branch/HEAD | local `main@d6628dd` | `origin/main`보다 3 commit 앞섬 (`ca9ce3e`, `2259fdc`, `d6628dd`) |
| hotfix dirty | 63개 경로 | Round 4 수정. 절대 reset/checkout/rebase로 버리면 안 됨 |
| origin/main | `2f592c4`, tag `1.12.2` | 아직 1.12.3 hotfix 미배포 |
| review worktrees | `task3-review-r3`, `task3-qa-r3` | Round 3 detached 검토 흔적. Task 3 Round 4 PASS/evidence 확정 뒤 정리 |
| unrelated worktrees | `dashboard-enhancements`, `AeroOne-release-1.7.0` | 다른 작업. 프로세스·파일을 건드리지 말 것 |

현재 AeroOne hotfix backend pytest는 실행 중이지 않다. 다른 worktree나 다른 저장소의 pytest가 보일 수 있으므로 command line과 worktree 경로로 소유권을 확인하지 않고 종료하면 안 된다.

---

## 3. Goal/세션 중단 원인

| 항목 | 값 |
|---|---|
| Goal objective | Task 3부터 Task 27, F1~F6까지 완료해 `1.13.0-dev`를 PR 직전 상태로 만들기 |
| Goal 최종 관측 상태 | `usageLimited` |
| 관측 사용량 | 659,011 tokens, 16,001초 |
| 직접 영향 | Task 3 backend full 최종 재실행을 감시하던 worker가 종료되어 실행 summary와 실패 node를 회수하지 못함 |
| 제품 상태 영향 | production credential/DB 변경 없음. 미커밋 worktree 파일은 보존됨 |
| 재개 조건 | 새 세션/사용량 복구 후 본 문서의 §10부터 재실행 |

이 중단은 검증 PASS가 아니다. 마지막 backend full은 실패 1건이 찍힌 채 정확한 node를 얻기 전에 종료됐으므로 처음부터 새 로그로 재실행해야 한다.

---

## 4. 전체 계획 페이지와 현재 상태

전체 acceptance, Must NOT, QA 시나리오, commit 정책은 [계획 원문](../../.omo/plans/v1-13-0-operator-experience-plan.md)에 있다. 아래 표는 실제 실행 상태와 재개 지점을 결합한 작업 페이지다.

| Task | 상태 | 의존성 | 구현/검증 핵심 | 다음 행동 |
|---:|---|---|---|---|
| 1 | 완료 | 없음 | proven-unsafe 1.12.2 ZIP/SHA exact pair 봉쇄, release/tag/body 보존, old URL 404 | evidence 보존만 |
| 2 | 완료 | 1 | 46 releases, 15 ZIP 계약 중앙-directory-only 감사; 승인 후 historical 14쌍/28 assets 삭제, 12 releases warning | evidence 보존만 |
| 3 | 진행 중 | 2 | DB-aware credential rotation, DPAPI recovery/journal/bundle, ACL/path/lock/resume/viewer/maintenance gate | backend full→frontend→WPF→evidence→Round 4 review→commit |
| 4 | 금지/대기 | 3 | 현재 workspace 실제 env/canonical DB의 전체 계정 비밀번호·JWT·session 회전과 quarantine | Task 3 unconditional PASS 전 실행 금지 |
| 5 | 대기 | 3 | public package allow-list policy와 pre/post verifier | Task 3 commit 뒤 TDD 시작 |
| 6 | 대기 | 5 | `git archive` builder, exact installers, Sandbox offline smoke | 관리자 elevation 필요; `RestartNeeded=true`면 reboot 승인 필요 |
| 7 | 대기 | 5 | CMS 기반 내부 data bundle, 역할별 독립 서명, trust chain, atomic import | 계획에 반영한 보강 계약대로 TDD |
| 8 | 대기 | 4,6,7 | Next 15.2.9, 1.12.3 metadata/incident/운영 문서 | 선행 release/security gate 완료 뒤 |
| 9 | 대기 | 4~8 | 1.12.3 full verify/tag/package/Sandbox/GitHub release | prerequisite PASS 전 tag 금지 |
| 10 | 대기 | 9 | 1.12.3 ancestry를 `1.13.0-dev`에 no-ff merge, OMO state 동기화 | rebase/squash 금지 |
| 11 | 대기 | 10 | `DESIGN.md`와 frontend design state로 시각 언어 고정 | 제품 UI 변경 전 실행 |
| 12 | 대기 | 10 | exact-pinned QA dependencies와 production-browser harness | 외부 CDN/Chromium download 금지 |
| 13 | 대기 | 10 | backend admin seam 추출, NSA module 상태를 모든 delivery surface에 강제 | 서버 권한 fail-closed 유지 |
| 14 | 대기 | 11 | frontend admin loader/tab registry/section shell 분리, partial failure | giant admin file 회피 |
| 15 | 대기 | 10 | single client session provider와 canonical NSA visibility helper | frontend 권한을 authority로 취급 금지 |
| 16 | 대기 | 11,12,15 | account menu, Document/NSA nav, AI scope를 shared session 계약으로 전환 | Document 공개/NSA exact 권한 matrix |
| 17 | 대기 | 11,12 | status-preserving API error와 safe `next` redirect/login | unsafe external redirect 차단 |
| 18 | 대기 | 12,13,15 | self-only `GET /api/v1/auth/activity` + composite index migration | prompt/answer/hash/IP/UA 반환 금지 |
| 19 | 대기 | 11,12,15~18 | `/activity` UI와 typed frontend contract/account menu 연결 | empty/401/5xx/retry 포함 |
| 20 | 대기 | 12,13 | 24h backend Overview와 실제 session 집계 | frontend 가짜 0/합성 차트 금지 |
| 21 | 대기 | 12,13 | service module access tuple merged-state server validator | invalid mutation/audit 0 |
| 22 | 대기 | 11,12,14,20 | dependency-free horizontal charts, Overview default, shortcut `0` | 실제 backend 값만 표시 |
| 23 | 대기 | 11,12,14,20 | Users/Sessions role/status/load/paging/autorefresh/purge UX | actual session/user 구분 |
| 24 | 대기 | 11,12,14,21 | Module create/edit access presets/preview | server validator와 동일 계약 |
| 25 | 대기 | 16~24 | phase report, 최신 handoff, 전체 운영/보안 문서 동기화 | 본 중간 문서를 최종 구현 상태로 교체/승격 |
| 26 | 대기 | 12,19,22~25 | backend/frontend/package/migration/browser/Axe/Lighthouse/react QA | 동일 revision, fresh artifacts, 두 visual review PASS |
| 27 | 대기 | 26 | README/backend/changelog의 release-final 1.13.0 metadata | metadata-only 마지막 dev commit |
| F1 | 대기 | 27 | plan compliance audit | Task 1~27 evidence를 양방향 매핑 |
| F2 | 대기 | 27 | 5-lane code quality review | goal/code/security/QA/context 모두 unconditional PASS |
| F3 | 대기 | 27 | real manual QA | 최종 SHA에서 browser matrix 재실행 |
| F4 | 대기 | 27 | scope fidelity | commit/Lore/ancestry/out-of-scope 0 |
| F5 | 대기 | 27 | security/release audit | containment/rotation/package/internal boundary 재검증 |
| F6 | 대기 | F1~F5 | dev push와 한국어 PR body, PR 생성 직전 중단 | `gh pr create` 실행 금지 |

---

## 5. 완료 작업 상세

### 5.1 Task 1 — 1.12.2 즉시 봉쇄

- release ID `350620445`, tag `1.12.2`를 보존했다.
- ZIP/SHA exact asset 두 개만 삭제했다.
- 사용·재배포 금지와 교체 예정 warning을 기존 본문 위에 추가했다.
- API raw CRLF와 CLI LF-normalized body hash를 둘 다 검증해 줄바꿈 정규화 오판을 차단했다.
- target 외 asset 집합과 release/tag/body suffix를 보존했다.
- 비인증 old ZIP/SHA URL이 모두 404임을 확인했다.
- archive를 다운로드·추출하지 않았고 raw entry name/내용을 evidence에 남기지 않았다.

### 5.2 Task 2 — historical containment

- Git 상태를 `1.13.0-dev@034bd03`, upstream divergence `0 0`으로 확인했다.
- 46개 release를 paginate해 14개 remote ZIP과 Task 1 local receipt 1개를 감사했다.
- HTTP 206 range와 EOCD/ZIP64/central directory만 읽고 full download/entry stream read를 0으로 유지했다.
- 15개 모두 env/database/storage/agent-state/dev-artifact 계열 unsafe로 판정했다.
- 사용자 `삭제 승인` 후 14 ZIP/SHA pair, 28 assets를 exact ID로 삭제했다.
- 12개 release에 warning을 추가했고 executor와 독립 verifier가 결과를 확인했다.
- Task 3~9를 막던 historical asset owner approval gate는 해제됐다.

---

## 6. Task 3 구현·검토 이력

### 6.1 커밋 계보

| Commit | 의도 | 상태 |
|---|---|---|
| `ca9ce3e` | DB 기준 전체 credential rotation 초기 구현 | Round 1 5-lane FAIL |
| `2259fdc` | recovery/integrity blocker 1차 보강 | Round 2 goal/security/context FAIL |
| `d6628dd` | 중단 안전 운영 경계 2차 보강 | Round 3 5-lane FAIL, runtime audit inconclusive |
| 미커밋 Round 4 | Round 3 blocker와 후속 회귀를 RED→GREEN으로 수정 | focused PASS, backend full 최종 PASS 미확정 |

local `main`은 `origin/main`보다 위 세 commit 앞서 있다. 이력을 squash/rebase/reset으로 지우면 안 된다.

### 6.2 Round 1 검토 지적

Round 1은 goal/QA/code/security/context가 모두 FAIL이었다. 핵심 blocker:

- corrupt pending artifact가 partial mutation을 유발할 수 있음
- journal non-atomic, crash seam 복구 불가
- TestMode가 production bypass로 악용될 수 있음
- script provenance mismatch
- reparse/hardlink scope escape와 cross-volume quarantine
- plaintext temp ACL window
- SQLite WAL이 포함되지 않는 recovery
- global lock/unique ledger 부재
- inactive admin/strict input/backup restore/docs drift

Round 1 조치로 physical path validation, atomic/pending 경계, WAL-aware recovery, global lock, ledger, strict command boundary, test seam 격리 등을 추가했다.

### 6.3 Round 2 검토 지적

Round 2는 QA PASS였지만 goal/security/context FAIL, code quality inconclusive였다. 핵심 blocker:

- live env physical preflight 누락
- env publish와 journal 사이 crash window
- workspace plaintext temp orphan
- session-local mutex
- backup commit/writer gap
- root/backend env profile drift
- dry-run side effect와 public failpoint surface
- general backup restore/credential handoff/docs drift

Round 2 조치로 physical env preflight, durable journal promotion, secure temp ownership, Global mutex, contiguous DB lock, profile binding, internal-only failpoint, dedicated credential viewer를 보강했다.

### 6.4 Round 3 검토 지적

Round 3은 5-lane 모두 FAIL, 세 runtime hypothesis 모두 inconclusive였다. QA 23개 중 13 PASS/10 FAIL. 확정 blocker:

- ordinary current SID ACL 적용이 `SeSecurityPrivilege`를 요구
- no-backup `File.Replace(..., $null)` legal form 실패
- production root 하드코딩과 viewer provenance mismatch
- root+backend env만 허용해 backend-only 설치 topology 거부
- prepared resume가 immutable pre-rotation recovery를 덮어쓸 수 있음
- recovery publish와 journal 사이 crash window
- service preflight TOCTOU와 회전 중 앱 재시작
- restore confirmation 뒤 archive 전 external writer race
- clipboard history/cloud 노출과 clear 실패 후 ownership 유실
- setup/rotation 문서와 artifact 이름 drift
- child timeout/LOC 초과

### 6.5 미커밋 Round 4에서 완료한 변경

| 영역 | 구현 결과 | 주요 검증 |
|---|---|---|
| ACL | `FileInfo.SetAccessControl(FileSecurity)`로 owner+DACL만 영속화, SACL privilege 제거 | ordinary-user RED→GREEN |
| atomic replace | Win32 `MoveFileExW(REPLACE_EXISTING|WRITE_THROUGH)` 모듈 | no-backup replace RED→GREEN |
| 구조 | main PowerShell 249 LOC 이하, 책임별 모듈 분리 | changed Python/PS pure LOC 모두 ≤250 |
| root/provenance | runtime-relative physical root와 exact entrypoint provenance | copied rotation/viewer synthetic PASS |
| env topology | root env optional, backend env required, journal v2 topology binding | backend-only/dual-env/resume/drift PASS |
| immutable recovery | versioned `aeroone-db-before-rotation.<uuid>.dpapi`, publish/commit crash reconstruction | immutable suite 4 PASS |
| maintenance gate | rotation/setup/start/backend가 동일 physical-workspace Global mutex 계약 사용 | wrapper/direct-holder/import-order PASS |
| restore/archive | Python `BEGIN IMMEDIATE`를 confirmation부터 archive ack까지 유지 | external writer blocked, archive 뒤 writer 성공 |
| clipboard | history/cloud 제외 metadata, owned-only atomic clear, 5회 retry, close 거부 | real STA clipboard behavioral PASS |
| artifact 이름 | final `credentials.dpapi`, versioned recovery 이름으로 통일 | stale fixed-name contract 0 |
| resume topology | journal상 root=true+live missing은 복구, root=false+unexpected live는 거부 | crash→resume와 backend-only reject PASS |
| timeout | child/ACL/viewer subprocess bounded wait와 cleanup | timeout contract PASS |
| docs | setup rerun caveat, rotation/viewer 계약, 이름 동기화 | changed markdown link scan PASS |
| Python 구조 | `sqlite_recovery` snapshot 분리, maintenance/journal/orchestrator tests 분리 | 9 characterization 전후 PASS |

### 6.6 주요 RED→GREEN 기록

| 결함 | RED | GREEN |
|---|---|---|
| maintenance wrapper 부재 | 1 failed / 11.92s | 1 passed / 22.69s |
| restore/archive writer race | writer acquired, 1 failed / 42.19s | database locked during archive, 1 passed / 39.18s |
| direct backend lifetime gate | direct holder 상호배제 미검증 | 2 passed / 47.61s |
| clipboard module 부재 | 2 failed / 2.85s | behavioral 2 passed / 6.26s, final fast 3 passed |
| XAML height | 430에서 clipped | 580에서 fit |
| missing root resume | `env-topology-changed` | exact node 1 passed / 66.71s |
| stale fixed recovery ACL | orchestrator exact fail | 1 passed / 223.35s |
| fixed recovery name 허용 | contract fail | contracts 2 passed |
| oversized recovery/maintenance | 263/269 LOC | 224/148 LOC + extracted modules/tests |
| stale production-like test seam | `python-runtime-missing` | current synthetic seam PASS |
| fixture `Set-Acl` privilege | assertion 전 `SeSecurityPrivilege` | `FileInfo.SetAccessControl` fixture PASS |
| worktree sibling bundle fixture | full backend 2 FAIL | synthetic temp bundle 2 PASS |

---

## 7. Task 3 현재 검증 상태

| Gate | 마지막 유효 결과 | 판정 |
|---|---|---|
| changed Python Ruff | PASS | 유효 |
| Task 3 production basedpyright | 0 errors, 0 warnings, 0 notes | 유효 |
| compileall/import probe | PASS | 유효 |
| changed PowerShell AST | 26/26 PASS | 유효 |
| pure LOC | production/test touched 모두 ≤250 | 유효 |
| secret/stale-name/root/Set-Acl scan | count 0 | 유효 |
| changed markdown links | dead 0 | 유효 |
| `git diff --check` | PASS | 유효 |
| focused credential rotation | 85 passed, 3 warnings, 1979.95s | 유효 |
| backend full 1차 | 367 passed, 2 failed | fixture 결함 발견으로 superseded |
| 두 batch fixture 단독 | 2 passed, 20.27s | 유효 |
| backend full 최종 | 약 25분, 실패 1개 표시 후 worker 사용량 종료 | **무효/FAIL 취급** |
| frontend full | hotfix에 node_modules가 없어 첫 호출 전 종료; 병렬 재시도 worker tree cleanup | 미완료 |
| WPF independent desktop QA | capability 확인만 완료 | 미완료 |
| Round 4 5-lane review | 미실행 | 미완료 |
| Round 4 3-hypothesis audit | 미실행 | 미완료 |
| Task 3 evidence final | current checkpoint만 작성 | 미완료 |
| Task 3 Round 4 commit | 없음 | 미완료 |

마지막 backend full의 실패 node/trace는 회수되지 않았다. 추측으로 fixture/제품 결함을 분류하지 말고 새 실행에서 로그와 nodeid를 확보해야 한다.

---

## 8. Task 3 변경 파일 지도

### 8.1 production Python

- `backend/app/main.py`
- `backend/app/core/maintenance_gate.py`
- `backend/app/core/maintenance_gate_bootstrap.py`
- `backend/app/commands/credential_rotation_transaction.py`
- `backend/app/operations/credential_rotation_artifacts.py`
- `backend/app/operations/credential_rotation_ledger.py`
- `backend/app/operations/sqlite_recovery.py`
- `backend/app/operations/sqlite_recovery_snapshot.py`

### 8.2 PowerShell/batch

- `scripts/rotate_aeroone_credentials.ps1`
- `scripts/view_aeroone_credentials.ps1`
- `scripts/credential_rotation/Rotation.Archive.psm1`
- `Rotation.Bootstrap.psm1`
- `Rotation.Clipboard.psm1`
- `Rotation.Configuration.psm1`
- `Rotation.CredentialViewer.psm1`
- `Rotation.DatabaseTransaction.psm1`
- `Rotation.NativeFile.psm1`
- `Rotation.PathSecurity.psm1`
- `Rotation.ProcessLock.psm1`
- `Rotation.PythonCommand.psm1`
- `Rotation.Reconciliation.psm1`
- `Rotation.RecoveryOrchestrator.psm1`
- `Rotation.RecoveryPreparation.psm1`
- `Rotation.Runtime.psm1`
- `Rotation.Scope.psm1`
- `Rotation.SecureIO.psm1`
- `Rotation.Security.psm1`
- `Rotation.StateMachine.psm1`
- `Rotation.TestSeams.psm1`
- `scripts/windows/hold_maintenance_gate.ps1`
- `scripts/windows/invoke_with_maintenance_gate.ps1`
- `setup_offline.bat`
- `start_offline.bat`

### 8.3 tests

- `backend/tests/conftest.py`
- `backend/tests/rotation_harness.py`
- `backend/tests/maintenance_gate_harness.py`
- `backend/tests/integration/test_credential_rotation_{clipboard,contiguous_db_lock,environment_profiles,environment_topology,immutable_recovery,journal,journal_topology,maintenance_gate,orchestrator,orchestrator_core,parameter_surface,path_security,recovery,restore_archive_gate,secure_io,service_preflight,viewer}.py`
- `backend/tests/unit/test_credential_rotation_artifacts.py`
- `backend/tests/unit/shared/test_credential_rotation_artifact_names.py`
- `backend/tests/unit/shared/test_credential_rotation_process_timeouts.py`
- `backend/tests/unit/shared/test_windows_batch_scripts.py`

### 8.4 docs

- `README.md`
- `docs/CLOSED_NETWORK_GUIDE.md`
- `docs/INDEX.md`
- `docs/reports/phase-22-operator-visibility-and-module-management.md`
- `docs/reports/phase-8-offline-simulation.md`
- `docs/runbook/credential-rotation.md`

---

## 9. 남은 Task 4~10 상세 실행 페이지

### Task 4 — 실제 workspace credential rotation

선행 조건은 Task 3 commit과 unconditional Round 4 PASS다. 실행 전에 정확한 root/backend env topology, canonical SQLite 하나, AeroOne 소유 process/listener를 read-only로 확인한다. 다른 deployment root/provider key를 발견하면 자동 확장하지 말고 중단한다.

실행 결과에는 다음만 기록한다.

- 사용자 수, password hash inequality 수, session version 증가 수, session 삭제 수
- role/is_active 불변 여부
- known-old credential 401, 새 active credential 200, inactive credential 403
- secure root owner/DACL/retention과 DPAPI artifact 존재 여부
- quarantine source/destination count·size·digest 일치

secret, hash, raw DB row, raw absolute sensitive path는 기록하지 않는다. postcommit 실패는 rollback하지 않고 journal forward-resume한다.

### Task 5 — public package policy/verifier

- allow-list JSON과 installer policy를 strict schema로 만든다.
- exact `.env.example` 외 env, DB/WAL/SHM, `_database`, storage, backup, agent/VCS/worktree/cache/dev/QA를 구조적으로 거부한다.
- path traversal, drive/UNC/ADS, reserved name, case/Unicode duplicate, symlink/reparse를 거부한다.
- Python 3.12.7/Node 20.18.0 exact filename/hash/signer를 stage path에서 Authenticode 검증한다.
- post-ZIP은 extract 없이 entry SHA가 앞 단계 Valid signature를 통과한 pinned digest와 같은지 증명한다.
- manifest/entry를 one-to-one으로 검증하고 실패 산출물은 publishable 위치에 남기지 않는다.

### Task 6 — public package builder/Sandbox

- robocopy workspace 복사를 `git archive` allow-list builder로 교체한다.
- clean temp에서 npm ci/build/prune, runtime requirements wheelhouse만 만든다.
- exact two installers만 generated root에 넣는다.
- release profile은 annotated tag=HEAD=version, QA profile은 ignored artifact와 `publishable=false`를 강제한다.
- 현재 host는 Windows 11 Pro build 26200, virtualization/hypervisor 조건은 충족하지만 현재 shell은 비관리자이고 Sandbox executable이 없다.
- 관리자 PowerShell에서 feature를 활성화해야 하며 반환값 `RestartNeeded=true`일 때만 별도 reboot 승인을 받는다. 자동 reboot 금지.

### Task 7 — internal data bundle

- approval raw JSON은 duplicate key를 거부하는 strict parser로 읽는다.
- normal roots와 NSA root를 혼합하지 않는다.
- 역할별 운영자가 별도 signer 도구로 `.p7s`를 만들고 builder는 private signing key를 사용하지 않는다.
- thumbprint/subject/EKU/validity뿐 아니라 signature와 Windows organizational trust chain을 검증한다.
- trust policy fixed path/registry digest/protected exact read-only ACL을 검증한다.
- AES-256-CBC EnvelopedCms, deterministic inventory, canonical paths를 사용한다.
- import는 Task 3 maintenance gate 아래 same-volume staging+durable journal+old-root recovery로 수행한다.
- production trust absent baseline은 fail-closed여야 하고 real trust provisioning/real bundle은 이번 PR 범위 밖이다.

### Task 8~10 — 1.12.3 release와 dev ancestry

Task 8에서 Next 15.2.9 exact pin, 1.12.3 metadata, incident/rotation/package 문서를 맞춘다. Task 9는 full backend/frontend/package/Sandbox를 clean source에서 통과한 뒤 local tag→package→Sandbox→push/draft→digest→publish 순서를 지킨다. 실패한 local tag/partial draft asset은 계획대로 정리한다. Task 10은 root dev worktree에서 OMO plan/evidence를 먼저 보존하고 `origin/main`의 verified 1.12.3 ancestry를 no-ff merge한다. rebase/squash/cherry-pick으로 hotfix 계보를 단순화하지 않는다.

---

## 9A. 남은 Task 11~15 — 제품 기반 상세 페이지

### Task 11 — 시각 언어 선고정

root `DESIGN.md`에 계획이 요구하는 8개 exact heading을 만들고 기존 `globals.css`, Tailwind semantic tokens, local SVG/primitives에서 실제 운영 콘솔의 언어를 추출한다. Account menu, Login, Activity, Admin tabs, horizontal chart에 대해 loading/empty/error/disabled/degraded/focus/light/dark/200% zoom 상태를 코드 전에 정의한다. `.omo/frontend-design/state.md`에는 결정, accepted debt, 증거를 누적한다. production import graph에 들어가지 않는 dev showcase와 component test로 상태 조합을 검증한다.

금지 사항은 marketing hero 재설계, emoji icon, 새 font/icon/chart/animation dependency, one-off palette 확산, 기존 접근성 부채를 근거 없이 해결됐다고 기록하는 것이다. DESIGN commit보다 앞선 제품 UI commit이 없어야 한다.

### Task 12 — 재현 가능한 browser QA 기반

host Node 22.14.0에서 Playwright/Axe/Lighthouse/react-grab/react-scan/react-doctor 등 계획의 7종을 exact version으로 dev dependency/lockfile에 고정한다. offline product Node 20.18.0과 QA host를 혼합하지 않는다. 새 commit SHA마다 격리 runtime root, synthetic strong secrets, 새 SQLite/storage, anonymous/normal/NSA/admin identities, stable Chrome, health/teardown을 만드는 harness를 구현한다.

real env/DB/storage, bundled Playwright Chromium download, `npx latest`, CDN, dev-tool의 production import/ZIP 포함을 금지한다. 외부 browser network/CDN/`:11434` 0, listener/process/temp/secret env 잔존 0을 self-test로 증명해야 한다.

### Task 13 — backend admin seam과 NSA module stop

기존 admin route/OpenAPI/audit/CSRF/session fanout을 characterization test로 고정한 뒤 query/mutation service seam을 추출한다. `can_access_collection_service`는 Document/Civil의 기존 public 의미를 보존하고, NSA에 대해서만 module row 존재 + enabled + non-hidden 조건을 canonical authority와 결합한다.

collection list/content/download/search, admin unified search, AI requested scope/selected refs/RAG/FTS loader가 같은 helper를 사용해야 한다. admin이라도 module disabled/hidden/missing이면 NSA는 fail-closed다. module seeding/management와 collection policy 간 circular import를 만들지 않는다.

### Task 14 — admin frontend 분리와 부분 실패

`admin-console-tabs.tsx`에서 typed data loader, navigation registry, section shell/state를 분리한다. initial load를 `Promise.allSettled` 기반 per-section `loading|ready|empty|error` 상태로 바꾸어 한 endpoint 실패가 다른 성공 데이터를 0/empty로 덮지 않게 한다. 기존 9 tabs, default Modules, shortcut 1~9, mutation scoped refresh, sessions 15초 refresh는 그대로 고정한다.

실패 section retry는 해당 key만 refetch해야 하고 interval/mutation이 전체 endpoint를 호출하면 실패다. 새 module은 pure LOC 250 이하, strict types를 유지한다.

### Task 15 — single client session와 NSA visibility

AppShell은 server component로 유지하고 하나의 `ClientSessionProvider` island만 둔다. provider는 `loading|anonymous|authenticated|unavailable`, full session, retry를 제공한다. session BFF는 auth me, effective permissions, public modules를 server-to-server로 조회해 strict parse한다.

`canViewNsa`는 authenticated + module enabled/non-hidden + admin/global legacy/exact resource grant를 모두 정확히 검사한다. malformed/loading/unavailable/wrong grant는 false다. 이 helper는 UI 노출 판단일 뿐 backend authority를 대체하지 않는다. provider fetch는 최초 1회, retry 때만 추가한다.

---

## 9B. 남은 Task 16~19 — 일반 사용자 흐름 상세 페이지

### Task 16 — account menu와 권한 기반 nav/AI scope

기존 `AdminNavLink`를 `AccountMenu`로 교체한다. 이 단계에서는 Admin console과 Logout만 넣고 Activity는 Task 19 route와 같은 commit에서 원자적으로 활성화한다. trigger ARIA, Enter/Space/ArrowUp/Down, cyclic arrows, Home/End, Escape focus return, Tab/outside close를 완전 구현한다. logout 실패는 menu를 유지하고 성공은 `/login` hard navigation한다.

Document는 항상 유지하고 NSA는 Task 15 helper가 true일 때만 primary nav와 AI scope에 동시에 보인다. anonymous/normal/wrong permission/session failure/module disabled/hidden에서 privileged DOM은 0이어야 한다. direct NSA API 401/403은 유지한다.

### Task 17 — typed API error와 safe redirect

`browserFetch`는 status를 보존하는 `ApiError`만 일관되게 throw하도록 한다. `sanitizeNextPath`는 root-relative same-origin path 하나만 허용하고 raw/decoded double slash, backslash, scheme/credentials, control, malformed percent, repeated decode 공격을 모두 `/`로 보낸다.

login page는 server-side sanitized `next`만 form에 전달한다. submit 중 disable/loading/request 1회를 보장하고 성공은 safe hard navigation, 기본 `/`다. theme redirect와 auth proxy activity allow-list도 같은 계약을 쓴다. default `/admin`, untrusted `router.push`, 한 번 decode 검사는 금지다.

### Task 18 — self-only activity API와 migration

`GET /api/v1/auth/activity`는 current user의 bounded metadata만 반환한다. active sessions, login/logout, AI request status/timestamps, safe accessible module hints를 포함하되 prompt/answer/title/snippet/citation/hash/IP/UA/session ID/request ID/conversation ID 등 민감 식별자·본문은 반환하지 않는다. 다른 사용자와 expired session을 제외한다.

필요 composite index를 Alembic upgrade/downgrade/upgrade로 검증한다. client supplied user ID를 받지 않고 current auth identity만 사용한다. NSA hint는 Task 13/15 canonical policy와 일치해야 한다.

### Task 19 — `/activity` 화면과 menu 원자 연결

typed API client와 `/activity` route/section components를 추가한다. identity, sessions, login/logout, AI metadata, modules를 각각 loading/empty/error로 표시한다. 401은 safe `/login?next=%2Factivity`, 5xx는 inline retry다. CJK-friendly deterministic timestamp/status label을 사용하고 raw ID/content를 DOM에 렌더하지 않는다.

Task 16의 Activity menu item은 이 route와 같은 commit에서 첫 authenticated item으로 활성화한다. normal user가 keyboard만으로 menu→Activity를 이동하고 다른 사용자 fixture와 sensitive content가 보이지 않는지 production browser에서 검증한다.

---

## 9C. 남은 Task 20~24 — 관리자 기능 상세 페이지

### Task 20 — 24시간 Overview와 실제 session 집계

단일 time anchor/transaction으로 current 24h와 previous 24h를 계산한다. users total/active/roles/created, actual session rows/distinct users/window, login success/failure/logout, AI request/failure, disjoint module buckets, safe system/newsletter/assets/read summary, recent audit max10을 backend response로 만든다.

DB URL, actor/target raw IDs, IP/UA/metadata, full audit event를 제거한다. active session count와 active user count를 구분하고 compatibility `active_count` 의미를 문서화한다. module bucket은 disabled/hidden 우선으로 mutually exclusive여야 한다. fixed clock boundary/duplicate sessions/expired rows/query count를 pytest로 검증한다.

### Task 21 — module access tuple server validator

create와 PATCH의 existing + `exclude_unset` merged state를 mutation/audit 전에 pure validator로 검사한다. 허용 상태는 admin null gate, public ungated, public known global permission, exact NSA resource tuple 네 가지뿐이다. partial/unknown/mismatch/unsafe ID/admin+gate는 400이다.

invalid request는 row/audit/session mutation 0이어야 한다. toggle-only PATCH는 valid gate를 보존한다. non-admin public listing은 disabled/hidden을 제거하고 NSA는 canonical collection policy를 추가 확인한다.

### Task 22 — dependency-free Overview UI

small typed modules로 metric formatter/card/grouped·stacked horizontal bars/text-value list를 만든다. graphic은 `aria-hidden`, 모든 의미는 text heading/label/value로 제공한다. Overview를 첫/default tab으로 추가하고 `0=Overview`, 기존 `1..9` mapping은 그대로 유지한다. editable target/modifier에서는 shortcut을 무시한다.

Task 20 backend aggregate만 authoritative value로 사용한다. missing/error를 0으로 위조하지 않고 detail endpoint 실패는 section별 degraded/retry다. donut/ring/sparkline/canvas-only/runtime chart dependency를 금지한다.

### Task 23 — Users/Sessions 실제 부하와 paging

Users에는 created/last login, role/status counts, text+horizontal bars, search/sort, 10/page client paging, query/sort 변경 시 page 1 reset을 구현한다. 21-user fixture가 10/10/1인지 확인한다.

Sessions에는 actual rows/distinct users와 recent event window를 표시하되 기존 connectedUsers-only 15초 refresh, last refresh, search/sort, login event 10/page, purge confirmation/scoped refresh를 보존한다. 한 사용자에 session 2개면 session=2/user=1이다. narrow viewport root overflow와 clipped control은 0이어야 한다.

### Task 24 — module access preset/preview UI

draft/API/create/edit에 gate 3필드를 완전 연결한다. Document ungated와 exact NSA collection preset을 제공하고 pure frontend validator가 server의 네 상태를 같은 표현으로 설명한다. edit preset은 key/title/href/description/sort identity를 덮어쓰지 않는다.

invalid partial/unknown/unsafe/mismatch는 inline error, API call 0이다. server 400에서도 row UI/DB/audit가 변하지 않는다. toggle payload는 `is_enabled`만 전송한다. create/update/delete/toggle의 기존 scoped refresh/audit behavior를 유지한다.

---

## 9D. 남은 Task 25~27 — 문서·통합·버전 상세 페이지

### Task 25 — 최종 구현 문서화

본 WIP 보고서와 2026-07-11 핸드오프를 출발점으로 실제 구현 완료 시점의 `phase-26-operator-experience.md`와 최신 handoff를 작성한다. README, AGENTS, CLAUDE, CONTRIBUTING, INDEX, CLOSED_NETWORK_GUIDE, windows-offline, admin-auth, install manual을 실제 account/activity/NSA/module/Overview/QA/package 계약과 맞춘다.

이 중간 문서의 pass count나 branch/HEAD를 그대로 복사하지 말고 final revision에서 다시 측정한다. 1.13.0 released 표현과 version badge는 아직 금지하며 1.12.3을 current stable로 유지한다. old handoff는 삭제하지 않고 superseded chain으로 연결한다.

### Task 26 — 동일 revision 전체 QA

backend full, frontend full/typecheck/build, Alembic upgrade/downgrade/upgrade, package security/E2E를 하나의 commit SHA에서 실행한다. Browser Matrix 전부를 375×812, 768×1024, 1280×800, 대상 화면 200% zoom에서 실행한다. keyboard/focus/CJK/root overflow/console/page/request/4xx/5xx/external network/Axe를 계측한다.

`/login`, `/activity`, `/admin` mobile+desktop Lighthouse median은 계획상 100/100/100/100이고 react-doctor blocking 0, react-scan unnecessary render 0을 요구한다. QA-mode package를 clean temp에 설치해 setup/start/health/login/empty NSA smoke를 수행한다. fresh screenshots를 두 independent visual reviewer가 같은 SHA에서 unconditional PASS해야 한다.

### Task 27 — release-final metadata only

Task 26 green SHA 이후 README badge/release line, backend app version, frontend changelog 최신 entry만 1.13.0으로 바꾼다. version focused tests와 stale current-version scanner를 실행한다. 이 commit 이후 tracked source/docs를 수정하지 않고 final wave에서는 ignored artifacts만 만든다.

annotated 1.13.0 tag, official ZIP/release, main merge, 기능/refactor 동시 변경은 금지다. metadata diff만 마지막 dev commit이어야 한다.

---

## 9E. F1~F6 최종 검증 상세 페이지

### F1 — Plan compliance

Original Request, 추천안 1~5, Must Have/Not, Task 1~27를 changed files/tests/evidence와 양방향 매핑한다. 누락, 근거 없는 PASS, stale evidence 재사용, out-of-scope 변경이 하나라도 있으면 APPROVE하지 않는다.

### F2 — Code quality 5-lane

goal/constraints, code quality, security, hands-on QA, context fidelity를 같은 final SHA에서 독립 검토한다. strict Python/TypeScript, transaction/error handling, test quality, dead/duplicate paths, LOC, admin seam, UI slop/token을 확인한다. 다섯 lane 모두 unconditional APPROVE여야 한다.

### F3 — Real manual QA

Task 27 SHA에서 backend/frontend/package와 Browser Matrix를 새로 실행한다. metadata/changelog가 보이는 final UI를 fresh screenshot/Axe/Lighthouse/react QA로 다시 캡처한다. 두 visual reviewer가 375/768/1280, 200%, light/dark/degraded 상태를 독립 확인한다.

### F4 — Scope fidelity

original IN/OUT과 changed-file map, docs links/headings/version/credential literal/policy matrix, 모든 commit의 한국어 본문+7 Lore trailer를 확인한다. `034bd03`과 `1.12.3^{}` ancestry, two-parent merge, dev branch 보존, 1.13 PR/tag/release/main merge/official ZIP/real internal bundle 없음이 조건이다.

### F5 — Security/release audit

1.12.2/historical containment, 1.12.3 release/digest, credential rotation/quarantine, public policy/verifier, CMS internal approval/import boundary, QA ZIP categories를 재검증한다. old URLs 404, known-old credential reject, public forbidden 0, real internal bundle 0, secret evidence 0을 확인한다.

### F6 — push와 PR 직전 중단

F1~F5가 같은 HEAD를 unconditional PASS했는지 확인한 뒤 diff/status/secret/generated staging scan을 실행한다. `1.13.0-dev`를 push하고 divergence `0 0`을 확인한다. ignored artifact로 한국어 PR 제목/본문을 준비하되 `gh pr create`나 `--dry-run`은 실행하지 않는다. tracked worktree clean, open 1.13 PR 없음에서 사용자에게 최종 표를 제공한다.

---

## 10. 다음 에이전트의 정확한 재개 절차

### 10.1 읽기 전용 인수 확인

```powershell
Set-Location D:/Chanil_Park/Project/Programming/AeroOne
git status --short --branch
git worktree list --porcelain
git rev-list --left-right --count HEAD...origin/1.13.0-dev

Set-Location .worktrees/1.12.3-hotfix
git status --short
git rev-list --left-right --count origin/main...HEAD
git log --oneline origin/main..HEAD
```

기대값:

- root `1.13.0-dev@034bd03`, upstream `0 0`
- hotfix local main은 origin/main보다 `0 3`
- hotfix에 63개 dirty 경로
- production env/DB/secure root를 조회·변경하는 명령 없음

### 10.2 backend full 재실행

이전 worker wrapper는 child exit code를 잘못 0으로 반환한 적이 있다. 다음 실행은 stdout/stderr를 파일로 보존하고 process의 실제 exit code와 pytest summary를 모두 확인해야 한다. `-vv` 또는 `--tb=short`를 사용해 실패 node를 회수한다.

```powershell
Set-Location D:/Chanil_Park/Project/Programming/AeroOne/.worktrees/1.12.3-hotfix/backend
$env:PYTHONPATH='.'
& 'D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe' `
  -m pytest tests -vv --tb=short -p no:cacheprovider
```

권장 outer timeout은 75분이다. timeout/interrupt 시 이 실행이 만든 process tree만 정리하고 unrelated `dashboard-enhancements`/다른 저장소 pytest를 건드리지 않는다.

실패 시:

1. nodeid와 traceback을 evidence에 기록한다.
2. 해당 node 단독 RED를 재현한다.
3. fixture 결함인지 product 결함인지 runtime evidence로 구분한다.
4. 최소 수정 후 단독 GREEN.
5. focused 85개와 backend full을 다시 실행한다.

### 10.3 frontend 순차 gate

hotfix worktree에는 `node_modules`가 없다. backend와 병렬 실행하면 안 된다. root의 검증된 node_modules/binary를 hotfix cwd에서 사용하거나 clean install 전략을 명시적으로 택한다. 이전 병렬 시도는 vitest worker 66개를 만들었고 모두 cleanup됐다.

필수 gate:

- frontend full Vitest
- typecheck
- production build
- owned node/vitest worker 0

### 10.4 WPF/manual QA

- `computer-use` skill을 읽고 synthetic masked bundle만 사용한다.
- viewer accessibility tree, 실제 screenshot, XAML fit/keyboard/focus를 확인한다.
- secret 표시/복사 버튼을 누르지 않는다.
- clipboard behavioral test는 원본 capture/restore receipt를 남긴다.
- 창/PID/clipboard/temp를 모두 정리한다.

### 10.5 evidence와 Round 4 review

- `task-3-current-status.md`를 최종 `task-3.md`/`task-3-error.md`로 승격한다.
- Round 4에서 goal/code/security/hands-on QA/context 5개 lane을 독립 실행한다.
- debugging audit는 최소 세 hypothesis를 실제 runtime으로 검증한다.
- 모든 lane이 unconditional PASS여야 한다.
- review worktree/debug journal/temp/listener를 정리한다.

### 10.6 Task 3 커밋

Task 3의 현재 Round 4 diff는 하나의 큰 보안 보강 commit으로 정리할 수 있지만, stage 전에 `git diff --check`, secret/generated artifact scan, actual file list를 재확인한다. 제목/본문은 한국어이고 아래 7개 Lore trailer를 모두 포함한다.

- `Constraint:`
- `Rejected:`
- `Confidence:`
- `Scope-risk:`
- `Directive:`
- `Tested:`
- `Not-tested:`

Task 4는 이 commit과 Round 4 PASS evidence 뒤에만 시작한다.

---

## 11. 금지 사항과 즉시 정지 조건

- hotfix dirty 63개 경로를 reset/checkout/clean/rebase하지 않는다.
- 다른 worktree/저장소의 pytest/node/PowerShell process를 종료하지 않는다.
- Task 3 PASS 전 production env/DB/secure root를 회전하지 않는다.
- secret/hash/raw DB row/clipboard plaintext를 stdout/evidence/Git에 남기지 않는다.
- `APP_ENV` 값 축소, closed_network/production security 면제, offline LAN fallback/firewall scope 완화 금지.
- public package에 env/DB/storage/_database/agent state/dev artifact를 넣지 않는다.
- 1.13.0 PR/tag/release/main merge를 만들지 않는다.
- Sandbox feature 활성화가 재부팅을 요구해도 자동 reboot하지 않는다.

---

## 12. 현실적 남은 시간과 milestone

| Milestone | 예상 작업량 | 외부 조건 |
|---|---:|---|
| Task 3 완전 마감 | 1~3시간 | backend 실패 원인에 따라 증가 가능 |
| Task 4~10 | 6~12시간 | 관리자 elevation, 선택적 reboot, GitHub release |
| Task 11~24 | 12~24시간 | backend/frontend/browser 반복 QA |
| Task 25~27 | 4~8시간 | 전체 문서와 동일 revision QA |
| F1~F6 | 3~6시간 | 독립 reviewers와 final push |

총 잔여량은 약 25~50 agent 작업시간이다. 한 세션에서 완료될 분량으로 가정하지 말고 milestone별 evidence/commit을 남겨 다음 세션이 안전하게 이어받게 한다.

---

## 13. 완료 판정

이 문서는 v1.13.0 완료 증명이 아니다. 다음 조건이 모두 충족될 때만 최종 완료로 대체한다.

- Task 1~27 체크 완료
- F1~F5 unconditional PASS
- `1.13.0-dev` push 후 upstream divergence `0 0`
- tracked worktree clean
- open 1.13 PR/tag/release 없음
- 한국어 PR body artifact 준비
- production credential/package/browser/security evidence가 동일 final revision을 가리킴
