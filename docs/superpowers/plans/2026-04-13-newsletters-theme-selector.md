# Newsletters Single-Port Theme Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visible Light / Dark selector to `/newsletters` and `/newsletters/[slug]` while running only one frontend on port `29501`.

**Architecture:** Resolve theme from query string first, then optional environment fallback, then `light`. Implement a server-rendered link selector so one frontend instance can render both `?theme=light` and `?theme=dark`.

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

In `frontend/tests/app/newsletters-layout.test.tsx`, assert the selector and query precedence:

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

Update the page call:

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

### Task 4: Full Verification And Single-Port Runtime Check

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

- [ ] **Step 2: Run one frontend port**

Use `start.bat` or `next start` on `29501`. Do not start `29503` for normal verification.

Preferred:

```powershell
.\start.bat
```

Fallback if backend is already running and only frontend is needed:

```powershell
npx next start -p 29501 --hostname 127.0.0.1
```

- [ ] **Step 3: Verify single-port theme switching**

Run:

```powershell
function Probe($url, $label) {
  $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
  $content = $response.Content
  "${label}_STATUS=$($response.StatusCode)"
  "${label}_selector=$($content.Contains('newsletter-theme-selector'))"
  "${label}_dark-panel=$($content.Contains('bg-slate-900/95'))"
  "${label}_dark-shell=$($content.Contains('bg-slate-950'))"
  "${label}_white-panel=$($content.Contains('bg-white'))"
}
Probe 'http://127.0.0.1:29501/newsletters' DEFAULT_29501
Probe 'http://127.0.0.1:29501/newsletters?theme=dark' DARK_QUERY_29501
Probe 'http://127.0.0.1:29501/newsletters?theme=light' LIGHT_QUERY_29501
```

Expected:

```text
DEFAULT_29501_STATUS=200
DEFAULT_29501_selector=True
DEFAULT_29501_dark-panel=False
DEFAULT_29501_white-panel=True
DARK_QUERY_29501_STATUS=200
DARK_QUERY_29501_selector=True
DARK_QUERY_29501_dark-panel=True
DARK_QUERY_29501_dark-shell=True
LIGHT_QUERY_29501_STATUS=200
LIGHT_QUERY_29501_selector=True
LIGHT_QUERY_29501_dark-panel=False
LIGHT_QUERY_29501_white-panel=True
```

- [ ] **Step 4: Commit with UTF-8 Korean message**

Commit message:

```text
뉴스레터 단일 포트 테마 선택 흐름으로 정리한다

프론트엔드를 여러 포트로 나누지 않고 29501 하나에서 Light와 Dark를 query string으로 선택하도록 spec과 plan을 정리했다.
테마 선택 UI는 같은 포트의 /newsletters 화면에서 동작하며, NEWSLETTERS_THEME는 query가 없을 때의 선택적 기본값으로만 남긴다.

Constraint: 사용자는 여러 프론트엔드 포트가 아니라 하나의 포트에서 테마를 선택하길 원했다
Rejected: 29503을 공식 다크 테마 포트로 유지 | 제품 동작과 다르고 검증 흐름을 혼란스럽게 만든다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: 정상 실행 검증은 29501 단일 포트에서 /newsletters, /newsletters?theme=dark, /newsletters?theme=light를 확인할 것
Tested: npm run test; npm run typecheck; npm run build; single-port 29501 probes for default/dark/light query
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

Use UTF-8 file with `git commit -F`.

---

## Self-Review

Spec coverage:
- Visible selector: Tasks 2-3.
- Query overrides env: Tasks 1 and 3.
- Single frontend port only: Task 4.
- No official `29503`: Task 4.

Placeholder scan:
- No placeholders remain.

Type consistency:
- `NewsletterTheme`, route `theme?: string`, and selector props are used consistently.
