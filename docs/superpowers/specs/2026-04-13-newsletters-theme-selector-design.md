# Newsletters Theme Selector Design

Date: 2026-04-13
Status: Approved for planning and implementation

## Summary

The newsletters page can now render light or dark through `NEWSLETTERS_THEME`, which is useful for port-based comparison. The missing user-facing piece is a visible selector that lets users switch the page theme from the `/newsletters` UI itself.

This design adds a query-string based selector:

- `/newsletters?theme=light`
- `/newsletters?theme=dark`

The selector works with the existing runtime theme layer and does not replace it. Environment variables remain the default source for port-based launches, while the query string becomes the explicit per-page override.

## Goals

- Add a visible Light / Dark selector to `/newsletters`.
- Add the same selector to `/newsletters/[slug]`.
- Preserve the current report-style page shell.
- Preserve calendar collapse/expand.
- Preserve `HT / MD / PDF` card selection.
- Preserve `NEWSLETTERS_THEME` for port-based defaults.
- Make query string theme override the environment variable.
- Avoid cookies, localStorage, and new dependencies.

## Non-Goals

- Do not add a global site-wide theme system.
- Do not persist theme in cookies or localStorage.
- Do not add client-side hydration-only theme switching.
- Do not change newsletter data fetching.
- Do not redesign unrelated pages.

## Theme Resolution

Theme priority:

1. URL query parameter: `theme=light` or `theme=dark`
2. Environment variable: `NEWSLETTERS_THEME=light|dark`
3. Default: `light`

Recommended helper:

```ts
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

Create:

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
- Uses normal links, not client state.
- Links to `/newsletters?theme=light` and `/newsletters?theme=dark`.
- If `slug` is present, links include both values:
  - `/newsletters?slug=<slug>&theme=light`
  - `/newsletters?slug=<slug>&theme=dark`
- The selected theme has `aria-current="true"`.
- The selector itself exposes `data-testid="newsletter-theme-selector"`.

## Page Integration

### `/newsletters`

`SearchParams` should include:

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

When a detail is active:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} slug={activeDetail.slug} />
```

When no detail exists:

```tsx
<NewsletterThemeSelector theme={newsletterTheme} />
```

### `/newsletters/[slug]`

`params` remains the slug source. Add `searchParams` for theme:

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

## Runtime Examples

Port defaults still work:

```powershell
$env:NEWSLETTERS_THEME='light'
npx next start -p 29501 --hostname 127.0.0.1
```

```powershell
$env:NEWSLETTERS_THEME='dark'
npx next start -p 29503 --hostname 127.0.0.1
```

Query override also works:

```text
http://127.0.0.1:29501/newsletters?theme=dark
http://127.0.0.1:29503/newsletters?theme=light
```

## Testing

Add or update tests for:

- theme helper query precedence
- selector link generation without slug
- selector link generation with slug
- selector selected-state semantics
- `/newsletters?theme=dark` rendering dark shell and dark newsletter panels
- `/newsletters?theme=light` overriding `NEWSLETTERS_THEME=dark`
- `/newsletters/[slug]?theme=dark` passes dark theme to shell and workspace

## Acceptance Criteria

- `/newsletters` visibly shows a Light / Dark selector.
- `/newsletters/[slug]` visibly shows a Light / Dark selector.
- `theme=dark` changes the page to dark.
- `theme=light` changes the page to light even when `NEWSLETTERS_THEME=dark`.
- Existing `NEWSLETTERS_THEME` port-based behavior still works when no query theme is present.
- All tests, typecheck, and build pass.
- `29501` can show light by default and dark through query override.
- `29503` can show dark by default and light through query override.
