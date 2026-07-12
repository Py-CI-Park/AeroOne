AeroOne v1.13.0 운영 경험·패키지 안전성 개발을 중단점부터 이어서 완주한다.

결정 완료 계획: `.omo/plans/v1-13-0-operator-experience-plan.md`
상태 보고서: `docs/reports/v1-13-0-development-status-2026-07-11.md`
재개 절차: `docs/runbook/ai-agent-handoff-2026-07-11.md`
각 goal의 세부 acceptance·Must NOT·QA·commit 정책은 위 계획 원문과 상태 보고서 §4·§9를 진실 원천으로 따른다.

전역 제약(모든 goal 공통, 위반 시 즉시 중단):
- 제품 코드 변경은 `.worktrees/1.12.3-hotfix`(local `main@d6628dd`, 63 dirty)에 있다. reset/checkout/clean/rebase/squash 금지 — 사용자 작업이다.
- `1.13.0-dev` root에서 제품 코드를 직접 수정하지 않는다.
- production `.env`, canonical DB, `%USERPROFILE%/AeroOne-secure`는 Task 4 owner 승인 전까지 건드리지 않는다.
- Task 3이 backend/frontend/WPF/Round 4 review까지 unconditional PASS 하기 전 Task 4 실제 자격증명 회전을 실행하지 않는다.
- 각 gate의 명시 조건 충족 전 commit/push/tag/release/PR 금지. 1.13.0 main merge/tag/release/PR 생성은 F6 직전까지 금지.
- 커밋은 한국어 제목·본문 + 7개 Lore trailer(AGENTS.md §3).
- unrelated worktree(dashboard-enhancements, release-1.7.0)와 다른 저장소 프로세스를 종료하지 않는다.

@goal: Task 3 자격증명 회전 도구 완전 마감
Round 4 구현이 끝난 `.worktrees/1.12.3-hotfix`의 DB-aware 자격증명 회전 도구를 unconditional PASS로 마감한다. backend full(369 tests)을 새 로그·실제 exit-code 보존 방식으로 재실행해 실패 node를 단독 RED→최소 수정→단독 GREEN→focused 85→full 순으로 격리 해결한다. 그 뒤 frontend(vitest full/typecheck/build), WPF viewer 독립 QA(synthetic masked bundle만, secret 표시/복사 금지), evidence 갱신, Round 4 5-lane review(goal/code/security/QA/context)와 3-hypothesis runtime audit를 모두 unconditional PASS로 통과시킨 뒤 debug journal·review worktree·temp·listener를 정리하고 한국어 Round 4 commit을 만든다. Task 3 plan checkbox와 boulder/ledger를 동기화한다. production `.env`/DB/secure root는 절대 건드리지 않는다.

@goal: Task 4 실제 workspace 자격증명·세션 회전과 quarantine
Task 3이 완전 PASS하고 commit된 뒤에만 실행한다. 현재 workspace의 실제 `.env`/canonical DB의 전체 계정 비밀번호·JWT·session을 검증된 회전 도구로 단일 transaction 회전하고, 노출 가능 이전 자격증명을 immutable quarantine으로 봉쇄한다. production secret/hash/DB row/clipboard plaintext를 출력하지 않는다. 실제 production 자격증명·secure root를 변경하므로 owner의 명시 승인이 반드시 선행되어야 한다.

@goal: Task 5~9 안전 패키저·내부 번들·1.12.3 릴리스
public package allow-list policy와 pre/post ZIP verifier(Task 5), `git archive` 기반 builder·exact installer·Windows Sandbox offline smoke(Task 6), CMS 승인 기반 내부 data bundle·역할별 독립 서명·trust chain·atomic import(Task 7), Next 15.2.9 exact pin과 1.12.3 metadata/incident/운영 문서(Task 8), 1.12.3 full verify/tag/package/Sandbox/GitHub release(Task 9)를 TDD로 구현·검증한다. Sandbox 부재나 `RestartNeeded=true`, GitHub release는 owner 승인/관리자 elevation이 필요한 지점이다. prerequisite PASS 전 tag 금지.

@goal: Task 10 1.12.3 계보를 1.13.0-dev에 no-ff merge
root dev worktree에서 OMO plan/evidence를 먼저 보존한 뒤 `origin/main`의 verified 1.12.3 ancestry를 `1.13.0-dev`에 `--no-ff` merge하고 OMO state를 동기화한다. rebase/squash/cherry-pick으로 hotfix 계보를 단순화하지 않는다. 한국어 merge commit + Lore trailer.

@goal: Task 11~15 제품 기반 계층
`DESIGN.md`와 frontend design state로 시각 언어를 선고정(11), exact-pinned QA dependency와 production-browser harness를 외부 CDN/Chromium download 없이 구성(12), backend admin seam 추출과 NSA module 상태를 모든 delivery surface에 fail-closed로 강제(13), frontend admin loader/tab registry/section shell 분리와 partial failure 처리(14), single client session provider와 canonical NSA visibility helper(15)를 TDD로 구현한다. frontend 권한을 authority로 취급하지 않는다.

@goal: Task 16~24 사용자 흐름과 관리자 콘솔 UX
account menu·Document/NSA nav·AI scope의 shared session 계약 전환(16), status-preserving API error와 safe next redirect/login(17), self-only `GET /api/v1/auth/activity` + composite index migration(18), `/activity` UI와 typed contract 연결(19), 24h Overview backend와 실제 session 집계(20), module access tuple server validator(21), dependency-free horizontal charts·Overview default(22), Users/Sessions 실제 부하·paging·autorefresh·purge UX(23), Module create/edit access presets/preview(24)를 구현한다. 가짜 0/합성 차트 금지, 실제 backend 값만 표시, 민감 식별자·본문 반환 금지.

@goal: Task 25~27 문서·통합 QA·릴리스 메타데이터
최종 구현 문서화와 최신 handoff·운영/보안 문서 동기화(25), 동일 revision에서 backend/frontend/package/migration/browser/Axe/Lighthouse/react 전체 QA를 fresh artifact로 재실행하고 두 visual review PASS(26), README/backend/changelog의 release-final 1.13.0 metadata-only 마지막 dev commit(27)을 수행한다. 이 중간 상태 문서를 최종 구현 상태로 승격한다. annotated tag/official release/main merge/기능 동시 변경 금지.

@goal: F1~F6 최종 검증과 PR 직전 정지
plan compliance audit(F1), 5-lane code quality review 전부 unconditional PASS(F2), 최종 SHA에서 real manual QA browser matrix(F3), scope fidelity·commit/Lore/ancestry/out-of-scope 0(F4), security/release audit로 containment/rotation/package/internal boundary 재검증(F5)를 통과한 뒤 dev push와 한국어 PR body를 준비하고 `gh pr create` 실행 직전에 정지한다(F6). PR 생성은 하지 않는다.
