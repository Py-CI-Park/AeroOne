# Global Theme Cookie Design

Date: 2026-04-16
Status: Approved for planning and implementation

## Summary

The current theme selector is visible and compact, but theme state is still primarily URL-query driven. This causes two issues:

- clicking a calendar date can drop `theme=dark` and return the page to light mode
- navigating across screens can lose the selected theme because query strings are not global state

This design keeps the single small nav icon but stores the selected theme in a cookie so the choice persists across navigation and reloads.

## Goals

- Keep one frontend port: `29501`.
- Keep one small nav icon next to `로그인`.
- Persist selected theme across page navigation.
- Preserve theme when clicking calendar dates.
- Keep query string support for direct links and testing.
- Avoid localStorage and hydration-only theme switching.
- Avoid new dependencies.

## Non-Goals

- Do not reintroduce two theme icons.
- Do not reintroduce a large body selector card.
- Do not run a second frontend port for dark mode.
- Do not build a full user preferences system.

## Theme Resolution

Theme priority:

1. URL query parameter: `theme=light|dark`
2. Cookie: `aeroone_theme=light|dark`
3. Environment variable fallback: `NEWSLETTERS_THEME=light|dark`
4. Default: `light`

The query parameter remains useful for direct links and tests, but the cookie is the normal persistence mechanism.

## Cookie

Cookie name:

```text
aeroone_theme
```

Allowed values:

```text
light
dark
```

Suggested cookie properties:

- `path=/`
- `sameSite=lax`
- `maxAge=31536000`

## Theme Route

Add:

```text
frontend/app/theme/route.ts
```

Behavior:

- accepts `theme=light|dark`
- accepts `next=<path>`
- sets `aeroone_theme`
- redirects to `next`
- rejects unsafe external redirects by falling back to `/newsletters`

Example:

```text
/theme?theme=dark&next=/newsletters?slug=newsletter-20260330
```

## Selector Behavior

`NewsletterThemeSelector` remains a single icon.

Current light:

- icon: `☾`
- label: `다크 테마로 전환`
- href: `/theme?theme=dark&next=<currentPath>`

Current dark:

- icon: `☀`
- label: `라이트 테마로 전환`
- href: `/theme?theme=light&next=<currentPath>`

The selector needs the current path so it can return the user to the same location after setting the cookie.

## Calendar Links

`NewsletterDateCalendar` should preserve the current theme in date links:

```text
/newsletters?slug=<slug>&theme=<currentTheme>
```

Cookie persistence should already keep the theme, but adding the query parameter makes the link behavior explicit and protects direct server-rendered transitions.

## Page Integration

`/newsletters` and `/newsletters/[slug]` should resolve theme from:

- query
- cookie
- environment
- default

They should pass the current path to `AppShell` so the nav selector can build the correct `next` URL.

## Tests

Required tests:

- theme helper resolves query before cookie
- theme helper resolves cookie before environment
- theme route sets cookie and redirects safely
- selector builds `/theme` link with `next`
- calendar links include the current theme
- `/newsletters?theme=dark` renders dark and selector points back to current path
- `/newsletters/[slug]?theme=dark` renders dark and selector includes slug in next path

## Acceptance Criteria

- Theme selector remains a single icon next to `로그인`.
- Selecting dark or light persists through navigation.
- Calendar date clicks keep the selected theme.
- `/newsletters?theme=dark` renders dark.
- `/newsletters` without query uses the cookie value when present.
- All tests, typecheck, build, and runtime checks pass.
