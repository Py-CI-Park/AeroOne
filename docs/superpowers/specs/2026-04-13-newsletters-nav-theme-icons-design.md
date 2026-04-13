# Newsletters Nav Theme Icons Design

Date: 2026-04-13
Status: Approved for planning

## Summary

The newsletters theme selector should not appear as a large content card above the newsletter workspace. Theme selection is a view preference, so it belongs in the application navigation next to `로그인`.

This design replaces the large `Light / Dark` selector card with two very small nav icons:

- sun icon for light theme
- moon icon for dark theme

The app still uses a single frontend port (`29501`) and switches theme through query strings on the same page.

## Goals

- Remove the large body-level theme selector card from `/newsletters`.
- Remove the large body-level theme selector card from `/newsletters/[slug]`.
- Add a very small sun/moon selector beside the `로그인` nav link.
- Keep single-port theme switching:
  - `/newsletters?theme=light`
  - `/newsletters?theme=dark`
- Preserve `slug` when switching theme:
  - `/newsletters?slug=<slug>&theme=light`
  - `/newsletters?slug=<slug>&theme=dark`
- Preserve accessibility with `aria-label`.
- Preserve current report-style newsletter layout.
- Preserve calendar collapse/expand.
- Avoid new dependencies.

## Non-Goals

- Do not introduce a multi-port theme workflow.
- Do not add a full global theme settings menu.
- Do not persist theme in cookies or localStorage.
- Do not add client-only theme state.
- Do not change newsletter data fetching.
- Do not redesign unrelated pages.

## Component Changes

### AppShell

`AppShell` should own the nav placement.

Add optional props:

```ts
theme?: NewsletterTheme;
showThemeSelector?: boolean;
themeSlug?: string;
```

Behavior:

- `showThemeSelector` defaults to `false`.
- When `showThemeSelector` is true, render the small theme selector immediately after the `로그인` link.
- Other pages continue to render no theme selector unless they opt in.

### NewsletterThemeSelector

Keep the component, but change it from a card selector to a compact nav selector.

Props remain:

```ts
{
  theme: NewsletterTheme;
  slug?: string;
  className?: string;
}
```

New rendering:

- wrapper: inline `span` or small `div`
- `data-testid="newsletter-theme-selector"`
- light link:
  - visible icon: `☀`
  - `aria-label="라이트 테마"`
  - href: `/newsletters?theme=light` or `/newsletters?slug=<slug>&theme=light`
- dark link:
  - visible icon: `☾`
  - `aria-label="다크 테마"`
  - href: `/newsletters?theme=dark` or `/newsletters?slug=<slug>&theme=dark`
- selected theme:
  - `aria-current="true"`
  - subtle selected styling

The visible labels `Light`, `Dark`, and `화면 테마 선택` should not appear in the page body.

## Route Changes

### `/newsletters`

Remove direct body rendering:

```tsx
<NewsletterThemeSelector ... />
```

Pass theme selector configuration into `AppShell`:

```tsx
<AppShell
  title="뉴스레터 서비스"
  contentClassName="max-w-[1600px]"
  theme={newsletterTheme}
  showThemeSelector
  themeSlug={activeDetail?.slug}
>
```

### `/newsletters/[slug]`

Remove direct body rendering:

```tsx
<NewsletterThemeSelector ... />
```

Pass theme selector configuration into `AppShell`:

```tsx
<AppShell
  title={detail.title}
  theme={newsletterTheme}
  showThemeSelector
  themeSlug={detail.slug}
>
```

## Theme Resolution

Keep the current query-string resolution:

1. `theme=light|dark`
2. `NEWSLETTERS_THEME`
3. `light`

The selector remains link-based so a single frontend port can render both themes without hydration-only client state.

## Tests

Update tests so they verify:

- `AppShell` renders no selector by default.
- `AppShell` renders the compact selector after `로그인` when `showThemeSelector` is true.
- `NewsletterThemeSelector` renders icon links with aria labels.
- `NewsletterThemeSelector` preserves slug in hrefs.
- `/newsletters` does not render a body-level selector card.
- `/newsletters` does render the nav selector.
- `/newsletters?theme=dark` still renders dark shell and dark panels.
- `/newsletters?theme=light` still overrides `NEWSLETTERS_THEME=dark`.
- `/newsletters/[slug]?theme=dark` passes theme and slug to `AppShell`.

## Runtime Verification

Use one frontend port only:

```text
http://127.0.0.1:29501/newsletters
http://127.0.0.1:29501/newsletters?theme=dark
http://127.0.0.1:29501/newsletters?theme=light
```

Expected:

- `29501/newsletters` shows the small sun/moon selector next to `로그인`.
- `29501/newsletters?theme=dark` switches the same page to dark mode.
- `29501/newsletters?theme=light` switches the same page to light mode.
- No `29503` frontend is required.

## Acceptance Criteria

- The theme selector appears next to `로그인`, not in the newsletter body.
- The selector is small and icon-based.
- The selector links are accessible through `aria-label`.
- The selector preserves the active newsletter slug.
- Theme switching works on `29501` only.
- Existing newsletter layout and preview behavior remain intact.
- Tests, typecheck, and build pass.
