# AppShell Global Theme Design

Date: 2026-04-16
Status: Approved for planning and implementation

## Summary

Theme handling is currently centered on `/newsletters`. The user expectation is broader: the theme toggle should be visible and stable across every screen that uses `AppShell`, including the home page, login page, and admin pages. The selected theme should also persist when moving between pages.

This design promotes theme handling to an `AppShell`-level convention.

## Goals

- Apply theme to every page that uses `AppShell`.
- Show the theme toggle next to `로그인` on every `AppShell` page.
- Keep one frontend port: `29501`.
- Persist selected theme through `aeroone_theme` cookie.
- Preserve query override behavior.
- Preserve newsletter-specific behavior including calendar theme links.
- Avoid localStorage, client-only theme state, and new dependencies.

## Non-Goals

- Do not build a user profile preference system.
- Do not redesign admin features.
- Do not remove login or admin functionality.
- Do not add multiple frontend ports.

## Theme Resolution

Use the existing priority:

1. query `theme=light|dark`
2. cookie `aeroone_theme=light|dark`
3. `NEWSLETTERS_THEME`
4. `light`

Add a server helper:

```ts
export async function getAppTheme(themeParam?: string): Promise<NewsletterTheme>
```

It reads cookies via `next/headers` and calls `resolveNewsletterThemeFromSearchParam`.

## AppShell Behavior

`AppShell` should render the theme toggle by default.

Recommended props:

```ts
theme?: NewsletterTheme;
showThemeSelector?: boolean; // default true
themePath?: string;
```

Default behavior:

- `showThemeSelector = true`
- `themePath = '/'`

Pages may opt out only if there is a concrete reason. No current page needs to opt out.

## Page Integration

Update every page that uses `AppShell`.

Required pages:

- `frontend/app/page.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/newsletters/page.tsx`
- `frontend/app/newsletters/[slug]/page.tsx`
- `frontend/app/admin/newsletters/page.tsx`
- `frontend/app/admin/imports/page.tsx`
- `frontend/app/admin/newsletters/new/page.tsx`
- `frontend/app/admin/newsletters/[id]/edit/page.tsx`

Each page should:

- resolve theme with `getAppTheme(searchParams?.theme)`
- pass `theme`
- pass an accurate `themePath`

Examples:

```tsx
<AppShell title="서비스 대시보드" theme={theme} themePath="/">
```

```tsx
<AppShell title="관리자 로그인" theme={theme} themePath="/login">
```

```tsx
<AppShell title="뉴스레터 서비스" theme={theme} themePath="/newsletters?slug=...">
```

## Admin And Login

Admin and login remain necessary because admin routes can mutate or sync newsletter data.

The current development credentials come from `backend/.env`:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

This design does not change authentication.

## Tests

Add/update tests for:

- `getAppTheme` reads cookie fallback.
- `AppShell` renders selector by default.
- home page passes theme and path.
- login page passes theme and path.
- admin pages pass theme and path while keeping auth guard behavior.
- newsletters page still supports query override and calendar link preservation.

## Acceptance Criteria

- `/` can render dark theme from cookie.
- `/login` can render dark theme from cookie.
- `/admin/newsletters` can render dark theme from cookie after auth.
- `/newsletters` can render dark theme from cookie and query.
- Theme toggle is visible next to `로그인` on AppShell pages.
- Calendar date click preserves the selected theme.
- All tests, typecheck, build, and runtime checks pass.
