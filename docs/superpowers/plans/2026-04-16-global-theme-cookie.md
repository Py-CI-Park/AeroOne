# Global Theme Cookie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the newsletter light/dark theme across navigation using a cookie while keeping the single nav icon selector.

**Architecture:** Resolve theme from query, then cookie, then environment, then light. Add a `/theme` route that sets the cookie and redirects back to a safe local path. Preserve the current theme in calendar links.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library

---

## File Structure

- `frontend/lib/theme.ts`
  - Extend resolver to accept cookie value.
  - Add cookie constants.

- `frontend/app/theme/route.ts`
  - New route handler that sets `aeroone_theme` and redirects.

- `frontend/components/newsletter/newsletter-theme-selector.tsx`
  - Link to `/theme?theme=<next>&next=<currentPath>`.

- `frontend/components/layout/app-shell.tsx`
  - Accept `themePath?: string` and pass it to selector.

- `frontend/app/newsletters/page.tsx`
  - Read cookies.
  - Resolve query/cookie/env theme.
  - Pass current path to AppShell.

- `frontend/app/newsletters/[slug]/page.tsx`
  - Read cookies.
  - Resolve query/cookie/env theme.
  - Pass current path to AppShell.

- `frontend/components/newsletter/newsletter-date-calendar.tsx`
  - Add `theme` to date links.

- Tests:
  - `frontend/tests/lib/theme.test.ts`
  - `frontend/tests/app/theme-route.test.ts`
  - `frontend/tests/components/newsletter-theme-selector.test.tsx`
  - `frontend/tests/components/newsletter-date-calendar.test.tsx`
  - `frontend/tests/app/newsletters-layout.test.tsx`
  - `frontend/tests/app/newsletter-detail-page.test.tsx`

---

### Task 1: Extend Theme Resolution

**Files:**
- Modify: `frontend/lib/theme.ts`
- Modify: `frontend/tests/lib/theme.test.ts`

- [ ] **Step 1: Add failing tests**

Add to `frontend/tests/lib/theme.test.ts`:

```ts
test('uses cookie theme before environment theme when query is absent', () => {
  expect(resolveNewsletterThemeFromSearchParam(undefined, 'light', 'dark')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam(undefined, 'dark', 'light')).toBe('light');
});
```

- [ ] **Step 2: Run helper tests and verify RED**

Run:

```powershell
npm run test -- tests/lib/theme.test.ts
```

Expected:

- FAIL because helper does not accept cookie value yet.

- [ ] **Step 3: Implement resolver**

Update `frontend/lib/theme.ts`:

```ts
export type NewsletterTheme = 'light' | 'dark';

export const NEWSLETTER_THEME_COOKIE = 'aeroone_theme';

export function resolveNewsletterTheme(value = process.env.NEWSLETTERS_THEME): NewsletterTheme {
  return value === 'dark' ? 'dark' : 'light';
}

export function resolveNewsletterThemeFromSearchParam(
  themeParam: string | undefined,
  envValue = process.env.NEWSLETTERS_THEME,
  cookieValue?: string,
): NewsletterTheme {
  if (themeParam === 'dark' || themeParam === 'light') {
    return themeParam;
  }

  if (cookieValue === 'dark' || cookieValue === 'light') {
    return cookieValue;
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

### Task 2: Add Theme Cookie Route

**Files:**
- Create: `frontend/app/theme/route.ts`
- Create: `frontend/tests/app/theme-route.test.ts`

- [ ] **Step 1: Write route tests**

Create `frontend/tests/app/theme-route.test.ts`:

```ts
import { GET } from '@/app/theme/route';
import { NEWSLETTER_THEME_COOKIE } from '@/lib/theme';

test('sets theme cookie and redirects to a safe local next path', async () => {
  const request = new Request('http://localhost/theme?theme=dark&next=/newsletters?slug=abc');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('/newsletters?slug=abc');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=dark`);
  expect(response.headers.get('set-cookie')).toContain('Path=/');
});

test('falls back to newsletters for invalid theme and unsafe redirect', async () => {
  const request = new Request('http://localhost/theme?theme=invalid&next=https://example.com');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('/newsletters');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=light`);
});
```

- [ ] **Step 2: Run route tests and verify RED**

Run:

```powershell
npm run test -- tests/app/theme-route.test.ts
```

Expected:

- FAIL because `frontend/app/theme/route.ts` does not exist.

- [ ] **Step 3: Implement route**

Create `frontend/app/theme/route.ts`:

```ts
import { NextResponse } from 'next/server';

import { NEWSLETTER_THEME_COOKIE, resolveNewsletterTheme } from '@/lib/theme';

function safeNextPath(raw: string | null) {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) {
    return '/newsletters';
  }

  return raw;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const theme = resolveNewsletterTheme(url.searchParams.get('theme') ?? undefined);
  const next = safeNextPath(url.searchParams.get('next'));
  const response = NextResponse.redirect(new URL(next, url.origin));

  response.cookies.set(NEWSLETTER_THEME_COOKIE, theme, {
    path: '/',
    sameSite: 'lax',
    maxAge: 31536000,
  });

  return response;
}
```

- [ ] **Step 4: Run route tests and verify GREEN**

Run:

```powershell
npm run test -- tests/app/theme-route.test.ts
```

Expected:

- PASS.

---

### Task 3: Point Selector To Cookie Route

**Files:**
- Modify: `frontend/components/newsletter/newsletter-theme-selector.tsx`
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/tests/components/newsletter-theme-selector.test.tsx`
- Modify: `frontend/tests/components/app-shell.test.tsx`

- [ ] **Step 1: Update selector tests**

Expected href examples:

```tsx
expect(toggle).toHaveAttribute('href', '/theme?theme=dark&next=%2Fnewsletters');
expect(toggle).toHaveAttribute('href', '/theme?theme=light&next=%2Fnewsletters%3Fslug%3Dnewsletter-20260330');
```

- [ ] **Step 2: Implement selector route link**

Update selector to accept:

```ts
currentPath?: string;
```

Build href:

```ts
function buildThemeHref(theme: NewsletterTheme, currentPath = '/newsletters') {
  const params = new URLSearchParams();
  params.set('theme', theme);
  params.set('next', currentPath);
  return `/theme?${params.toString()}`;
}
```

- [ ] **Step 3: Update AppShell prop threading**

Add:

```ts
themePath?: string;
```

Pass:

```tsx
<NewsletterThemeSelector theme={theme} currentPath={themePath} />
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
npm run test -- tests/components/newsletter-theme-selector.test.tsx tests/components/app-shell.test.tsx
```

Expected:

- PASS.

---

### Task 4: Preserve Theme Through Routes And Calendar

**Files:**
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify: `frontend/components/newsletter/newsletter-date-calendar.tsx`
- Modify: `frontend/tests/components/newsletter-date-calendar.test.tsx`
- Modify: `frontend/tests/app/newsletters-layout.test.tsx`
- Modify: `frontend/tests/app/newsletter-detail-page.test.tsx`

- [ ] **Step 1: Read cookie in routes**

Use:

```ts
import { cookies } from 'next/headers';
import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';
```

Then:

```ts
const cookieStore = await cookies();
const cookieTheme = cookieStore.get(NEWSLETTER_THEME_COOKIE)?.value;
const newsletterTheme = resolveNewsletterThemeFromSearchParam(params.theme, process.env.NEWSLETTERS_THEME, cookieTheme);
```

- [ ] **Step 2: Build current theme path**

For `/newsletters`:

```ts
const themePath = activeDetail?.slug ? `/newsletters?slug=${activeDetail.slug}` : '/newsletters';
```

For `[slug]`:

```ts
const themePath = `/newsletters?slug=${detail.slug}`;
```

Pass `themePath` to `AppShell`.

- [ ] **Step 3: Preserve theme in calendar links**

Update date links:

```tsx
href={`/newsletters?slug=${cell.entry.slug}&theme=${theme}`}
```

- [ ] **Step 4: Update tests**

Calendar test:

```tsx
expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
  'href',
  '/newsletters?slug=newsletter-20260326&theme=light',
);
```

Dark calendar test should expect:

```tsx
'/newsletters?slug=newsletter-20260326&theme=dark'
```

Route layout test should expect `/theme?...next=...` links and dark query override.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
npm run test -- tests/app/theme-route.test.ts tests/components/newsletter-theme-selector.test.tsx tests/components/app-shell.test.tsx tests/components/newsletter-date-calendar.test.tsx tests/app/newsletters-layout.test.tsx tests/app/newsletter-detail-page.test.tsx tests/lib/theme.test.ts
```

Expected:

- PASS.

---

### Task 5: Full Verification And Runtime Check

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

- [ ] **Step 2: Runtime check**

Use one frontend port:

```text
http://127.0.0.1:29501/newsletters
http://127.0.0.1:29501/newsletters?theme=dark
```

Verify:

- selector visible
- default has moon icon
- dark query has sun icon
- calendar date links include `theme=dark` in dark mode
- clicking theme route sets cookie and redirects back

- [ ] **Step 3: Commit**

Use UTF-8 `git commit -F`:

```text
뉴스레터 테마를 쿠키로 유지하고 달력 링크에 반영한다

테마 선택을 query string에만 의존하지 않고 aeroone_theme 쿠키로 저장해 화면 이동과 새로고침 후에도 유지되도록 했다.
달력 날짜 링크도 현재 theme를 포함하도록 바꿔 다크 모드에서 날짜를 선택해도 라이트 모드로 돌아가지 않게 했다.

Constraint: 사용자가 첫 화면과 다른 화면 이동에서도 테마 선택이 유지되길 원했다
Rejected: query string만 유지 | 달력과 nav 링크마다 theme 누락이 반복될 수 있다
Confidence: 높음
Scope-risk: 보통
Reversibility: 깔끔함
Directive: 테마 우선순위는 query -> cookie -> env -> light 순서로 유지할 것
Tested: npm run test; npm run typecheck; npm run build; runtime theme route and calendar link checks
Not-tested: 사용자 최종 시각 승인 여부는 아직 받지 않았다
```

---

## Self-Review

Spec coverage:
- Cookie persistence: Tasks 1-4.
- Calendar theme preservation: Task 4.
- Single icon remains: Task 3.
- Full verification: Task 5.

Placeholder scan:
- No placeholders remain.
