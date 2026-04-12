# Newsletters Runtime Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the latest `/newsletters` implementation as light on `29501` and dark on `29503` without relying on the old `d735c76` comparison worktree.

**Architecture:** Add a tiny `NewsletterTheme` layer and thread it from server routes into AppShell and newsletter panels. Keep the existing report-style structure intact and vary only theme classes based on `NEWSLETTERS_THEME`, defaulting to `light`.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Vitest, Testing Library, PowerShell, Git

---

## File Structure

- `frontend/lib/theme.ts`
  - Create shared `NewsletterTheme` type and resolver.

- `frontend/components/layout/app-shell.tsx`
  - Add optional `theme` prop.
  - Keep default light shell.
  - Add dark shell classes for newsletter dark runtime.

- `frontend/app/newsletters/page.tsx`
  - Resolve `newsletterTheme`.
  - Pass theme to `AppShell`, `NewsletterDateCalendar`, and `NewslettersWorkspace`.

- `frontend/app/newsletters/[slug]/page.tsx`
  - Resolve `newsletterTheme`.
  - Pass theme to `AppShell` and `NewslettersWorkspace`.

- `frontend/components/newsletter/newsletters-workspace.tsx`
  - Accept optional `theme`.
  - Pass theme to selector and preview panel.

- `frontend/components/newsletter/newsletter-date-calendar.tsx`
  - Accept optional `theme`.
  - Preserve collapse/expand behavior.
  - Switch classes between light and dark.

- `frontend/components/newsletter/newsletter-asset-selector.tsx`
  - Accept optional `theme`.
  - Preserve card semantics.
  - Switch classes between light and dark.

- `frontend/components/newsletter/newsletter-preview-panel.tsx`
  - Accept optional `theme`.
  - Preserve preview structure.
  - Switch classes between light and dark.

- Tests:
  - `frontend/tests/components/app-shell.test.tsx`
  - `frontend/tests/components/newsletter-date-calendar.test.tsx`
  - `frontend/tests/components/newsletter-asset-selector.test.tsx`
  - `frontend/tests/components/newsletter-preview-panel.test.tsx`
  - `frontend/tests/app/newsletters-layout.test.tsx`
  - `frontend/tests/app/newsletter-detail-page.test.tsx`

---

### Task 1: Add Theme Type And AppShell Theme Support

**Files:**
- Create: `frontend/lib/theme.ts`
- Modify: `frontend/components/layout/app-shell.tsx`
- Create: `frontend/tests/components/app-shell.test.tsx`

- [ ] **Step 1: Write the failing AppShell tests**

Create `frontend/tests/components/app-shell.test.tsx`:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { AppShell } from '@/components/layout/app-shell';

test('renders the default shell with light theme classes', () => {
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
```

- [ ] **Step 2: Run the AppShell test and verify RED**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx
```

Expected:

- FAIL because `AppShell` does not accept `theme`.
- FAIL because `app-shell` and `app-shell-header` test ids do not exist yet.

- [ ] **Step 3: Add theme utilities**

Create `frontend/lib/theme.ts`:

```ts
export type NewsletterTheme = 'light' | 'dark';

export function resolveNewsletterTheme(value = process.env.NEWSLETTERS_THEME): NewsletterTheme {
  return value === 'dark' ? 'dark' : 'light';
}

export function isDarkTheme(theme: NewsletterTheme) {
  return theme === 'dark';
}
```

- [ ] **Step 4: Update AppShell**

Replace `frontend/components/layout/app-shell.tsx` with:

```tsx
import React from 'react';
import Link from 'next/link';
import { ReactNode } from 'react';

import type { NewsletterTheme } from '@/lib/theme';

export function AppShell({
  title,
  children,
  contentClassName = 'max-w-6xl',
  theme = 'light',
}: {
  title: string;
  children: ReactNode;
  contentClassName?: string;
  theme?: NewsletterTheme;
}) {
  const dark = theme === 'dark';

  return (
    <div
      data-testid="app-shell"
      className={`min-h-screen ${dark ? 'bg-slate-950' : 'bg-slate-100'}`}
      suppressHydrationWarning
    >
      <header
        data-testid="app-shell-header"
        className={`border-b ${dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'}`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <Link href="/" className={`text-lg font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>
              AeroOne
            </Link>
            <p className={`text-sm ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
              사내 뉴스레터 / 문서 플랫폼
            </p>
          </div>
          <nav className={`flex gap-4 text-sm ${dark ? 'text-slate-300' : 'text-slate-600'}`}>
            <Link href="/">대시보드</Link>
            <Link href="/newsletters">뉴스레터</Link>
            <Link href="/admin/newsletters">관리자</Link>
            <Link href="/login">로그인</Link>
          </nav>
        </div>
      </header>
      <main className={`mx-auto px-6 py-8 ${contentClassName}`}>
        <h1 className={`mb-6 text-2xl font-semibold ${dark ? 'text-slate-100' : 'text-slate-900'}`}>{title}</h1>
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Run the AppShell test and verify GREEN**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx
```

Expected:

- PASS.

---

### Task 2: Thread Theme Through Newsletter Routes And Components

**Files:**
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify: `frontend/components/newsletter/newsletters-workspace.tsx`
- Modify: `frontend/components/newsletter/newsletter-date-calendar.tsx`
- Modify: `frontend/components/newsletter/newsletter-asset-selector.tsx`
- Modify: `frontend/components/newsletter/newsletter-preview-panel.tsx`

- [ ] **Step 1: Update newsletter server routes**

In `frontend/app/newsletters/page.tsx`, add:

```ts
import { resolveNewsletterTheme } from '@/lib/theme';
```

Inside the page function before `return`, add:

```ts
const newsletterTheme = resolveNewsletterTheme();
```

Pass it:

```tsx
<AppShell title="뉴스레터 서비스" contentClassName="max-w-[1600px]" theme={newsletterTheme}>
```

```tsx
<NewsletterDateCalendar entries={calendarEntries} selectedSlug={activeDetail.slug} theme={newsletterTheme} />
```

```tsx
<NewslettersWorkspace
  key={activeDetail.slug}
  calendarPanel={(
    <section data-testid="newsletters-calendar-panel">
      <NewsletterDateCalendar entries={calendarEntries} selectedSlug={activeDetail.slug} theme={newsletterTheme} />
    </section>
  )}
  newsletter={activeDetail}
  initialContentHtml={initialContentHtml}
  theme={newsletterTheme}
/>
```

In `frontend/app/newsletters/[slug]/page.tsx`, add:

```ts
import { resolveNewsletterTheme } from '@/lib/theme';
```

Before `return`, add:

```ts
const newsletterTheme = resolveNewsletterTheme();
```

Pass it:

```tsx
<AppShell title={detail.title} theme={newsletterTheme}>
  <NewslettersWorkspace
    key={detail.slug}
    newsletter={detail}
    initialContentHtml={initialContentHtml}
    theme={newsletterTheme}
  />
</AppShell>
```

- [ ] **Step 2: Update NewslettersWorkspace**

In `frontend/components/newsletter/newsletters-workspace.tsx`, import:

```ts
import type { NewsletterTheme } from '@/lib/theme';
```

Add prop:

```ts
theme = 'light',
```

and type:

```ts
theme?: NewsletterTheme;
```

Pass it:

```tsx
<NewsletterAssetSelector
  availableAssetTypes={availableAssetTypes}
  selectedAsset={selectedAsset}
  onChange={setSelectedAsset}
  theme={theme}
/>
```

```tsx
<NewsletterPreviewPanel title={newsletter.title} selectedAsset={selectedAsset} theme={theme}>
```

- [ ] **Step 3: Update NewsletterDateCalendar**

In `frontend/components/newsletter/newsletter-date-calendar.tsx`, import:

```ts
import type { NewsletterTheme } from '@/lib/theme';
```

Add prop:

```ts
theme = 'light',
```

and type:

```ts
theme?: NewsletterTheme;
```

Add:

```ts
const dark = theme === 'dark';
```

Keep `open` behavior unchanged.

Use conditional classes equivalent to:

```tsx
<section className={`rounded-xl border p-3 shadow-sm ${
  dark ? 'border-slate-800 bg-slate-900/95 text-slate-100' : 'border-slate-200 bg-white text-slate-900'
}`}>
```

The dark branch should match the previous `d735c76` dark visual direction. The light branch should match current `3853840/713a761` light classes.

- [ ] **Step 4: Update NewsletterAssetSelector**

In `frontend/components/newsletter/newsletter-asset-selector.tsx`, import:

```ts
import type { NewsletterTheme } from '@/lib/theme';
```

Add prop:

```ts
theme = 'light',
```

and type:

```ts
theme?: NewsletterTheme;
```

Add:

```ts
const dark = theme === 'dark';
```

Use conditional classes so:

- light root includes `bg-white`
- dark root includes `bg-slate-900/95`
- light inactive cards use `bg-slate-50`
- dark inactive cards use `bg-slate-950`
- active cards stay clearly selected in both modes

- [ ] **Step 5: Update NewsletterPreviewPanel**

In `frontend/components/newsletter/newsletter-preview-panel.tsx`, import:

```ts
import type { NewsletterTheme } from '@/lib/theme';
```

Add prop:

```ts
theme = 'light',
```

and type:

```ts
theme?: NewsletterTheme;
```

Add:

```ts
const dark = theme === 'dark';
```

Use conditional classes so:

- light root includes `bg-white`
- dark root includes `bg-slate-900/95`
- title and badge colors match the theme

---

### Task 3: Add Theme Tests

**Files:**
- Modify: `frontend/tests/components/newsletter-date-calendar.test.tsx`
- Modify: `frontend/tests/components/newsletter-asset-selector.test.tsx`
- Modify: `frontend/tests/components/newsletter-preview-panel.test.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`
- Modify: `frontend/tests/app/newsletter-detail-page.test.tsx`

- [ ] **Step 1: Extend calendar test for dark theme**

Append to `frontend/tests/components/newsletter-date-calendar.test.tsx`:

```tsx
it('can render the calendar panel with dark theme classes', () => {
  const { container } = render(
    <NewsletterDateCalendar
      theme="dark"
      selectedSlug="newsletter-20260326"
      entries={[
        { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
      ]}
    />,
  );

  const panel = container.querySelector('section');

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(screen.getByRole('button', { name: '달력 접기' })).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByTestId('newsletter-calendar-grid')).toBeVisible();
});
```

- [ ] **Step 2: Extend asset selector test for dark theme**

Append to `frontend/tests/components/newsletter-asset-selector.test.tsx`:

```tsx
test('renders report-style format cards with dark theme classes', () => {
  render(
    <NewsletterAssetSelector
      theme="dark"
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="pdf"
      onChange={vi.fn()}
    />,
  );

  const panel = screen.getByTestId('newsletters-format-panel');

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(within(panel).getByRole('button', { name: /PDF/ })).toHaveAttribute('aria-pressed', 'true');
});
```

- [ ] **Step 3: Extend preview panel test for dark theme**

Append to `frontend/tests/components/newsletter-preview-panel.test.tsx`:

```tsx
test('renders the preview panel with dark theme classes', () => {
  render(
    <NewsletterPreviewPanel title="Dark Preview" selectedAsset="pdf" theme="dark">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  const panel = screen.getByTestId('newsletters-preview-panel');

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(within(panel).getByRole('heading', { name: 'Dark Preview' })).toHaveClass('text-slate-100');
});
```

- [ ] **Step 4: Add a route-level dark theme test**

In `frontend/tests/app/newsletters-layout.test.tsx`, add a test that sets the environment variable, imports the page dynamically, and verifies dark shell/panel classes. Use `vi.resetModules()` to force the server module to read the changed env.

```tsx
test('route renders dark theme when NEWSLETTERS_THEME is dark', async () => {
  vi.resetModules();
  process.env.NEWSLETTERS_THEME = 'dark';

  const { default: ThemedNewslettersPage } = await import('@/app/newsletters/page');

  render(await ThemedNewslettersPage({ searchParams: Promise.resolve({}) }));

  expect(screen.getByTestId('app-shell')).toHaveClass('bg-slate-950');
  expect(screen.getByTestId('newsletters-format-panel')).toHaveClass('bg-slate-900/95');
  expect(screen.getByTestId('newsletters-preview-panel')).toHaveClass('bg-slate-900/95');

  delete process.env.NEWSLETTERS_THEME;
});
```

If existing hoisted mocks do not survive `vi.resetModules()`, use `vi.stubEnv('NEWSLETTERS_THEME', 'dark')` in a test that imports the route normally and confirm the route reads env at render time. The expected assertion remains the same.

- [ ] **Step 5: Update detail page test mock for theme prop**

In `frontend/tests/app/newsletter-detail-page.test.tsx`, ensure the `NewslettersWorkspace` mock accepts `theme`:

```tsx
NewslettersWorkspace: ({
  newsletter,
  initialContentHtml,
  theme,
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
  theme?: string;
}) => (
  <div>
    <div data-testid="newsletters-workspace" data-theme={theme}>{newsletter.title}</div>
    <div data-testid="newsletter-detail-html">{initialContentHtml ?? ''}</div>
  </div>
),
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
npm run test -- tests/components/app-shell.test.tsx tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-asset-selector.test.tsx tests/components/newsletter-preview-panel.test.tsx tests/app/newsletters-layout.test.tsx tests/app/newsletter-detail-page.test.tsx
```

Expected:

- PASS.

---

### Task 4: Full Verification And Port Comparison

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

- `npm run test`: all tests pass.
- `npm run typecheck`: exits 0.
- `npm run build`: exits 0.

- [ ] **Step 2: Start backend if needed**

Run:

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:18437/api/v1/newsletters' -UseBasicParsing -TimeoutSec 10
```

If it fails, start backend with the known local venv and `.env`.

- [ ] **Step 3: Start 29501 light and 29503 dark**

Start light:

```powershell
$env:NEWSLETTERS_THEME='light'
npx next start -p 29501 --hostname 127.0.0.1
```

Start dark:

```powershell
$env:NEWSLETTERS_THEME='dark'
npx next start -p 29503 --hostname 127.0.0.1
```

- [ ] **Step 4: Verify both URLs**

Run:

```powershell
function Probe($port, $label) {
  $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/newsletters" -UseBasicParsing -TimeoutSec 10
  $content = $response.Content
  "${label}_STATUS=$($response.StatusCode)"
  "${label}_has-control-grid=$($content.Contains('newsletters-control-grid'))"
  "${label}_has-calendar-grid=$($content.Contains('newsletter-calendar-grid'))"
  "${label}_has-format-heading=$($content.Contains('HTML / Markdown / PDF'))"
  "${label}_has-collapse-label=$($content.Contains('달력 접기'))"
  "${label}_has-dark-panel=$($content.Contains('bg-slate-900/95'))"
  "${label}_has-white-panel=$($content.Contains('bg-white'))"
}
Probe 29501 LIGHT_29501
Probe 29503 DARK_29503
```

Expected:

```text
LIGHT_29501_STATUS=200
LIGHT_29501_has-control-grid=True
LIGHT_29501_has-calendar-grid=True
LIGHT_29501_has-format-heading=True
LIGHT_29501_has-collapse-label=True
LIGHT_29501_has-dark-panel=False
LIGHT_29501_has-white-panel=True
DARK_29503_STATUS=200
DARK_29503_has-control-grid=True
DARK_29503_has-calendar-grid=True
DARK_29503_has-format-heading=True
DARK_29503_has-collapse-label=True
DARK_29503_has-dark-panel=True
```

- [ ] **Step 5: Commit with UTF-8 Korean message**

Use `git commit -F` with a UTF-8 without BOM file.

Commit message:

```text
뉴스레터 화면에 포트별 런타임 테마를 추가한다

NEWSLETTERS_THEME 환경변수로 같은 최신 뉴스레터 화면을 밝은 테마와 다크 테마로 실행할 수 있게 했다.
29501은 기본 밝은 테마로, 29503은 dark 환경값을 주어 다크 테마로 비교할 수 있으며 d735c76 비교 worktree에 의존하지 않는다.

Constraint: 사용자가 29501은 밝게, 29503은 다크모드로 직접 비교하길 원했다
Rejected: d735c76 detached worktree 유지 | 최신 코드와 분리되어 기능 검증과 PR 관리가 불안정하다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: 테마 변경은 NEWSLETTERS_THEME와 NewsletterTheme 타입을 통해 확장할 것
Tested: npm run test; npm run typecheck; npm run build; Probe 29501 light and 29503 dark
Not-tested: 사용자 브라우저에서 최종 시각 승인 여부는 아직 받지 않았다
```

- [ ] **Step 6: Verify commit encoding**

Run:

```powershell
$log = git log --format='%H%n%B%n---END---' -1 HEAD
$bad = $log | Select-String -Pattern '\?{3,}|�|﻿\?'
if ($bad) { $bad | ForEach-Object { $_.Line }; exit 1 }
'OK: latest commit message has no mojibake markers'
```

Expected:

```text
OK: latest commit message has no mojibake markers
```

---

## Self-Review

Spec coverage:
- Latest code can render light and dark: Tasks 1-4.
- `29501=light`, `29503=dark`: Task 4.
- Do not rely on `d735c76`: Architecture and Task 4.
- Preserve structure and behavior: Tasks 2-3 tests.
- Korean commit safety: Task 4 Steps 5-6.

Placeholder scan:
- No `TBD`, `TODO`, or unspecified implementation steps remain.

Type consistency:
- `NewsletterTheme`, `resolveNewsletterTheme`, and optional `theme` props are introduced in Task 1 and used consistently afterward.
