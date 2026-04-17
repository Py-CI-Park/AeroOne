# AppShell Global Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AppShell pages share the same cookie-backed light/dark theme and always show the compact nav theme toggle.

**Architecture:** Add a server theme helper that reads query/cookie/env/default in one place, make AppShell show the selector by default, and update each AppShell page to pass theme and current path.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library

---

## File Structure

- `frontend/lib/server-theme.ts`
  - New server helper for cookie-backed theme resolution.

- `frontend/components/layout/app-shell.tsx`
  - Show theme selector by default.

- App pages:
  - `frontend/app/page.tsx`
  - `frontend/app/login/page.tsx`
  - `frontend/app/newsletters/page.tsx`
  - `frontend/app/newsletters/[slug]/page.tsx`
  - `frontend/app/admin/newsletters/page.tsx`
  - `frontend/app/admin/imports/page.tsx`
  - `frontend/app/admin/newsletters/new/page.tsx`
  - `frontend/app/admin/newsletters/[id]/edit/page.tsx`

- Tests:
  - `frontend/tests/lib/server-theme.test.ts`
  - page tests for home/login/admin/newsletters
  - existing component tests

---

### Task 1: Add Server Theme Helper

**Files:**
- Create: `frontend/lib/server-theme.ts`
- Create: `frontend/tests/lib/server-theme.test.ts`

- [ ] Write failing tests for cookie fallback and query override.
- [ ] Implement `getAppTheme(themeParam?: string)` using `cookies().getAll()`.
- [ ] Run `npm run test -- tests/lib/server-theme.test.ts`.

Expected:

- PASS after implementation.

---

### Task 2: Make AppShell Selector Default-On

**Files:**
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/tests/components/app-shell.test.tsx`

- [ ] Change `showThemeSelector` default from `false` to `true`.
- [ ] Keep opt-out support with `showThemeSelector={false}`.
- [ ] Update tests so default shell renders selector.
- [ ] Run `npm run test -- tests/components/app-shell.test.tsx`.

Expected:

- PASS.

---

### Task 3: Apply Theme To Public Pages

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/login/page.tsx`
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify related tests.

- [ ] Home: make async, read `searchParams`, pass `theme` and `themePath="/"`.
- [ ] Login: use a small server wrapper or split client form so page can resolve theme server-side.
- [ ] Newsletters: replace local cookie code with `getAppTheme`.
- [ ] Newsletter detail: replace local cookie code with `getAppTheme`.
- [ ] Run focused public page tests.

Expected:

- PASS.

---

### Task 4: Apply Theme To Admin Pages

**Files:**
- Modify: `frontend/app/admin/newsletters/page.tsx`
- Modify: `frontend/app/admin/imports/page.tsx`
- Modify: `frontend/app/admin/newsletters/new/page.tsx`
- Modify: `frontend/app/admin/newsletters/[id]/edit/page.tsx`
- Modify or add tests as needed.

- [ ] Keep existing `requireAdminSession()` behavior.
- [ ] Resolve app theme after/before auth guard without changing auth semantics.
- [ ] Pass accurate `themePath`.
- [ ] Run focused admin page tests or typecheck if no page tests exist.

Expected:

- PASS.

---

### Task 5: Full Verification And Runtime Check

**Files:**
- No additional source changes expected.

- [ ] Run:

```powershell
npm run test
npm run typecheck
npm run build
```

- [ ] Runtime check on one frontend port:

```text
http://127.0.0.1:29501/
http://127.0.0.1:29501/login
http://127.0.0.1:29501/newsletters
http://127.0.0.1:29501/newsletters?theme=dark
```

- [ ] Confirm cookie route still sets `aeroone_theme`.
- [ ] Commit with UTF-8 Korean message.

Commit message:

```text
AppShell 전역 테마 유지로 모든 화면을 맞춘다

뉴스레터에 한정되던 테마 처리를 AppShell 사용 화면 전체로 확장했다.
테마는 query, cookie, env, light 순서로 해석되며 홈, 로그인, 관리자, 뉴스레터 화면에서 같은 단일 아이콘 토글을 사용할 수 있다.

Constraint: 사용자가 첫 화면과 전체 화면 이동에서도 테마가 동일하게 유지되길 원했다
Rejected: 뉴스레터 페이지에만 테마 적용 | 홈과 관리자 화면에서 다시 라이트 모드로 보이는 문제가 남는다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: AppShell 페이지를 추가할 때 getAppTheme과 themePath 전달을 함께 적용할 것
Tested: npm run test; npm run typecheck; npm run build; runtime checks for home/login/newsletters
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

---

## Self-Review

Spec coverage:
- Home/login/admin/newsletters theme: Tasks 3-4.
- AppShell default selector: Task 2.
- Cookie persistence: Task 1.
- Full verification: Task 5.

Placeholder scan:
- No placeholders remain.
