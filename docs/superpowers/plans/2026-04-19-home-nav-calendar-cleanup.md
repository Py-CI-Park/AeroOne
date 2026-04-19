# Home Navigation And Calendar Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the public `Newsletter` nav link, remove the home card description, and make the Newsletter calendar collapsed by default.

**Architecture:** Keep the `/newsletters` route and home service card as the public Newsletter entry point, but simplify the header and home card copy. Keep `NewsletterDateCalendar` behavior intact and only change its initial open state from expanded to collapsed.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library

---

## File Structure

- `frontend/components/layout/app-shell.tsx`
  - Remove the `/newsletters` text link from the header nav.
  - Keep the dashboard link and theme toggle.
  - Normalize labels touched in this file.

- `frontend/app/page.tsx`
  - Keep the home card link to `/newsletters`.
  - Remove the home card description prop.
  - Keep the title `Newsletter`.

- `frontend/components/dashboard/service-card.tsx`
  - Make `description` optional.
  - Do not render a paragraph when description is missing.

- `frontend/components/newsletter/newsletter-date-calendar.tsx`
  - Start collapsed by default.
  - Keep expand/collapse button.
  - Normalize labels touched in this file.

- `frontend/tests/components/app-shell.test.tsx`
  - Assert the header does not expose a `Newsletter` nav link.

- `frontend/tests/app/home-page.test.tsx`
  - Assert the home card has no description.

- `frontend/tests/components/service-card.test.tsx`
  - Assert `ServiceCard` works without description.

- `frontend/tests/components/newsletter-date-calendar.test.tsx`
  - Assert calendar starts collapsed and expands on click.

---

### Task 1: Remove Header Newsletter Link And Home Card Description

**Files:**
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/dashboard/service-card.tsx`
- Modify: `frontend/tests/components/app-shell.test.tsx`
- Modify: `frontend/tests/app/home-page.test.tsx`
- Modify: `frontend/tests/components/service-card.test.tsx`

- [ ] **Step 1: Update AppShell test first**

In `frontend/tests/components/app-shell.test.tsx`, update the default shell test to assert there is no public `Newsletter` nav link:

```tsx
expect(screen.getByRole('link', { name: '대시보드' })).toHaveAttribute('href', '/');
expect(screen.queryByRole('link', { name: 'Newsletter' })).not.toBeInTheDocument();
expect(screen.queryByRole('link', { name: '관리자' })).not.toBeInTheDocument();
expect(screen.queryByRole('link', { name: '로그인' })).not.toBeInTheDocument();
expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
```

Also update the theme selector order test to compare the selector after the dashboard link:

```tsx
const dashboard = screen.getByRole('link', { name: '대시보드' });
const selector = screen.getByTestId('newsletter-theme-selector');

expect(dashboard.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
```

- [ ] **Step 2: Update home and ServiceCard tests**

In `frontend/tests/app/home-page.test.tsx`, assert the home card has no old description:

```tsx
const newsletterLink = within(screen.getByRole('main')).getByRole('link', { name: /Newsletter/i });

expect(newsletterLink).toHaveAttribute('href', '/newsletters');
expect(newsletterLink).not.toHaveTextContent('Open the latest issue and browse previous issues by date.');
expect(newsletterLink).toHaveTextContent('활성 서비스');
expect(screen.queryByTestId('service-card-icon')).not.toBeInTheDocument();
expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
```

In `frontend/tests/components/service-card.test.tsx`, assert missing description does not render an empty paragraph:

```tsx
render(
  <ServiceCard
    title="Newsletter"
    href="/newsletters"
    badge="활성 서비스"
  />,
);

const card = screen.getByRole('link', { name: /Newsletter/i });

expect(card).toHaveAttribute('href', '/newsletters');
expect(card).not.toHaveTextContent('Open the latest issue and browse previous issues by date.');
expect(screen.queryByTestId('service-card-description')).not.toBeInTheDocument();
```

Keep the existing description-capable case:

```tsx
render(
  <ServiceCard
    title="문서"
    description="문서 설명"
    href="/docs"
    badge="활성 서비스"
  />,
);

expect(screen.getByTestId('service-card-description')).toHaveTextContent('문서 설명');
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx tests/app/home-page.test.tsx tests/components/service-card.test.tsx
```

Expected:

- FAIL because the header still renders the `Newsletter` nav link.
- FAIL because the home card still renders the description.
- FAIL because `ServiceCard.description` is still required and/or rendered unconditionally.

- [ ] **Step 4: Implement header and card cleanup**

In `frontend/components/layout/app-shell.tsx`, keep only dashboard and theme toggle in nav:

```tsx
<nav className={`flex gap-4 text-sm ${dark ? 'text-slate-300' : 'text-slate-600'}`}>
  <Link href="/">대시보드</Link>
  {showThemeSelector ? <NewsletterThemeSelector theme={theme} currentPath={themePath} /> : null}
</nav>
```

In `frontend/app/page.tsx`, remove the `description` prop:

```tsx
<ServiceCard
  title="Newsletter"
  href="/newsletters"
  badge="활성 서비스"
/>
```

In `frontend/components/dashboard/service-card.tsx`, make description optional:

```ts
description?: string;
```

Render it conditionally:

```tsx
{description ? (
  <p data-testid="service-card-description" className="mt-3 text-sm leading-6 text-slate-600">
    {description}
  </p>
) : null}
```

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx tests/app/home-page.test.tsx tests/components/service-card.test.tsx
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

Use UTF-8 `git commit -F`.

Commit title:

```text
홈 내비게이션과 Newsletter 카드 설명을 줄인다
```

---

### Task 2: Start Calendar Collapsed

**Files:**
- Modify: `frontend/components/newsletter/newsletter-date-calendar.tsx`
- Modify: `frontend/tests/components/newsletter-date-calendar.test.tsx`

- [ ] **Step 1: Update calendar tests first**

In `frontend/tests/components/newsletter-date-calendar.test.tsx`, update the light calendar test:

```tsx
const toggle = screen.getByRole('button', { name: '달력 펼치기' });
const calendarGrid = screen.getByTestId('newsletter-calendar-grid');

expect(calendarGrid).not.toBeVisible();

fireEvent.click(toggle);

expect(screen.getByRole('button', { name: '달력 접기' })).toHaveAttribute('aria-expanded', 'true');
expect(calendarGrid).toBeVisible();
```

For dark calendar test:

```tsx
expect(screen.getByRole('button', { name: '달력 펼치기' })).toHaveAttribute('aria-expanded', 'false');
expect(screen.getByTestId('newsletter-calendar-grid')).not.toBeVisible();
```

Keep theme link expectations:

```tsx
expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
  'href',
  '/newsletters?slug=newsletter-20260326&theme=dark',
);
```

- [ ] **Step 2: Run calendar test and verify RED**

Run:

```powershell
npm run test -- tests/components/newsletter-date-calendar.test.tsx
```

Expected:

- FAIL because the calendar currently starts expanded.

- [ ] **Step 3: Implement collapsed default**

In `frontend/components/newsletter/newsletter-date-calendar.tsx`, change:

```ts
const [open, setOpen] = useState(true);
```

to:

```ts
const [open, setOpen] = useState(false);
```

Normalize button labels if needed:

```tsx
{open ? '달력 접기' : '달력 펼치기'}
```

- [ ] **Step 4: Run calendar test and verify GREEN**

Run:

```powershell
npm run test -- tests/components/newsletter-date-calendar.test.tsx
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

Use UTF-8 `git commit -F`.

Commit title:

```text
Newsletter 달력을 기본 접힘 상태로 시작한다
```

---

### Task 3: Full Verification And Runtime Check

**Files:**
- No additional source changes expected.

- [ ] **Step 1: Run full verification**

Run:

```powershell
npm run test
npm run typecheck
npm run build
```

Expected:

- all pass.

- [ ] **Step 2: Runtime check**

Run the app on one frontend port:

```powershell
.\start.bat
```

Verify:

```text
http://127.0.0.1:29501/
http://127.0.0.1:29501/newsletters
http://127.0.0.1:29501/newsletters?theme=dark
```

Expected:

- home header has no `Newsletter` nav text link
- home card still links to `/newsletters`
- home card has no description text
- theme toggle remains visible
- newsletter calendar starts collapsed
- clicking `달력 펼치기` opens calendar
- dark mode still works

- [ ] **Step 3: Commit only if verification changes files**

No commit expected unless verification modifies tracked files.

---

## Self-Review

Spec coverage:

- Header Newsletter link removal: Task 1.
- Home card description removal: Task 1.
- Calendar collapsed default: Task 2.
- Theme persistence not regressed: Task 3.
- Touched-file mojibake cleanup: Tasks 1 and 2.

Placeholder scan:

- No placeholders remain.

Type consistency:

- `ServiceCard.description` becomes optional and tests use the same prop shape.
