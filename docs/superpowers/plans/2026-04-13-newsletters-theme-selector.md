# Newsletters Theme Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visible Light / Dark selector to `/newsletters` and `/newsletters/[slug]` while keeping `NEWSLETTERS_THEME` as the port-level default.

**Architecture:** Resolve theme from query string first, then environment variable, then `light`. Implement a server-rendered link selector so theme changes are visible, URL-addressable, and free of hydration mismatch risk.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library

---

## File Structure

- `frontend/lib/theme.ts`
  - Add `resolveNewsletterThemeFromSearchParam`.

- `frontend/components/newsletter/newsletter-theme-selector.tsx`
  - New presentational link selector.
  - Generates `/newsletters?theme=light|dark`.
  - Preserves `slug` when present.

- `frontend/app/newsletters/page.tsx`
  - Add `theme?: string` to `SearchParams`.
  - Resolve theme from query first.
  - Render selector above workspace.

- `frontend/app/newsletters/[slug]/page.tsx`
  - Accept `searchParams`.
  - Resolve theme from query first.
  - Render selector above workspace.

- Tests:
  - `frontend/tests/lib/theme.test.ts`
  - `frontend/tests/components/newsletter-theme-selector.test.tsx`
  - `frontend/tests/app/newsletters-layout.test.tsx`
  - `frontend/tests/app/newsletter-detail-page.test.tsx`

---

### Task 1: Add Query Theme Resolution

**Files:**
- Modify: `frontend/lib/theme.ts`
- Create: `frontend/tests/lib/theme.test.ts`

- [ ] **Step 1: Write failing helper tests**

Create `frontend/tests/lib/theme.test.ts`:

```ts
import { resolveNewsletterTheme, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

test('resolves environment theme with light fallback', () => {
  expect(resolveNewsletterTheme('dark')).toBe('dark');
  expect(resolveNewsletterTheme('light')).toBe('light');
  expect(resolveNewsletterTheme('unexpected')).toBe('light');
  expect(resolveNewsletterTheme(undefined)).toBe('light');
});

test('uses query theme before environment theme', () => {
  expect(resolveNewsletterThemeFromSearchParam('dark', 'light')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('light', 'dark')).toBe('light');
  expect(resolveNewsletterThemeFromSearchParam(undefined, 'dark')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('invalid', 'dark')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('invalid', undefined)).toBe('light');
});
```

- [ ] **Step 2: Run helper tests and verify RED**

Run:

```powershell
npm run test -- tests/lib/theme.test.ts
```

Expected:

- FAIL because `resolveNewsletterThemeFromSearchParam` does not exist.

- [ ] **Step 3: Implement helper**

Update `frontend/lib/theme.ts`:

```ts
export type NewsletterTheme = 'light' | 'dark';

export function resolveNewsletterTheme(value = process.env.NEWSLETTERS_THEME): NewsletterTheme {
  return value === 'dark' ? 'dark' : 'light';
}

export function resolveNewsletterThemeFromSearchParam(
  themeParam: string | undefined,
  envValue = process.env.NEWSLETTERS_THEME,
): NewsletterTheme {
  if (themeParam === 'dark' || themeParam === 'light') {
    return themeParam;
  }

  return resolveNewsletterTheme(envValue);
}
```

- [ ] **Step 4: Run helper tests and verify GREEN**

Run:

```powershell
npm run test -- tests/lib/theme.test.ts
```

Expected:

- PASS.

---

### Task 2: Add Theme Selector Component

**Files:**
- Create: `frontend/components/newsletter/newsletter-theme-selector.tsx`
- Create: `frontend/tests/components/newsletter-theme-selector.test.tsx`

- [ ] **Step 1: Write failing selector tests**

Create `frontend/tests/components/newsletter-theme-selector.test.tsx`:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders light and dark links without slug', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const light = screen.getByRole('link', { name: 'Light' });
  const dark = screen.getByRole('link', { name: 'Dark' });

  expect(selector).toBeInTheDocument();
  expect(light).toHaveAttribute('href', '/newsletters?theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?theme=dark');
  expect(light).toHaveAttribute('aria-current', 'true');
  expect(dark).not.toHaveAttribute('aria-current');
});

test('preserves slug in theme links', () => {
  render(<NewsletterThemeSelector theme="dark" slug="newsletter-20260330" />);

  const light = screen.getByRole('link', { name: 'Light' });
  const dark = screen.getByRole('link', { name: 'Dark' });

  expect(light).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=dark');
  expect(dark).toHaveAttribute('aria-current', 'true');
});
```

- [ ] **Step 2: Run selector tests and verify RED**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx
```

Expected:

- FAIL because `NewsletterThemeSelector` does not exist.

- [ ] **Step 3: Implement selector**

Create `frontend/components/newsletter/newsletter-theme-selector.tsx`:

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
  return (
    <section
      data-testid="newsletter-theme-selector"
      className={`mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm ${className}`}
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Theme</p>
        <h2 className="mt-1 text-sm font-semibold text-slate-900">화면 테마 선택</h2>
      </div>
      <div className="flex gap-2">
        {(['light', 'dark'] as const).map((item) => {
          const active = item === theme;
          return (
            <Link
              key={item}
              href={buildThemeHref(item, slug)}
              aria-current={active ? 'true' : undefined}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                active
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200 hover:bg-blue-50'
              }`}
            >
              {item === 'light' ? 'Light' : 'Dark'}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run selector tests and verify GREEN**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx
```

Expected:

- PASS.

---

### Task 3: Integrate Selector Into Newsletter Routes

**Files:**
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`
- Modify: `frontend/tests/app/newsletter-detail-page.test.tsx`

- [ ] **Step 1: Update `/newsletters` route**

In `frontend/app/newsletters/page.tsx`:

```ts
import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';
import { resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
```

Update search params:

```ts
type SearchParams = {
  slug?: string;
  theme?: string;
};
```

Resolve:

```ts
const newsletterTheme = resolveNewsletterThemeFromSearchParam(params.theme);
```

Render before the workspace/list:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={activeDetail?.slug} />
```

- [ ] **Step 2: Update `/newsletters/[slug]` route**

In `frontend/app/newsletters/[slug]/page.tsx`, update function signature:

```ts
export default async function NewsletterDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ theme?: string }>;
})
```

Resolve:

```ts
const query = await searchParams;
const newsletterTheme = resolveNewsletterThemeFromSearchParam(query.theme);
```

Render before workspace:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={detail.slug} />
```

- [ ] **Step 3: Update route tests**

In `frontend/tests/app/newsletters-layout.test.tsx`, add assertions:

```tsx
expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
expect(screen.getByRole('link', { name: 'Light' })).toHaveAttribute(
  'href',
  `/newsletters?slug=${detail.slug}&theme=light`,
);
expect(screen.getByRole('link', { name: 'Dark' })).toHaveAttribute(
  'href',
  `/newsletters?slug=${detail.slug}&theme=dark`,
);
```

Add query precedence test:

```tsx
test('query theme overrides NEWSLETTERS_THEME environment default', async () => {
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  render(await NewslettersPage({ searchParams: Promise.resolve({ theme: 'light' }) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-100');
  expect(screen.getByTestId('newsletters-format-panel')).toHaveClass('bg-white');
  expect(screen.getByRole('link', { name: 'Light' })).toHaveAttribute('aria-current', 'true');
});
```

In `frontend/tests/app/newsletter-detail-page.test.tsx`, mock and assert selector:

```tsx
vi.mock('@/components/newsletter/newsletter-theme-selector', () => ({
  NewsletterThemeSelector: ({ theme, slug }: { theme: string; slug?: string }) => (
    <div data-testid="newsletter-theme-selector" data-theme={theme} data-slug={slug} />
  ),
}));
```

Update calls to include `searchParams`:

```tsx
render(await NewsletterDetailPage({
  params: Promise.resolve({ slug: detail.slug }),
  searchParams: Promise.resolve({ theme: 'dark' }),
}));
```

Assert:

```tsx
expect(screen.getByTestId('newsletter-theme-selector')).toHaveAttribute('data-theme', 'dark');
expect(screen.getByTestId('newsletter-theme-selector')).toHaveAttribute('data-slug', detail.slug);
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
npm run test -- tests/lib/theme.test.ts tests/components/newsletter-theme-selector.test.tsx tests/app/newsletters-layout.test.tsx tests/app/newsletter-detail-page.test.tsx
```

Expected:

- PASS.

---

### Task 4: Full Verification And Runtime Check

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

Run latest build with:

```powershell
$env:NEWSLETTERS_THEME='light'
npx next start -p 29501 --hostname 127.0.0.1
```

```powershell
$env:NEWSLETTERS_THEME='dark'
npx next start -p 29503 --hostname 127.0.0.1
```

Probe:

```powershell
function Probe($url, $label) {
  $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
  $content = $response.Content
  "${label}_STATUS=$($response.StatusCode)"
  "${label}_selector=$($content.Contains('newsletter-theme-selector'))"
  "${label}_dark-panel=$($content.Contains('bg-slate-900/95'))"
  "${label}_white-panel=$($content.Contains('bg-white'))"
}
Probe 'http://127.0.0.1:29501/newsletters' LIGHT_DEFAULT
Probe 'http://127.0.0.1:29501/newsletters?theme=dark' LIGHT_QUERY_DARK
Probe 'http://127.0.0.1:29503/newsletters' DARK_DEFAULT
Probe 'http://127.0.0.1:29503/newsletters?theme=light' DARK_QUERY_LIGHT
```

Expected:

- selector is present for all.
- light default has no `bg-slate-900/95`.
- light query dark has `bg-slate-900/95`.
- dark default has `bg-slate-900/95`.
- dark query light has `bg-white`.

- [ ] **Step 3: Commit with UTF-8 Korean message**

Commit message:

```text
뉴스레터 화면에 테마 선택 링크를 추가한다

NEWSLETTERS_THEME 기반 포트별 기본 테마를 유지하면서 사용자가 화면에서 Light와 Dark를 직접 선택할 수 있도록 query string 기반 selector를 추가했다.
theme query는 환경변수보다 우선하며, slug가 있는 뉴스레터에서도 선택한 날짜를 유지한 채 테마를 바꿀 수 있다.

Constraint: 화면에 테마 선택 UI가 보여야 했다
Rejected: cookie/localStorage 기반 저장 | 서버 렌더링 구조에서 불필요하게 복잡하고 hydration 위험이 있다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: 테마 우선순위는 query -> NEWSLETTERS_THEME -> light 순서를 유지할 것
Tested: npm run test; npm run typecheck; npm run build; runtime probes for 29501/29503 default and query override
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

Use UTF-8 file with `git commit -F`.

---

## Self-Review

Spec coverage:
- Visible selector: Task 2 and Task 3.
- Query overrides env: Task 1 and Task 3.
- `/newsletters` and `[slug]`: Task 3.
- Port defaults still work: Task 4.

Placeholder scan:
- No placeholders remain.

Type consistency:
- `NewsletterTheme`, route `theme?: string`, and selector props are used consistently.
