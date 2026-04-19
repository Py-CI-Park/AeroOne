# Home Hero Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the home-page hero section entirely so the newsletter service card becomes the first visible content, with no replacement copy and no leftover blank space.

**Architecture:** Keep the change extremely small. Delete the top hero `<section>` from `frontend/app/page.tsx`, leave the newsletter card grid unchanged, and add one focused home-page regression test that proves the removed copy stays gone while the newsletter link remains visible.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library

---

## File Structure

- `frontend/app/page.tsx`
  - Home page route.
  - Currently owns both the hero section and the newsletter service card grid.
  - This task should remove only the hero `<section>` and keep the service card grid intact.
- `frontend/tests/app/home-page.test.tsx`
  - New focused home-page regression test.
  - Should verify the removed hero copy is absent and the newsletter service link still exists.

## Notes Before Editing

- The current working tree is clean.
- This is a deletion-focused task. Do not replace the hero with new content, flags, or hidden placeholders.

---

### Task 1: Add a Failing Home-Page Regression Test

**Files:**
- Create: `frontend/tests/app/home-page.test.tsx`

- [ ] **Step 1: Create the failing home-page test**

Create `frontend/tests/app/home-page.test.tsx` with this content:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import HomePage from '@/app/page';

test('removes the home hero copy while keeping the newsletter service link', async () => {
  render(await HomePage());

  expect(screen.queryByText('AeroOne Internal Platform')).not.toBeInTheDocument();
  expect(screen.queryByText('사내 문서형 서비스 시작점')).not.toBeInTheDocument();
  expect(
    screen.queryByText(/현재는 뉴스레터 서비스부터 시작합니다/),
  ).not.toBeInTheDocument();

  expect(screen.getByRole('link', { name: /뉴스레터 서비스/i })).toHaveAttribute(
    'href',
    '/newsletters',
  );
});
```

- [ ] **Step 2: Run the focused test and verify it fails first**

Run:

```powershell
npm run test -- tests/app/home-page.test.tsx
```

Expected:

- FAIL because the hero copy is still rendered in `frontend/app/page.tsx`.

- [ ] **Step 3: Commit the failing-test checkpoint**

Run:

```powershell
git add frontend/tests/app/home-page.test.tsx
git commit -m "홈 히어로 제거 회귀 테스트를 먼저 고정한다"
```

Expected:

- A commit exists containing only the new failing home-page regression test.

---

### Task 2: Remove the Hero Section From the Home Page

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/tests/app/home-page.test.tsx`

- [ ] **Step 1: Remove the hero section from `frontend/app/page.tsx`**

Replace `frontend/app/page.tsx` with this content:

```tsx
import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';

export default function HomePage() {
  return (
    <AppShell title="서비스 대시보드">
      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <ServiceCard
          title="뉴스레터 서비스"
          description="가장 최신 뉴스레터를 바로 보고, 발행 날짜별로 이전 뉴스레터를 탐색합니다."
          href="/newsletters"
          badge="우선 제공"
          icon="🗞"
        />
      </section>
    </AppShell>
  );
}
```

- [ ] **Step 2: Re-run the focused test**

Run:

```powershell
npm run test -- tests/app/home-page.test.tsx
```

Expected:

- PASS.

- [ ] **Step 3: Run the full frontend test suite**

Run:

```powershell
npm run test
```

Expected:

- PASS for the full frontend test suite.

- [ ] **Step 4: Run frontend typecheck**

Run:

```powershell
npm run typecheck
```

Expected:

- PASS.

- [ ] **Step 5: Commit the hero removal**

Run:

```powershell
git add frontend/app/page.tsx frontend/tests/app/home-page.test.tsx
git commit -m "홈 상단 히어로를 제거하고 서비스 카드만 남긴다"
```

Expected:

- A commit exists containing the home-page hero removal and the matching regression test.

---

### Task 3: Final Verification

**Files:**
- No new files in this task.

- [ ] **Step 1: Verify the working tree is clean after tests**

Run:

```powershell
git status --short
```

Expected:

- No uncommitted tracked file changes remain.

- [ ] **Step 2: Optionally verify the home page in the browser**

Run:

```powershell
npm run dev
```

Then open:

- `http://localhost:29501/`

Expected:

- The top hero copy is gone.
- The newsletter service card is the first visible main content.
- The `/newsletters` link still works.

- [ ] **Step 3: If no additional runtime-only changes were needed, stop without a new commit**

This task should end with the implementation commit from Task 2 as the final code change.

---

## Final Verification Checklist

- [ ] `git status --short`
- [ ] `npm run test -- tests/app/home-page.test.tsx`
- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] Manual check of `/`
- [ ] Confirm hero copy is gone
- [ ] Confirm newsletter service card remains visible and linked
