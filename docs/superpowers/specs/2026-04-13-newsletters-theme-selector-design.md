# Newsletters Single-Port Theme Selector Design

Date: 2026-04-13
Status: Approved for planning and implementation

## Summary

The required behavior is a single frontend server on the normal AeroOne frontend port, with Light and Dark selectable inside the page. Running multiple frontend ports for different themes is not the product behavior and should not be part of normal verification.

The newsletters page should therefore use one frontend port:

- `http://localhost:29501/newsletters`

and let the user switch theme through links on that same page:

- `http://localhost:29501/newsletters?theme=light`
- `http://localhost:29501/newsletters?theme=dark`

## Goals

- Use a single frontend port: `29501`.
- Add a visible Light / Dark selector to `/newsletters`.
- Add the same selector to `/newsletters/[slug]`.
- Preserve the current report-style page shell.
- Preserve calendar collapse/expand.
- Preserve `HT / MD / PDF` card selection.
- Make query string theme selection the primary user-facing behavior.
- Keep `NEWSLETTERS_THEME` only as an optional fallback default, not as the normal comparison mechanism.
- Avoid cookies, localStorage, multiple frontend servers, and new dependencies.

## Non-Goals

- Do not run `29503` as the official dark-mode frontend.
- Do not keep a detached `d735c76` worktree for dark-mode use.
- Do not introduce a global site-wide theme system.
- Do not persist theme in cookies or localStorage.
- Do not add client-side hydration-only theme switching.
- Do not change newsletter data fetching.
- Do not redesign unrelated pages.

## Theme Resolution

Theme priority:

1. URL query parameter: `theme=light` or `theme=dark`
2. Environment variable fallback: `NEWSLETTERS_THEME=light|dark`
3. Default: `light`

The query parameter is the primary user-facing control. The environment variable exists only so local or deployment environments can choose a default when no query is present.

Helper contract:

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

## Theme Selector Component

Component:

- `frontend/components/newsletter/newsletter-theme-selector.tsx`

Props:

```ts
{
  theme: NewsletterTheme;
  slug?: string;
  className?: string;
}
```

Behavior:

- Renders a small segmented selector with `Light` and `Dark`.
- Uses normal links, not client-only state.
- Links to `/newsletters?theme=light` and `/newsletters?theme=dark`.
- If `slug` is present, links preserve it:
  - `/newsletters?slug=<slug>&theme=light`
  - `/newsletters?slug=<slug>&theme=dark`
- The selected theme has `aria-current="true"`.
- The selector exposes `data-testid="newsletter-theme-selector"`.

## Page Integration

### `/newsletters`

`SearchParams` includes:

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

Render `NewsletterThemeSelector` above `NewslettersWorkspace`.

When a newsletter detail is active:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={activeDetail.slug} />
```

When no detail is active:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} />
```

### `/newsletters/[slug]`

Add `searchParams` for theme:

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

Render selector above `NewslettersWorkspace`:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={detail.slug} />
```

## Runtime Behavior

Normal run:

```powershell
start.bat
```

Expected frontend:

```text
http://localhost:29501/newsletters
```

Theme URLs:

```text
http://localhost:29501/newsletters?theme=light
http://localhost:29501/newsletters?theme=dark
```

Slug URLs:

```text
http://localhost:29501/newsletters?slug=<slug>&theme=light
http://localhost:29501/newsletters?slug=<slug>&theme=dark
```

## Testing

Add or update tests for:

- theme helper query precedence
- selector link generation without slug
- selector link generation with slug
- selector selected-state semantics
- `/newsletters?theme=dark` rendering dark shell and dark newsletter panels
- `/newsletters?theme=light` overriding `NEWSLETTERS_THEME=dark`
- `/newsletters/[slug]?theme=dark` passing dark theme to shell and workspace

Runtime verification must use one frontend port:

- `/newsletters`
- `/newsletters?theme=dark`
- `/newsletters?theme=light`

## Acceptance Criteria

- `start.bat` runs one frontend on port `29501`.
- `/newsletters` visibly shows a Light / Dark selector.
- `/newsletters/[slug]` visibly shows a Light / Dark selector.
- `/newsletters?theme=dark` changes the same `29501` frontend to dark.
- `/newsletters?theme=light` changes the same `29501` frontend to light.
- `theme=light` overrides `NEWSLETTERS_THEME=dark`.
- No official verification step requires `29503`.
- All tests, typecheck, and build pass.
