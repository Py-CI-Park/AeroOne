# Home Navigation And Calendar Cleanup Design

Date: 2026-04-19
Status: Approved for planning

## Summary

This cleanup addresses four UI issues found after the Newsletter page and global theme work:

- the top navigation still exposes a `Newsletter` text link next to `대시보드`
- the home Newsletter card still shows the description text `Open the latest issue...`
- the Newsletter calendar starts expanded instead of collapsed
- recently touched UI files still contain mojibake text that should be normalized where edited

The work should stay small and should not change backend APIs, admin authentication, or the Newsletter preview data model.

## Goals

- Remove the `Newsletter` text link from the top navigation.
- Keep the dashboard/home link and the theme toggle in the header.
- Remove the home Newsletter card description text.
- Let `ServiceCard` render cleanly without a description.
- Start `NewsletterDateCalendar` collapsed by default.
- Keep the existing calendar expand/collapse button.
- Normalize Korean labels in edited files only.
- Preserve current theme behavior and cookie persistence.

## Non-Goals

- Do not remove the `/newsletters` route.
- Do not remove the home card link to `/newsletters`.
- Do not remove admin authentication.
- Do not change Newsletter data fetching.
- Do not change preview previous/next navigation.
- Do not add new dependencies.

## Detailed Design

### Header Navigation

Current header navigation should change from:

```text
대시보드  Newsletter  [theme toggle]
```

to:

```text
대시보드  [theme toggle]
```

The `Newsletter` route remains accessible through:

- home service card
- direct URL `/newsletters`

### Home Newsletter Card

The home card should keep:

- title: `Newsletter`
- badge: `활성 서비스`
- href: `/newsletters`

The card should remove:

- description text: `Open the latest issue and browse previous issues by date.`

`ServiceCard` should support an optional `description`.

If no description is passed:

- do not render the `<p>` description element
- keep the visual spacing clean

### Calendar Default State

`NewsletterDateCalendar` should initialize as collapsed:

```ts
const [open, setOpen] = useState(false);
```

Default visible button:

```text
달력 펼치기
```

When clicked:

- calendar grid becomes visible
- button label becomes `달력 접기`

The theme and date link behavior remain unchanged.

### Mojibake Cleanup

Only normalize labels in files touched by this cleanup:

- `frontend/components/layout/app-shell.tsx`
- `frontend/app/page.tsx`
- `frontend/components/dashboard/service-card.tsx`
- `frontend/components/newsletter/newsletter-date-calendar.tsx`
- matching tests

Do not broaden the cleanup to unrelated files.

## Tests

Update tests to verify:

- AppShell no longer renders a `Newsletter` nav link.
- AppShell still renders the dashboard link and theme toggle.
- Home page card still links to `/newsletters`.
- Home page card no longer renders the removed description.
- `ServiceCard` handles missing `description`.
- Calendar starts collapsed.
- Calendar expand button reveals the grid.
- Calendar links still preserve `theme`.

## Acceptance Criteria

- Header shows `대시보드` and theme toggle only.
- Home card title is `Newsletter`.
- Home card has no description paragraph.
- Clicking home card still navigates to `/newsletters`.
- Newsletter calendar is collapsed on first render.
- Clicking `달력 펼치기` opens the calendar.
- Theme state is not regressed.
- Tests, typecheck, build, and runtime checks pass.
