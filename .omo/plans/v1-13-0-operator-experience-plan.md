# v1-13-0-operator-experience-plan - Work Plan

## TL;DR (For humans)
**What you'll get:** v1.13.0 개발 브랜치에서 로그인 후 문서/NSA 진입이 자연스럽게 보이고, 계정 메뉴 안에서 내 활동과 관리자 콘솔을 열 수 있게 됩니다. 관리자 콘솔은 첫 화면이 통합 상황판으로 바뀌고, 사용자/세션/모듈 관리 화면은 그래프와 넓은 운영 패널 중심으로 재구성됩니다.

**Why this approach:** 폐쇄망 운영 앱이므로 새 차트/아이콘 런타임 의존성을 늘리지 않고 기존 Next/Tailwind/SVG 체계를 확장합니다. NSA는 이미 서버 권한 모델이 있으므로 보안 정책을 바꾸지 않고 세션/권한 기반 진입점만 정리합니다.

**What it will NOT do:** NSA를 공개 메뉴로 풀지 않습니다. 관리자 감사 로그나 AI 원문을 일반 사용자에게 노출하지 않습니다. README 릴리즈 badge는 개발 초기에 1.13.0으로 바꾸지 않습니다.

**Effort:** Large
**Risk:** Medium - 인증/권한, 관리자 콘솔, 프론트 시각화가 함께 움직이므로 회귀 표면이 넓습니다.
**Decisions I made for you:** 새 런타임 의존성 금지, 로그인 성공 기본 이동은 대시보드, 관리자 진입은 계정 메뉴, 일반 사용자 최근 작업은 기존 로그인/세션/AI 로그 기반, Overview 탭은 기존 탭을 보존하며 첫 탭으로 추가.

Your next move: 이 계획을 실행하려면 별도 실행 지시를 내리세요. 예: `$omo:start-work .omo/plans/v1-13-0-operator-experience-plan.md`

---

> TL;DR (machine): Large / Medium risk / v1.13.0-dev branch, auth-aware nav/account menu, self activity, admin overview charts, user/session/module UX, docs/tests/offline QA.

## Scope
### Must have
- Create `1.13.0-dev` from the current synced `origin/main` before product edits.
- Add root `DESIGN.md` before UI implementation. It must codify AeroOne's existing operational-console style and the richer login treatment.
- Make Document and NSA top-level navigation session-aware:
  - Document is visible for authenticated users and remains consistent with public module access.
  - NSA is visible only when `ClientSession.permissions` contains `collections.nsa.read`, `search.nsa.read`, admin role, or `ClientSession.resources` contains `collection:nsa` with `collections.nsa.read`.
- Replace the current inline Admin link/user pill/logout row with an account menu under the account ID:
  - all authenticated users: account trigger, "내 활동", logout.
  - admins: additionally show "관리자 콘솔" with a proper SVG icon.
  - anonymous users: login link remains available.
- Upgrade login UI to a richer AeroOne command-center sign-in surface:
  - no marketing landing page.
  - preserve labels, autofill, loading/error states, keyboard flow.
  - fix touched mojibake Korean strings.
  - after successful login, route to a safe `next` query value if present, otherwise `/`.
- Add normal-user recent activity:
  - authenticated self-only backend API.
  - frontend API/types.
  - account menu entry and dashboard/activity panel.
  - show recent login/logout, active/recent session, AI request summaries, current AI conversation summaries when available, and accessible module hints.
- Add admin console Overview tab as default first tab:
  - status cards for env/version/DB/newsletters/assets/AI/read tracking.
  - module status chart, asset health chart, user role/activity summary, session/login summary, recent audit list.
  - no new chart library.
- Improve user/session load visualization:
  - wider/taller panels.
  - active sessions and login events remain searchable/sortable.
  - show status distribution and operator-readable load indicators.
- Improve module management UX:
  - expose `required_permission`, `resource_type`, `resource_id`.
  - add safe presets for public document and NSA collection modules.
  - add route/audience/status preview.
  - validate permission fields before create/update.
- Update tests and docs that are directly affected.
- Keep all verification agent-executable with evidence files under `.omo/evidence/`.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Do not weaken `can_read_collection`, `collections.nsa.read`, `search.nsa.read`, or `collection:nsa` ResourceGrant semantics.
- Do not show NSA nav to anonymous/plain users.
- Do not add `lucide-react`, chart libraries, animation libraries, or any new runtime dependency unless the user separately approves that dependency.
- Do not commit `.env`, secrets, generated ZIP files, `dist/`, `_database/`, `node_modules/`, `.venv/`, or existing untracked package folders.
- Do not use emojis as icons in new/touched UI. Use local SVG icons.
- Do not turn the operational app into a landing page.
- Do not hide functionality to satisfy Lighthouse or visual checks.
- Do not update the README version badge to `1.13.0` until the release-final version commit.
- Do not expose global admin audit details to normal users.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: TDD for backend auth/self-activity and permission boundaries; tests-after for visual/admin UI refactors where the existing component tests define the behavior; browser QA after implementation.
- Backend unit/integration:
  - `cd backend && .venv\Scripts\activate && set PYTHONPATH=. && python -m pytest tests -q`
  - add focused tests before backend implementation for self activity and NSA visibility regressions.
- Frontend static/tests:
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`
- Browser QA:
  - production build/server for admin/login/dashboard/activity routes.
  - Playwright screenshots at 375, 768, 1280 widths.
  - keyboard checks for account menu and admin tabs.
  - permission checks for anonymous, normal user, NSA-authorized user, admin.
- Design-system compliance:
  - `DESIGN.md` exists before UI edits.
  - touched UI colors/spacing/icon patterns map back to `DESIGN.md`.
  - no new raw one-off visual language in repeated components.
- Evidence:
  - each todo writes `.omo/evidence/task-<N>-v1-13-0-operator-experience-plan.md`.
  - final wave writes `.omo/evidence/final-v1-13-0-operator-experience-plan.md`.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.
- Wave 0: branch, design system, encoding/copy inventory.
- Wave 1: auth-aware navigation, account menu, login UI and routing.
- Wave 2: self activity backend/frontend.
- Wave 3: admin Overview dashboard and chart primitives.
- Wave 4: user/session load and module management UX.
- Wave 5: docs, full regression, browser/offline smoke, release-readiness notes.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | 2-11 | none |
| 2 | 1 | 3, 4, 6, 8, 9, 10 | 5 backend contract research only |
| 3 | 2 | 4, 6 | 5 |
| 4 | 2, 3 | 6 | 5 |
| 5 | 1 | 6 | 3, 4 |
| 6 | 3, 4, 5 | 11 | 7, 8 after shared types settle |
| 7 | 1 | 8, 9 | 5 |
| 8 | 2, 7 | 11 | 9, 10 |
| 9 | 2, 7 | 11 | 8, 10 |
| 10 | 2, 7 | 11 | 8, 9 |
| 11 | 3-10 | final verification | none |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Create the v1.13.0 development branch and protect unrelated dirty work
  What to do / Must NOT do: Verify branch state, create `1.13.0-dev` from `origin/main`, and record untracked paths that must not be staged. Do not delete or modify `_codex_exports/`, `pkg264_082120*`, `pkg264_082225*`, or prior `.omo` artifacts.
  Parallelization: Wave 0 | Blocked by: none | Blocks: all product work
  References (executor has NO interview context - be exhaustive): AGENTS.md §9 release cycle; `git status --short --branch` observed `main...origin/main`; `git tag --sort=-version:refname` observed latest `1.12.2`; `git branch --all --list *1.13.0*` observed no branch.
  Acceptance criteria (agent-executable): `git branch --show-current` prints `1.13.0-dev`; `git rev-list --left-right --count 1.13.0-dev...origin/main` prints `0 0` immediately after branch creation; evidence lists untracked files not to stage.
  QA scenarios (name the exact tool + invocation): happy: `git status --short --branch` shows `## 1.13.0-dev` plus only pre-existing untracked artifacts. failure: if `1.13.0-dev` already exists, switch to it only after `git rev-parse 1.13.0-dev` and upstream relationship are recorded; do not overwrite. Evidence `.omo/evidence/task-1-v1-13-0-operator-experience-plan.md`
  Commit: N | branch setup only

- [ ] 2. Add `DESIGN.md` and UI execution constraints for AeroOne v1.13.0
  What to do / Must NOT do: Create root `DESIGN.md` from existing AeroOne UI patterns before touching UI code. Include tokens, typography, spacing, surface model, icon rules, chart primitives, login surface direction, admin dashboard layout rules, responsive constraints, accessibility, and accepted debt. Do not invent a marketing-site style.
  Parallelization: Wave 0 | Blocked by: 1 | Blocks: 3, 4, 6, 8, 9, 10
  References (executor has NO interview context - be exhaustive): no `DESIGN.md` found by `rg --files -g "DESIGN.md" -g "design-system.md" -g "design-tokens.md"`; `frontend/package.json:13-30`; `frontend/components/ui/icons.tsx:1`; `frontend/components/layout/app-shell.tsx:44-109`; `frontend/components/admin/admin-console-tabs.tsx:452-523`; `frontend/components/auth/login-form.tsx:21-55`.
  Acceptance criteria (agent-executable): root `DESIGN.md` exists; it has sections for foundations, tokens, primitives, states, motion, responsive behavior, charts, accessibility, and debt; grep confirms no product UI file was edited before `DESIGN.md` exists in the branch history.
  QA scenarios (name the exact tool + invocation): happy: `Test-Path DESIGN.md` and `Select-String -Path DESIGN.md -Pattern "Account menu","Admin overview","Chart"` succeed. failure: if implementation needs a token not in `DESIGN.md`, update `DESIGN.md` first and note it in evidence. Evidence `.omo/evidence/task-2-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `v1.13.0 운영 UI 기준을 먼저 고정`

- [ ] 3. Replace inline admin link with an accessible account menu
  What to do / Must NOT do: Replace or refactor `AdminNavLink` into an account menu component under the account ID. Include SVG icons in `Icon` for admin console, activity, logout, user/account, and menu chevron if needed. The menu must support click, keyboard open/close, Escape, outside click, focus states, admin-only console item, all-user activity item, logout state/error, and anonymous login fallback. Do not show Admin as a separate top-level nav link.
  Parallelization: Wave 1 | Blocked by: 2 | Blocks: 4, 6
  References (executor has NO interview context - be exhaustive): `frontend/components/layout/admin-nav-link.tsx:21-88`; `frontend/components/layout/app-shell.tsx:103`; `frontend/app/api/frontend/session/route.ts:8-65`; `frontend/lib/types.ts:75-88`; `frontend/lib/api.ts:88-96`; `frontend/tests/components/admin-nav-link.test.tsx`; `frontend/tests/components/app-shell.test.tsx`; `frontend/components/ui/icons.tsx:1-127`.
  Acceptance criteria (agent-executable): component tests cover anonymous login fallback, normal user menu without admin item, admin user menu with admin item, logout success/error, Escape close, outside-click close, and focusable menu items; `npm run typecheck` passes.
  QA scenarios (name the exact tool + invocation): happy: Vitest renders an admin session, opens account trigger, finds "관리자 콘솔", "내 활동", and "로그아웃". failure: normal user session opens the menu and `queryByRole('menuitem', { name: /관리자 콘솔/ })` is absent. Evidence `.omo/evidence/task-3-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `계정 메뉴로 관리자 콘솔 진입을 정리`

- [ ] 4. Make AppShell navigation authenticated and permission-aware for Document/NSA
  What to do / Must NOT do: Extend `ActiveNav` to include `nsa`, render NSA only for authorized authenticated users, and keep Document visible after login. Use `ClientSession.permissions/resources/isAdmin` hints without trusting the frontend as the authorization boundary; backend collection APIs remain authoritative. Set `/nsa` page active state to `nsa`. Do not show NSA to anonymous or unauthorized plain users.
  Parallelization: Wave 1 | Blocked by: 2, 3 | Blocks: 6
  References (executor has NO interview context - be exhaustive): `frontend/components/layout/app-shell.tsx:13-17`, `frontend/components/layout/app-shell.tsx:69-103`; `frontend/app/nsa/page.tsx`; `frontend/app/documents/page.tsx`; `frontend/app/api/frontend/session/route.ts:8-65`; `backend/app/modules/admin/api.py:353-379`; `backend/app/modules/collections/policy.py:9-29`; `backend/tests/unit/test_admin_permissions.py:107-134`; `frontend/tests/app/nsa-page.test.tsx`; `frontend/tests/app/documents-page.test.tsx`; `frontend/tests/app/home-page.test.tsx:163-195`.
  Acceptance criteria (agent-executable): frontend tests prove nav states for anonymous, normal authenticated, NSA-authorized, and admin sessions; backend tests still prove unauthorized NSA collection access fails; `/nsa` active state is test-visible.
  QA scenarios (name the exact tool + invocation): happy: Vitest mocked session with `collections.nsa.read` sees NSA nav link to `/nsa`; mocked normal session sees Document but not NSA. failure: direct `/api/frontend/collections/nsa/list` unauthorized proxy test remains 401/403. Evidence `.omo/evidence/task-4-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `권한 기반 문서 네비게이션을 정비`

- [ ] 5. Add self-scoped recent activity backend contract
  What to do / Must NOT do: Add authenticated self activity response models and endpoint under auth, preferably `GET /api/v1/auth/activity`. Include current user identity, recent login/logout events for that user, active/recent sessions for that user, recent AI request metadata for that user, and accessible service module hints. If touching AI chat persistence, only populate `AiConversation.user_id` for authenticated chats as metadata; do not broaden conversation read permissions beyond session ownership. Do not expose admin audit logs or newsletter IP read tracking as user-owned work.
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 6
  References (executor has NO interview context - be exhaustive): `backend/app/modules/auth/api.py:79-89`; `backend/app/modules/auth/schemas.py:11-22`; `backend/app/modules/admin/models.py:87-121`; `backend/app/modules/admin/models.py:148-162`; `backend/app/modules/admin/api.py:368-379`; `backend/app/modules/ai/models.py:24-40`; `backend/app/modules/ai/api/public.py:145-262`; `backend/tests/integration/test_ai_api.py`; `backend/tests/integration/test_admin_operations_api.py:174-221`.
  Acceptance criteria (agent-executable): new backend tests fail before implementation and pass after: unauthenticated activity returns 401; user A cannot see user B login/session/AI logs; authorized user sees only their data; accessible modules include Document and include NSA only with permission; response omits prompt/answer/snippet content.
  QA scenarios (name the exact tool + invocation): happy: `python -m pytest tests/integration/test_auth_activity_api.py -q` creates a normal user, logs in, inserts own AI request metadata, and gets only self rows. failure: same test inserts other user's rows and asserts they are absent. Evidence `.omo/evidence/task-5-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `일반 사용자 활동 조회 계약을 추가`

- [ ] 6. Build normal-user activity UI and login route behavior
  What to do / Must NOT do: Add frontend types/API for self activity, a user-facing activity route or dashboard panel, and wire the account menu "내 활동" item to it. Upgrade login UI per `DESIGN.md`, fix touched Korean strings, preserve form semantics, show loading/error, support safe `next` redirect, and default success redirect to `/`. Do not default every login to `/admin`.
  Parallelization: Wave 2 | Blocked by: 3, 4, 5 | Blocks: 11
  References (executor has NO interview context - be exhaustive): `frontend/components/auth/login-form.tsx:7-26`; `frontend/app/login/page.tsx`; `frontend/lib/api.ts:88-96`, `frontend/lib/api.ts:333-341`; `frontend/lib/types.ts:75-88`; `frontend/tests/components/login-form.test.tsx`; `frontend/tests/lib/api.test.ts:151-173`; `frontend/app/api/frontend/auth/[...segments]/route.ts`; `frontend/app/page.tsx`.
  Acceptance criteria (agent-executable): tests cover successful login to `/`, safe `next` redirect, unsafe external `next` ignored, login loading/error UI, normal user activity render, unauthenticated activity redirect/login prompt, and account menu item linking to activity. `npm run typecheck` passes.
  QA scenarios (name the exact tool + invocation): happy: Playwright logs in as normal user, verifies landing at dashboard, opens account menu, enters "내 활동", and sees own recent session/login. failure: mocked self activity 401 leads to login state without crashing; malicious `?next=https://example.com` redirects to `/`. Evidence `.omo/evidence/task-6-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `사용자 활동 화면과 로그인 흐름을 개선`

- [ ] 7. Add admin dashboard chart primitives and data derivation helpers
  What to do / Must NOT do: Create small reusable, dependency-free visual primitives for KPI cards, status bars, donut/ring gauge, horizontal bar list, and simple sparkline/timeline. Add pure helper functions that derive overview metrics from existing `AdminSummary`, `ConnectedUsersResponse`, users, modules, health, AI status, and audits. Do not introduce a chart dependency. Do not place cards inside cards.
  Parallelization: Wave 3 | Blocked by: 1 | Blocks: 8, 9, 10
  References (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx:75-96`; `frontend/components/admin/admin-console-tabs.tsx:270-296`; `frontend/components/admin/admin-console-tabs.tsx:452-523`; `frontend/lib/types.ts:123-150`; `backend/app/modules/admin/schemas.py:215-235`; `DESIGN.md`.
  Acceptance criteria (agent-executable): helper unit tests cover empty state, normal mixed state, all-failure asset state, no AI state, and role/module distributions. Chart components expose accessible labels and do not require browser-only APIs to render under Vitest.
  QA scenarios (name the exact tool + invocation): happy: `npm run test -- --run frontend/tests/components/admin-overview-metrics.test.tsx` renders charts from fixture data and asserts ARIA labels/values. failure: empty arrays render "데이터 없음" style states and no division-by-zero/NaN text. Evidence `.omo/evidence/task-7-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `관리자 상황판 시각화 기반을 추가`

- [ ] 8. Make admin Overview the default first console tab
  What to do / Must NOT do: Add `overview` to admin tabs as the default active tab. Move existing top summary cards into a dedicated Overview section and extend it with charts and recent audit highlights. Keep all existing tabs and CRUD workflows. Rework number shortcuts so `1` activates Overview and the 10th tab has either `0` or no shortcut with visible/accessibility-safe behavior documented in tests.
  Parallelization: Wave 3 | Blocked by: 2, 7 | Blocks: 11
  References (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx:217-244`; `frontend/components/admin/admin-console-tabs.tsx:435-446`; `frontend/components/admin/admin-console-tabs.tsx:452-523`; `frontend/tests/components/admin-console-tabs.test.tsx`; `frontend/tests/components/admin-diagnostics.test.tsx`; `frontend/tests/components/admin-audit-section.test.tsx`.
  Acceptance criteria (agent-executable): tests prove default selected tab is Overview, existing tab contents are still reachable by click/keyboard, summary charts render from fetched state, refresh still loads all required keys, and no existing admin tests regress.
  QA scenarios (name the exact tool + invocation): happy: Playwright opens `/admin`, sees Overview KPI/charts before any tab click, then keyboard ArrowRight reaches modules/users/sessions. failure: mocked admin API failure shows existing toast/error and Overview empty/degraded state without crashing. Evidence `.omo/evidence/task-8-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `관리자 콘솔 첫 화면을 통합 상황판으로 전환`

- [ ] 9. Strengthen user/session load visualization and vertical panel ergonomics
  What to do / Must NOT do: Refactor sessions/users visual panels to be taller, denser, and easier to scan. Add login status distribution, active user list summary, failed-login indicator, last-refresh state, and responsive vertical scroll regions. Use existing `ListFilter`, `ListPagination`, and chart primitives. Do not remove search/sort/pagination/autorefresh/purge workflows.
  Parallelization: Wave 4 | Blocked by: 2, 7 | Blocks: 11
  References (executor has NO interview context - be exhaustive): `frontend/components/admin/sections/admin-sessions-section.tsx:18-139`; `frontend/components/admin/sections/admin-users-section.tsx`; `frontend/components/admin/widgets/list-filter.tsx`; `backend/app/modules/admin/api.py:410-427`; `backend/app/modules/admin/schemas.py:203-220`; `frontend/tests/components/admin-sessions-autorefresh.test.tsx`; `frontend/tests/components/g003-session-list-redteam.test.tsx`; `frontend/tests/components/admin-list-ux.test.tsx`.
  Acceptance criteria (agent-executable): tests verify autorefresh still refreshes only `connectedUsers`, purge still works, login event filtering/pagination remains, new charts have accessible names, empty/error states are readable, and vertical containers do not clip long Korean labels.
  QA scenarios (name the exact tool + invocation): happy: Playwright on 1280 and 768 widths captures Sessions/User panels with taller lists and visible graphs. failure: 375 width has no horizontal overflow and controls wrap without overlap. Evidence `.omo/evidence/task-9-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `사용자와 세션 로드 가시성을 높임`

- [ ] 10. Redesign module management for permission-aware modules
  What to do / Must NOT do: Expand `ModuleDraft` and module forms to include `required_permission`, `resource_type`, and `resource_id`. Add presets for public document and NSA collection modules, a compact route/status/audience preview, clearer validation, and a more scannable table/card layout. Preserve add/update/delete/toggle behavior and audit refresh. Do not let invalid permission/resource combinations submit.
  Parallelization: Wave 4 | Blocked by: 2, 7 | Blocks: 11
  References (executor has NO interview context - be exhaustive): `frontend/components/admin/admin-console-tabs.tsx:75`, `frontend/components/admin/admin-console-tabs.tsx:131-141`, `frontend/components/admin/admin-console-tabs.tsx:321-329`; `frontend/components/admin/sections/admin-modules-section.tsx:8-104`, `frontend/components/admin/sections/admin-modules-section.tsx:174-198`; `backend/app/modules/admin/schemas.py:142-194`; `backend/app/modules/admin/api.py:663-697`; `frontend/tests/components/admin-console-tabs.test.tsx:306-401`; `frontend/tests/components/admin-rbac-widgets.test.tsx:225-230`; `frontend/tests/components/admin-list-ux.test.tsx:168`.
  Acceptance criteria (agent-executable): tests prove existing modules round-trip permission fields, NSA preset creates `required_permission=collections.nsa.read`, `resource_type=collection`, `resource_id=nsa`, invalid resource ID/permission prevents submit, update payload includes changed permission fields, and create/update failure toasts remain.
  QA scenarios (name the exact tool + invocation): happy: Vitest fills NSA preset and asserts `createServiceModule` receives all permission fields. failure: resource id `../nsa` or permission mismatch shows inline error and does not call API. Evidence `.omo/evidence/task-10-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `권한형 모듈 관리를 UI에서 안전하게 처리`

- [ ] 11. Update documentation, release notes, and full regression evidence
  What to do / Must NOT do: Update docs that users/operators rely on: README feature descriptions only where behavior changed, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/runbook/windows-offline.md`, and a new phase report for v1.13.0 operator experience. Do not update README version badge or "릴리스 1.13.0 기준" line until release-final commit. Run full backend/frontend verification and browser smoke. If offline ZIP packaging is exercised, do not commit `dist/`.
  Parallelization: Wave 5 | Blocked by: 3-10 | Blocks: final verification
  References (executor has NO interview context - be exhaustive): AGENTS.md §5, §9; `README.md:66-75`, `README.md:94-97`, `README.md:289-314`, `README.md:318-331`; `docs/INDEX.md:5`, `docs/INDEX.md:70-75`, `docs/INDEX.md:120-138`, `docs/INDEX.md:158`; `docs/CLOSED_NETWORK_GUIDE.md`; `docs/runbook/windows-offline.md`.
  Acceptance criteria (agent-executable): docs mention account menu/admin console entry, self activity, Overview dashboard, permission-aware module management, and NSA nav semantics. Full test commands pass or pre-existing failures are isolated with logs. Release docs explain that version badge remains 1.12.2 until release-final.
  QA scenarios (name the exact tool + invocation): happy: run backend pytest, frontend typecheck/test/build, then browser smoke for `/login`, `/`, `/activity` or equivalent, `/admin`, `/documents`, `/nsa` with authorized and unauthorized users. failure: grep docs for premature `version-1.13.0` badge before release-final and fail if found. Evidence `.omo/evidence/task-11-v1-13-0-operator-experience-plan.md`
  Commit: Y | 제목: `v1.13.0 운영 경험 개선 문서를 정리`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit
  Verify every Must have is mapped to changed files/tests/evidence; verify every Must NOT guardrail with grep/tests; write `.omo/evidence/final-v1-13-0-operator-experience-plan.md`.
- [ ] F2. Code quality review
  Review diffs for authz weakening, untyped TypeScript, raw UI tokens not in `DESIGN.md`, over-large components, and unrelated refactors.
- [ ] F3. Real manual QA
  Use a real browser against production build. Capture screenshots for login, dashboard nav states, account menu, self activity, admin Overview, sessions/users, modules at 375/768/1280.
- [ ] F4. Scope fidelity
  Confirm no dependency additions, no release badge bump, no secrets/generated artifacts, no `_database` content, no `dist` ZIP, no unrelated file churn.

## Commit strategy
- Use multiple Korean commits, one per behavioral wave, preserving unrelated dirty work.
- Every commit message must follow repository Lore trailer rules:
  - Korean title and body.
  - include `Constraint`, `Rejected`, `Confidence`, `Scope-risk`, `Directive`, `Tested`, `Not-tested`.
- Recommended commit grouping:
  1. `v1.13.0 운영 UI 기준을 먼저 고정`
  2. `계정 메뉴와 권한 기반 문서 네비게이션을 정비`
  3. `일반 사용자 활동 조회와 화면을 추가`
  4. `관리자 콘솔 통합 상황판을 강화`
  5. `사용자 세션과 모듈 관리 UX를 개선`
  6. `v1.13.0 운영 경험 문서와 검증 근거를 정리`
- Do not squash the eventual dev branch into main; the release process requires no-ff merge.

## Success criteria
- `1.13.0-dev` exists and contains only intentional product/docs/plan evidence changes.
- Login no longer sends every user directly to `/admin`; safe redirect/default dashboard behavior is tested.
- Account ID opens a menu; admins see an icon+label admin console item; normal users do not.
- Document is visible after login; NSA is visible only for authorized users and direct unauthorized access still fails server-side.
- Normal users can view their own recent activity without seeing global admin audit data.
- Admin console opens on Overview and shows meaningful status charts/graphs without new runtime dependencies.
- User/session panels are taller, visually summarized, searchable, and keyboard/browser QA verified.
- Module management can safely edit permission-gated modules including NSA.
- Backend pytest, frontend typecheck, frontend Vitest, frontend build, and browser smoke are recorded.
- Docs reflect the new behavior and do not prematurely claim a 1.13.0 release badge.
