# Newsletters Nav Theme Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the newsletters theme selector out of the page body and render it as tiny sun/moon icons next to `로그인` in the top navigation.

**Architecture:** Keep query-string theme switching and the existing `NewsletterThemeSelector` component, but make it compact and let `AppShell` own the nav placement. Newsletter routes opt into the selector by passing `showThemeSelector` and `themeSlug` to `AppShell`.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library

---

## File Structure

- `frontend/components/newsletter/newsletter-theme-selector.tsx`
  - Convert from large card selector to compact icon selector.
  - Preserve link generation and slug preservation.

- `frontend/components/layout/app-shell.tsx`
  - Add `showThemeSelector?: boolean`.
  - Add `themeSlug?: string`.
  - Render `NewsletterThemeSelector` after `로그인` only when `showThemeSelector` is true.

- `frontend/app/newsletters/page.tsx`
  - Remove body-level `NewsletterThemeSelector`.
  - Pass `showThemeSelector` and `themeSlug` to `AppShell`.

- `frontend/app/newsletters/[slug]/page.tsx`
  - Remove body-level `NewsletterThemeSelector`.
  - Pass `showThemeSelector` and `themeSlug` to `AppShell`.

- Tests:
  - `frontend/tests/components/newsletter-theme-selector.test.tsx`
  - `frontend/tests/components/app-shell.test.tsx`
  - `frontend/tests/app/newsletters-layout.test.tsx`
  - `frontend/tests/app/newsletter-detail-page.test.tsx`

---

### Task 1: Convert Theme Selector To Compact Icon Links

**Files:**
- Modify: `frontend/components/newsletter/newsletter-theme-selector.tsx`
- Modify: `frontend/tests/components/newsletter-theme-selector.test.tsx`

- [ ] **Step 1: Replace selector tests with icon/aria-label contract**

Replace `frontend/tests/components/newsletter-theme-selector.test.tsx` with:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';

test('renders compact sun and moon links without slug', () => {
  render(<NewsletterThemeSelector theme="light" />);

  const selector = screen.getByTestId('newsletter-theme-selector');
  const light = screen.getByRole('link', { name: '라이트 테마' });
  const dark = screen.getByRole('link', { name: '다크 테마' });

  expect(selector).toBeInTheDocument();
  expect(selector).not.toHaveTextContent('화면 테마 선택');
  expect(selector).not.toHaveTextContent('Light');
  expect(selector).not.toHaveTextContent('Dark');
  expect(light).toHaveTextContent('☀');
  expect(dark).toHaveTextContent('☾');
  expect(light).toHaveAttribute('href', '/newsletters?theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?theme=dark');
  expect(light).toHaveAttribute('aria-current', 'true');
  expect(dark).not.toHaveAttribute('aria-current');
});

test('preserves slug in compact theme links', () => {
  render(<NewsletterThemeSelector theme="dark" slug="newsletter-20260330" />);

  const light = screen.getByRole('link', { name: '라이트 테마' });
  const dark = screen.getByRole('link', { name: '다크 테마' });

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

- FAIL because the current selector renders `Light`, `Dark`, and body-card text.

- [ ] **Step 3: Replace selector component**

Replace `frontend/components/newsletter/newsletter-theme-selector.tsx` with:

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
    <span data-testid="newsletter-theme-selector" className={`inline-flex items-center gap-1 ${className}`}>
      {(['light', 'dark'] as const).map((item) => {
        const active = item === theme;
        return (
          <Link
            key={item}
            href={buildThemeHref(item, slug)}
            aria-label={item === 'light' ? '라이트 테마' : '다크 테마'}
            aria-current={active ? 'true' : undefined}
            className={`inline-flex h-7 w-7 items-center justify-center rounded-full border text-xs leading-none transition ${
              active
                ? 'border-slate-900 bg-slate-900 text-white'
                : 'border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700'
            }`}
          >
            {item === 'light' ? '☀' : '☾'}
          </Link>
        );
      })}
    </span>
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

### Task 2: Move Selector Into AppShell Nav

**Files:**
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/tests/components/app-shell.test.tsx`

- [ ] **Step 1: Update AppShell tests**

Replace `frontend/tests/components/app-shell.test.tsx` with:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

test('renders the default shell with light theme classes and no theme selector', () => {
  render(
    <AppShell title="Light Shell">
      <p>content</p>
    </AppShell>,
  );

  const shell = screen.getByTestId('app-shell');
  const header = screen.getByTestId('app-shell-header');

  expect(shell).toHaveClass('bg-slate-100');
  expect(header).toHaveClass('bg-white');
  expect(screen.getByRole('heading', { name: 'Light Shell' })).toHaveClass('text-slate-900');
  expect(screen.getByText('사내 뉴스레터 / 문서 플랫폼')).toBeInTheDocument();
  expect(screen.queryByTestId('newsletter-theme-selector')).not.toBeInTheDocument();
});

test('renders a dark shell when theme is dark', () => {
  render(
    <AppShell title="Dark Shell" theme="dark">
      <p>content</p>
    </AppShell>,
  );

  const shell = screen.getByTestId('app-shell');
  const header = screen.getByTestId('app-shell-header');

  expect(shell).toHaveClass('bg-slate-950');
  expect(header).toHaveClass('bg-slate-950');
  expect(screen.getByRole('heading', { name: 'Dark Shell' })).toHaveClass('text-slate-100');
});

test('renders compact theme selector after login when opted in', () => {
  render(
    <AppShell title="Theme Shell" theme="dark" showThemeSelector themeSlug="newsletter-20260330">
      <p>content</p>
    </AppShell>,
  );

  const login = screen.getByRole('link', { name: '로그인' });
  const selector = screen.getByTestId('newsletter-theme-selector');
  const light = screen.getByRole('link', { name: '라이트 테마' });
  const dark = screen.getByRole('link', { name: '다크 테마' });

  expect(login.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(light).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=light');
  expect(dark).toHaveAttribute('href', '/newsletters?slug=newsletter-20260330&theme=dark');
  expect(dark).toHaveAttribute('aria-current', 'true');
});
```

- [ ] **Step 2: Run AppShell tests and verify RED**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx
```

Expected:

- FAIL because `showThemeSelector` and `themeSlug` are not implemented yet.

- [ ] **Step 3: Update AppShell implementation**

Update `frontend/components/layout/app-shell.tsx`:

```tsx
import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';
```

Add props:

```ts
showThemeSelector = false,
themeSlug,
```

Add types:

```ts
showThemeSelector?: boolean;
themeSlug?: string;
```

Render immediately after login:

```tsx
<Link href="/login">로그인</Link>
{showThemeSelector ? <NewsletterThemeSelector theme={theme} slug={themeSlug} /> : null}
```

- [ ] **Step 4: Run AppShell tests and verify GREEN**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx
```

Expected:

- PASS.

---

### Task 3: Remove Body-Level Selector From Newsletter Routes

**Files:**
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`
- Modify: `frontend/tests/app/newsletter-detail-page.test.tsx`

- [ ] **Step 1: Update `/newsletters` route**

Remove:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={activeDetail?.slug} />
```

Remove import:

```ts
import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';
```

Pass selector props to AppShell:

```tsx
<AppShell
  title="뉴스레터 서비스"
  contentClassName="max-w-[1600px]"
  theme={newsletterTheme}
  showThemeSelector
  themeSlug={activeDetail?.slug}
>
```

- [ ] **Step 2: Update `/newsletters/[slug]` route**

Remove:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={detail.slug} />
```

Remove import:

```ts
import { NewsletterThemeSelector } from '@/components/newsletter/newsletter-theme-selector';
```

Pass selector props to AppShell:

```tsx
<AppShell title={detail.title} theme={newsletterTheme} showThemeSelector themeSlug={detail.slug}>
```

- [ ] **Step 3: Update route tests**

In `frontend/tests/app/newsletters-layout.test.tsx`, keep selector assertions but make them nav-icon based:

```tsx
expect(screen.getByTestId('newsletter-theme-selector')).toBeInTheDocument();
expect(screen.queryByText('화면 테마 선택')).not.toBeInTheDocument();
expect(screen.getByRole('link', { name: '라이트 테마' })).toHaveAttribute(
  'href',
  `/newsletters?slug=${detail.slug}&theme=light`,
);
expect(screen.getByRole('link', { name: '다크 테마' })).toHaveAttribute(
  'href',
  `/newsletters?slug=${detail.slug}&theme=dark`,
);
```

In the query override test:

```tsx
expect(screen.getByRole('link', { name: '라이트 테마' })).toHaveAttribute('aria-current', 'true');
```

In `frontend/tests/app/newsletter-detail-page.test.tsx`, remove the `NewsletterThemeSelector` mock and assert `AppShell` props if AppShell is not mocked. If needed, mock `AppShell` to expose `showThemeSelector` and `themeSlug`:

```tsx
vi.mock('@/components/layout/app-shell', () => ({
  AppShell: ({
    title,
    children,
    theme,
    showThemeSelector,
    themeSlug,
  }: {
    title: string;
    children: React.ReactNode;
    theme?: string;
    showThemeSelector?: boolean;
    themeSlug?: string;
  }) => (
    <div data-testid="app-shell" data-theme={theme} data-show-theme-selector={String(Boolean(showThemeSelector))} data-theme-slug={themeSlug}>
      <h1>{title}</h1>
      {children}
    </div>
  ),
}));
```

Assert:

```tsx
expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark');
expect(screen.getByTestId('app-shell')).toHaveAttribute('data-show-theme-selector', 'true');
expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme-slug', detail.slug);
```

- [ ] **Step 4: Run route tests and verify GREEN**

Run:

```powershell
npm run test -- tests/app/newsletters-layout.test.tsx tests/app/newsletter-detail-page.test.tsx
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

- [ ] **Step 2: Verify one frontend port**

Ensure only port `29501` is needed for frontend verification.

Probe:

```powershell
function Probe($url, $label) {
  $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
  $content = $response.Content
  "${label}_STATUS=$($response.StatusCode)"
  "${label}_selector=$($content.Contains('newsletter-theme-selector'))"
  "${label}_body-label=$($content.Contains('화면 테마 선택'))"
  "${label}_dark-panel=$($content.Contains('bg-slate-900/95'))"
  "${label}_dark-shell=$($content.Contains('bg-slate-950'))"
  "${label}_white-panel=$($content.Contains('bg-white'))"
}
Probe 'http://127.0.0.1:29501/newsletters' DEFAULT_29501
Probe 'http://127.0.0.1:29501/newsletters?theme=dark' DARK_QUERY_29501
Probe 'http://127.0.0.1:29501/newsletters?theme=light' LIGHT_QUERY_29501
```

Expected:

- selector true for all.
- body-label false for all.
- dark query has dark panel and shell.
- light/default have white panel and no dark shell.
- no `29503` frontend is required.

- [ ] **Step 3: Commit with UTF-8 Korean message**

Commit message:

```text
뉴스레터 테마 선택을 로그인 옆 아이콘으로 옮긴다

본문의 큰 Light/Dark 선택 카드를 제거하고 AppShell 네비게이션의 로그인 링크 옆에 작은 해와 달 아이콘 selector를 배치했다.
테마 전환은 계속 같은 29501 포트에서 query string으로 동작하며, 뉴스레터 slug가 있는 경우에도 선택 상태를 유지한다.

Constraint: 사용자가 테마 선택을 로그인 옆 아주 작은 해와 달 아이콘으로 요청했다
Rejected: 본문 카드형 selector 유지 | 페이지 콘텐츠처럼 보여 위치 요구와 맞지 않는다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: 테마 selector는 AppShell opt-in nav 요소로 유지하고 본문 카드로 되돌리지 말 것
Tested: npm run test; npm run typecheck; npm run build; single-port 29501 probes for default/dark/light query
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

Use UTF-8 file with `git commit -F`.

---

## Self-Review

Spec coverage:
- Small nav icons next to login: Tasks 1-3.
- Body selector removed: Task 3.
- Single port only: Task 4.
- Accessibility labels: Task 1.

Placeholder scan:
- No placeholders remain.

Type consistency:
- `NewsletterThemeSelector` props remain stable.
- `AppShell` adds only optional opt-in props.
