# Newsletters Runtime Theme Design

Date: 2026-04-12
Status: Approved for planning and implementation

## Summary

The `/newsletters` page now has the desired report-style structure: a top control grid with the calendar and format selector, and a lower preview panel. The remaining requirement is to run the same latest branch in two visual modes:

- `29501`: light theme
- `29503`: dark theme

This must not use `d735c76` as a long-lived comparison server. `d735c76` is useful as a reference because it contains the control-grid layout and dark visual direction, but it is not a complete runtime dark-mode implementation. The correct design is to add a small theme layer to the current code so the same build can render either light or dark based on runtime configuration.

## Goals

- Keep the latest page-shell structure and behavior.
- Keep `newsletters-control-grid`.
- Keep calendar collapse/expand.
- Keep `HT / MD / PDF` card-style format selection.
- Keep the lower preview panel.
- Let `/newsletters` and `/newsletters/[slug]` render in either `light` or `dark`.
- Let separate processes on separate ports use different themes.
- Default to `light`.
- Preserve Korean text and avoid mojibake in new commits.

## Non-Goals

- Do not revert `d735c76`.
- Do not keep a permanent detached `d735c76` server as the dark-mode implementation.
- Do not add user-facing theme switching controls yet.
- Do not add new dependencies.
- Do not redesign unrelated app pages.

## Theme Selection

Use the `NEWSLETTERS_THEME` environment variable.

Allowed values:

- `dark`
- `light`

Default:

- `light`

Implementation rule:

```ts
const newsletterTheme = process.env.NEWSLETTERS_THEME === 'dark' ? 'dark' : 'light';
```

This is intentionally server-side. It allows two separate Next processes to render different themes:

```powershell
$env:NEWSLETTERS_THEME='light'
npx next start -p 29501 --hostname 127.0.0.1
```

```powershell
$env:NEWSLETTERS_THEME='dark'
npx next start -p 29503 --hostname 127.0.0.1
```

## Component Design

### Shared Type

Add a small shared type:

```ts
export type NewsletterTheme = 'light' | 'dark';
```

Preferred location:

- `frontend/lib/theme.ts`

### AppShell

Extend `AppShell`:

```ts
theme?: NewsletterTheme;
```

Behavior:

- `light`: keep current light shell.
- `dark`: use dark page background, dark header, light text, and dark navigation colors.

The default must remain `light` so existing pages do not change.

### NewslettersPage

`frontend/app/newsletters/page.tsx` should:

- resolve `newsletterTheme`
- pass it to `AppShell`
- pass it to `NewsletterDateCalendar`
- pass it to `NewslettersWorkspace`

### NewsletterDetailPage

`frontend/app/newsletters/[slug]/page.tsx` should:

- resolve the same `newsletterTheme`
- pass it to `AppShell`
- pass it to `NewslettersWorkspace`

### NewslettersWorkspace

`NewslettersWorkspace` should accept:

```ts
theme?: NewsletterTheme;
```

and pass it to:

- `NewsletterAssetSelector`
- `NewsletterPreviewPanel`

### NewsletterDateCalendar

`NewsletterDateCalendar` should accept:

```ts
theme?: NewsletterTheme;
```

It must preserve:

- month navigation
- selected date
- `달력 접기`
- `달력 펼치기`
- `newsletter-calendar-grid`

Only classes should vary by theme.

### NewsletterAssetSelector

`NewsletterAssetSelector` should accept:

```ts
theme?: NewsletterTheme;
```

It must preserve:

- `HT / MD / PDF` cards
- `aria-pressed`
- `onChange`
- `newsletters-format-panel`

Only classes should vary by theme.

### NewsletterPreviewPanel

`NewsletterPreviewPanel` should accept:

```ts
theme?: NewsletterTheme;
```

It must preserve:

- title
- selected asset badge
- children rendering
- `newsletters-preview-panel`

Only classes should vary by theme.

## Runtime Verification

Run the latest branch in two processes:

- `29501`: light
- `29503`: dark

Expected checks:

For `29501`:

- `/newsletters` returns `200`
- contains `newsletters-control-grid`
- contains `newsletter-calendar-grid`
- contains `HTML / Markdown / PDF`
- contains `달력 접기`
- does not contain `bg-slate-900/95`
- contains `bg-white`

For `29503`:

- `/newsletters` returns `200`
- contains `newsletters-control-grid`
- contains `newsletter-calendar-grid`
- contains `HTML / Markdown / PDF`
- contains `달력 접기`
- contains `bg-slate-900/95`
- contains dark shell classes from `AppShell`

## Test Strategy

- Add light and dark tests for `AppShell`.
- Extend calendar tests so both themes keep collapse/expand behavior.
- Extend asset selector tests so dark mode keeps card semantics.
- Extend preview panel tests so dark mode uses dark root panel classes.
- Add route-level test for `NEWSLETTERS_THEME=dark`.
- Keep existing tests passing.

## Risks

- Next.js environment variables can behave differently between build-time and runtime depending on where they are read. This design reads `process.env.NEWSLETTERS_THEME` in server components, so separate server processes should be able to render different themes.
- If production `next start` does not reflect runtime changes as expected, the fallback is a query-param based theme for local comparison only. That fallback is not part of the initial implementation.
