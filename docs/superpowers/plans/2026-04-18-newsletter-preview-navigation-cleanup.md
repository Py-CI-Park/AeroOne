# Newsletter Preview Navigation Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the public Newsletter UI, show the selected issue date in preview, add previous/next issue navigation, and document why admin login remains necessary.

**Architecture:** Keep the existing `/newsletters` server data flow and `NewslettersWorkspace` client shell. Compute issue date and adjacent navigation in the route from `calendarEntries`, then pass display props into `NewsletterPreviewPanel` through `NewslettersWorkspace`; keep `NewsletterDetailClient` preview-only.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library

---

## File Structure

- `frontend/app/page.tsx`
  - Rename public home card title to `Newsletter`.
  - Keep the home card icon removed.

- `frontend/app/newsletters/page.tsx`
  - Rename page title to `Newsletter`.
  - Compute selected issue display date.
  - Compute previous/next issue links from `calendarEntries`.
  - Preserve current theme in generated issue links.

- `frontend/components/layout/app-shell.tsx`
  - Rename top navigation Newsletter link to `Newsletter`.
  - Keep login/admin links and single theme toggle.

- `frontend/components/newsletter/newsletters-workspace.tsx`
  - Accept `displayDate` and `dateNavigation`.
  - Pass them to `NewsletterPreviewPanel`.

- `frontend/components/newsletter/newsletter-preview-panel.tsx`
  - Render optional selected issue date.
  - Render previous/next issue navigation.
  - Keep asset badge and preview children.

- `docs/runbook/admin-auth.md`
  - Document why admin login remains necessary.

---

### Task 1: Rename Public Newsletter Labels

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/tests/app/home-page.test.tsx`
- Modify: `frontend/tests/components/app-shell.test.tsx`

- [ ] **Step 1: Write failing label tests**

Update `frontend/tests/app/home-page.test.tsx` so the home card is found by `Newsletter` and the old public labels are absent:

```tsx
const newsletterLink = screen.getByRole('link', { name: /Newsletter/i });

expect(newsletterLink).toHaveAttribute('href', '/newsletters');
expect(newsletterLink).toHaveTextContent('Open the latest issue and browse previous issues by date.');
expect(newsletterLink).toHaveTextContent('활성 서비스');
expect(screen.queryByText('뉴스레터 서비스')).not.toBeInTheDocument();
expect(screen.queryByText('뉴스레터')).not.toBeInTheDocument();
```

Update `frontend/tests/components/app-shell.test.tsx` so the nav link is English:

```tsx
expect(screen.getByRole('link', { name: 'Newsletter' })).toHaveAttribute('href', '/newsletters');
expect(screen.queryByRole('link', { name: '뉴스레터' })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run label tests and verify RED**

```powershell
npm run test -- tests/app/home-page.test.tsx tests/components/app-shell.test.tsx
```

Expected: FAIL while the UI still renders old public labels.

- [ ] **Step 3: Implement label changes**

In `frontend/app/page.tsx`:

```tsx
<ServiceCard
  title="Newsletter"
  description="Open the latest issue and browse previous issues by date."
  href="/newsletters"
  badge="활성 서비스"
/>
```

In `frontend/components/layout/app-shell.tsx`:

```tsx
<Link href="/newsletters">Newsletter</Link>
```

- [ ] **Step 4: Run label tests and verify GREEN**

```powershell
npm run test -- tests/app/home-page.test.tsx tests/components/app-shell.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

Use `git commit -F` with a UTF-8 message file. Commit title:

```text
공개 Newsletter 명칭을 영어로 통일한다
```

---

### Task 2: Add Preview Date And Previous/Next Navigation

**Files:**
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/components/newsletter/newsletters-workspace.tsx`
- Modify: `frontend/components/newsletter/newsletter-preview-panel.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`
- Modify: `frontend/tests/components/newsletter-preview-panel.test.tsx`

- [ ] **Step 1: Add preview panel tests**

Add this test to `frontend/tests/components/newsletter-preview-panel.test.tsx`:

```tsx
test('renders selected issue date and previous next navigation', () => {
  render(
    <NewsletterPreviewPanel
      title="Aerospace Daily News"
      selectedAsset="html"
      displayDate="2026-03-26"
      dateNavigation={{
        previous: { label: '이전 날짜', href: '/newsletters?slug=old&theme=dark' },
        next: { label: '다음 날짜', href: '/newsletters?slug=new&theme=dark' },
      }}
      theme="dark"
    >
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByText('2026-03-26')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '이전 날짜' })).toHaveAttribute('href', '/newsletters?slug=old&theme=dark');
  expect(screen.getByRole('link', { name: '다음 날짜' })).toHaveAttribute('href', '/newsletters?slug=new&theme=dark');
});
```

Add this boundary test:

```tsx
test('renders disabled previous next labels when adjacent issues are missing', () => {
  render(
    <NewsletterPreviewPanel title="Only Issue" selectedAsset="html" displayDate="2026-03-26">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByText('이전 날짜')).toHaveAttribute('aria-disabled', 'true');
  expect(screen.getByText('다음 날짜')).toHaveAttribute('aria-disabled', 'true');
});
```

- [ ] **Step 2: Add route-level navigation tests**

In `frontend/tests/app/newsletters-layout.test.tsx`, use these calendar entries:

```tsx
const calendarEntries: NewsletterCalendarEntry[] = [
  { date: '2026-03-31', slug: 'newer-newsletter', title: 'Newer Newsletter', source_type: detail.source_type },
  { date: '2026-03-30', slug: detail.slug, title: detail.title, source_type: detail.source_type },
  { date: '2026-03-29', slug: 'older-newsletter', title: 'Older Newsletter', source_type: detail.source_type },
];
```

Add assertions:

```tsx
expect(screen.getByText('2026-03-30')).toBeInTheDocument();
expect(screen.getByRole('link', { name: '이전 날짜' })).toHaveAttribute(
  'href',
  '/newsletters?slug=older-newsletter&theme=dark',
);
expect(screen.getByRole('link', { name: '다음 날짜' })).toHaveAttribute(
  'href',
  '/newsletters?slug=newer-newsletter&theme=dark',
);
```

- [ ] **Step 3: Run navigation tests and verify RED**

```powershell
npm run test -- tests/components/newsletter-preview-panel.test.tsx tests/app/newsletters-layout.test.tsx
```

Expected: FAIL because preview date and navigation props are not implemented.

- [ ] **Step 4: Implement preview panel props**

In `frontend/components/newsletter/newsletter-preview-panel.tsx`, add:

```ts
type NewsletterDateNavigation = {
  previous?: { label: string; href: string };
  next?: { label: string; href: string };
};
```

Add props:

```ts
displayDate?: string;
dateNavigation?: NewsletterDateNavigation;
```

Render date and nav links in the header. Missing previous/next should render disabled spans with `aria-disabled="true"`.

- [ ] **Step 5: Thread props through workspace**

In `frontend/components/newsletter/newsletters-workspace.tsx`, accept:

```ts
displayDate?: string;
dateNavigation?: NewsletterDateNavigation;
```

Pass both to `NewsletterPreviewPanel`.

- [ ] **Step 6: Compute date and navigation in route**

In `frontend/app/newsletters/page.tsx`, compute:

```ts
const displayDate = activeDetail?.published_at?.slice(0, 10)
  ?? calendarEntries.find((entry) => entry.slug === activeDetail?.slug)?.date;
```

Compute adjacent links from sorted `calendarEntries`:

```ts
const sortedEntries = [...calendarEntries].sort((left, right) => right.date.localeCompare(left.date));
const index = sortedEntries.findIndex((entry) => entry.slug === activeDetail?.slug);
const newer = index > 0 ? sortedEntries[index - 1] : undefined;
const older = index >= 0 ? sortedEntries[index + 1] : undefined;
const dateNavigation = index >= 0 ? {
  previous: older ? { label: '이전 날짜', href: `/newsletters?slug=${older.slug}&theme=${newsletterTheme}` } : undefined,
  next: newer ? { label: '다음 날짜', href: `/newsletters?slug=${newer.slug}&theme=${newsletterTheme}` } : undefined,
} : undefined;
```

Pass `displayDate` and `dateNavigation` to `NewslettersWorkspace`.

- [ ] **Step 7: Run navigation tests and verify GREEN**

```powershell
npm run test -- tests/components/newsletter-preview-panel.test.tsx tests/app/newsletters-layout.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

Use `git commit -F` with a UTF-8 message file. Commit title:

```text
Newsletter 미리보기에 날짜와 이전 다음 이동을 추가한다
```

---

### Task 3: Document And Protect Admin Login Requirement

**Files:**
- Create: `docs/runbook/admin-auth.md`
- Create: `frontend/tests/app/admin-auth-required.test.ts`

- [ ] **Step 1: Add admin auth runbook**

Create `docs/runbook/admin-auth.md`:

```md
# Admin Authentication

Public Newsletter reading does not require login.

Admin login remains required because admin screens can change local Newsletter data:

- Import / Sync
- Newsletter creation
- Newsletter updates
- soft delete / inactive state changes
- thumbnail upload
- category and tag mutations

Development credentials are read from `backend/.env`:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

Do not remove authentication from `/admin/*` routes unless all mutation and sync functionality is removed or moved behind another trust boundary.
```

- [ ] **Step 2: Add admin auth smoke test**

Create `frontend/tests/app/admin-auth-required.test.ts`:

```ts
import { requireAdminSession } from '@/lib/server-auth';

test('admin pages still require an admin session helper', () => {
  expect(requireAdminSession).toBeTypeOf('function');
});
```

- [ ] **Step 3: Run auth test**

```powershell
npm run test -- tests/app/admin-auth-required.test.ts
```

Expected: PASS.

- [ ] **Step 4: Commit**

Use `git commit -F` with a UTF-8 message file. Commit title:

```text
관리자 로그인 유지 이유를 문서화한다
```

---

### Task 4: Final Verification

**Files:**
- No additional source changes expected.

- [ ] **Step 1: Run full verification**

```powershell
npm run test
npm run typecheck
npm run build
```

Expected: all pass.

- [ ] **Step 2: Runtime check**

Use one frontend port:

```text
http://127.0.0.1:29501/
http://127.0.0.1:29501/newsletters
http://127.0.0.1:29501/newsletters?theme=dark
```

Verify:

- home card title is `Newsletter`
- nav link is `Newsletter`
- preview shows selected issue date
- preview has previous/next date navigation
- dark theme date links include `theme=dark`

---

## Self-Review

Spec coverage:

- Public naming: Task 1.
- Preview date: Task 2.
- Previous/next navigation: Task 2.
- Theme preservation: Task 2.
- Admin login review: Task 3.
- Final verification: Task 4.

Placeholder scan:

- No placeholders remain.

Type consistency:

- `NewsletterDateNavigation` is introduced in Task 2 and threaded through `NewslettersWorkspace` and `NewsletterPreviewPanel`.
