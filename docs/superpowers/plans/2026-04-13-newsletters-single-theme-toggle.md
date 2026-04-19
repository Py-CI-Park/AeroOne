# Newsletters Single Theme Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two theme icons with one small icon that toggles to the opposite theme.

**Architecture:** Keep the existing query-string link strategy and nav placement. Simplify `NewsletterThemeSelector` so it renders one link computed from the current theme.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library

---

## File Structure

- `frontend/components/newsletter/newsletter-theme-selector.tsx`
  - Render one opposite-theme link instead of two links.

- `frontend/tests/components/newsletter-theme-selector.test.tsx`
  - Verify light renders moon link to dark.
  - Verify dark renders sun link to light.
  - Verify slug is preserved.

- `frontend/tests/components/app-shell.test.tsx`
  - Update nav selector expectations to one link.

- `frontend/tests/app/newsletters-layout.test.tsx`
  - Update route selector expectations to one link.

---

### Task 1: Update Selector Tests

**Files:**
- Modify: `frontend/tests/components/newsletter-theme-selector.test.tsx`

- [ ] **Step 1: Replace tests**

Use:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders one moon icon that switches light theme to dark', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const toggle = screen.getByRole('link', { name: '다크 테마로 전환' });

  expect(selector).toBeInTheDocument();
  expect(toggle).toHaveTextContent('☾');
  expect(toggle).toHaveAttribute('href', '/newsletters?theme=dark');
  expect(screen.queryByRole('link', { name: '라이트 테마로 전환' })).not.toBeInTheDocument();
});

test('renders one sun icon that switches dark theme to light and preserves slug', () => {
  render(<NewsletterThemeSelector theme="dark" slug="newsletter-20260330" />);

  const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

  expect(toggle).toHaveTextContent('☀');
  expect(toggle).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx
```

Expected:

- FAIL because current selector renders two links.

---

### Task 2: Implement Single Toggle

**Files:**
- Modify: `frontend/components/newsletter/newsletter-theme-selector.tsx`

- [ ] **Step 1: Replace selector implementation**

Use:

```tsx
import React from 'react';
import Link from 'next/link';

import type { NewsletterTheme } from '@/lib/theme';

function buildThemeHref(theme: NewsletterTheme, slug?: string) {
  const params = new URLSearchParams();
  if (slug) {
    params.set('slug', slug);
  }
  params.set('theme', theme);

  return `/newsletters?${params.toString()}`;
}

export function NewsletterThemeSelector({
  theme,
  slug,
  className = '',
}: {
  theme: NewsletterTheme;
  slug?: string;
  className?: string;
}) {
  const nextTheme: NewsletterTheme = theme === 'dark' ? 'light' : 'dark';
  const label = nextTheme === 'dark' ? '다크 테마로 전환' : '라이트 테마로 전환';
  const icon = nextTheme === 'dark' ? '☾' : '☀';

  return (
    <span data-testid="newsletter-theme-selector" className={`inline-flex items-center ${className}`}>
      <Link
        href={buildThemeHref(nextTheme, slug)}
        aria-label={label}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-xs leading-none text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
      >
        {icon}
      </Link>
    </span>
  );
}
```

- [ ] **Step 2: Run selector tests and verify GREEN**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx
```

Expected:

- PASS.

---

### Task 3: Update Integration Tests

**Files:**
- Modify: `frontend/tests/components/app-shell.test.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`

- [ ] **Step 1: Update AppShell test**

In `frontend/tests/components/app-shell.test.tsx`, change the opted-in selector assertion to:

```tsx
const toggle = screen.getByRole('link', { name: '라이트 테마로 전환' });

expect(login.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
expect(toggle).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
expect(toggle).toHaveTextContent('☀');
expect(screen.queryByRole('link', { name: '다크 테마로 전환' })).not.toBeInTheDocument();
```

- [ ] **Step 2: Update newsletters layout test**

In `frontend/tests/app/newsletters-layout.test.tsx`, change the selector assertion to:

```tsx
const darkToggle = screen.getByRole('link', { name: '다크 테마로 전환' });

expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
expect(darkToggle).toHaveAttribute('href', `/newsletters?slug=${detail.slug}&theme=dark`);
expect(darkToggle).toHaveTextContent('☾');
expect(screen.queryByRole('link', { name: '라이트 테마로 전환' })).not.toBeInTheDocument();
```

In the query override light test:

```tsx
expect(screen.getByRole('link', { name: '다크 테마로 전환' })).toHaveAttribute(
  'href',
  `/newsletters?slug=${detail.slug}&theme=dark`,
);
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx tests/components/app-shell.test.tsx tests/app/newsletters-layout.test.tsx
```

Expected:

- PASS.

---

### Task 4: Verify And Commit

**Files:**
- No extra source changes expected.

- [ ] **Step 1: Full verification**

Run:

```powershell
npm run test
npm run typecheck
npm run build
```

Expected:

- all pass.

- [ ] **Step 2: Runtime probe**

Run:

```powershell
function Probe($url, $label) {
  $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
  $content = $response.Content
  "${label}_STATUS=$($response.StatusCode)"
  "${label}_selector=$($content.Contains('newsletter-theme-selector'))"
  "${label}_sun=$($content.Contains('☀'))"
  "${label}_moon=$($content.Contains('☾'))"
  "${label}_dark-panel=$($content.Contains('bg-slate-900/95'))"
}
Probe 'http://127.0.0.1:29501/newsletters' DEFAULT_29501
Probe 'http://127.0.0.1:29501/newsletters?theme=dark' DARK_QUERY_29501
```

Expected:

- default light contains moon.
- dark query contains sun.

- [ ] **Step 3: Commit**

Use UTF-8 `git commit -F` with:

```text
뉴스레터 테마 선택을 단일 아이콘 토글로 줄인다

로그인 옆 테마 선택을 두 개의 해/달 링크에서 현재 테마의 반대 방향으로 전환하는 하나의 아이콘 링크로 단순화했다.
라이트 상태에서는 달 아이콘으로 다크 테마에 이동하고, 다크 상태에서는 해 아이콘으로 라이트 테마에 이동한다.

Constraint: 사용자가 한 아이콘으로 다크/라이트를 조절하길 원했다
Rejected: 해와 달 아이콘 두 개 유지 | 요청한 단일 토글 방식과 맞지 않는다
Confidence: 높음
Scope-risk: 좁음
Reversibility: 깔끔함
Directive: 테마 selector는 로그인 옆 단일 반대방향 토글로 유지할 것
Tested: npm run test; npm run typecheck; npm run build; single-port 29501 probes
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

---

## Self-Review

Spec coverage:
- One icon only: Tasks 1-3.
- Opposite theme link: Tasks 1-3.
- Slug preserved: Task 1.
- Single port runtime: Task 4.

Placeholder scan:
- No placeholders remain.
