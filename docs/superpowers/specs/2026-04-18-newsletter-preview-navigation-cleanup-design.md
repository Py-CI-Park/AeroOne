# Newsletter Preview Navigation Cleanup Design

Date: 2026-04-18
Status: Approved for planning

## Summary

This branch refines the public Newsletter experience after the page-shell redesign and global theme work.

The requested changes are:

- rename user-facing "newsletter service" labels to `Newsletter`
- show the currently selected issue date in the preview header
- add previous/next issue date navigation
- keep the current theme when using calendar links or date navigation
- review whether admin login is still necessary

Admin login should remain because admin screens can mutate, import, sync, and edit Newsletter data.

## Goals

- Use `Newsletter` as the user-facing product label in public navigation and public page titles.
- Remove the word "service" from the public Newsletter entry point.
- Show the selected issue date in the preview panel.
- Add previous/next issue-date navigation near the preview panel header.
- Preserve the selected theme in calendar links and previous/next links.
- Keep the single-icon theme toggle behavior.
- Keep admin login for admin-only mutation and sync features.

## Non-Goals

- Do not remove admin login.
- Do not expose admin mutation routes publicly.
- Do not redesign the full navigation system.
- Do not add a new date picker.
- Do not change backend Newsletter APIs unless a frontend-only solution is insufficient.
- Do not add dependencies.

## Naming

Use `Newsletter` for public user-facing labels.

Public UI changes:

- Home card title becomes `Newsletter`.
- `/newsletters` page title becomes `Newsletter`.
- Top navigation link becomes `Newsletter`.
- Home card description should avoid repeating `Newsletter` awkwardly. Recommended text: "Open the latest issue and browse previous issues by date."

Admin UI:

- Admin screens may keep Korean administrative words such as "admin", "create", and "edit" equivalents.
- When the object name is shown, use `Newsletter`.
- Example: admin Newsletter list title should read as "Admin Newsletter list" in the existing Korean UI style.

## Preview Date Display

The preview panel should show the selected issue date above or near the Newsletter title.

Example layout:

```text
2026-03-26
Aerospace Daily News
```

Preferred source:

- `newsletter.published_at`

Fallback:

- If `published_at` is missing, derive the date from the selected calendar entry.
- If neither exists, omit the date rather than showing a placeholder.

## Previous / Next Issue Navigation

Add two navigation links near the preview header:

- previous issue date
- next issue date

User-facing labels should be Korean equivalents of:

- previous date
- next date

Direction rules:

- next date means a newer issue than the currently selected issue
- previous date means an older issue than the currently selected issue

Disabled states:

- if there is no newer issue, disable the next link
- if there is no older issue, disable the previous link

Link format:

```text
/newsletters?slug=<targetSlug>&theme=<currentTheme>
```

## Data Flow

`/newsletters` already fetches:

- active Newsletter detail
- calendar entries
- current theme

The page should compute adjacent issue links from:

- `calendarEntries`
- `activeDetail.slug`
- `newsletterTheme`

Recommended component boundary:

- `NewslettersWorkspace` remains the client shell for selected asset state.
- `NewsletterPreviewPanel` receives optional `displayDate` and optional `dateNavigation` props.
- `NewsletterDetailClient` remains preview-only and should not own date navigation.

Suggested type:

```ts
type NewsletterDateNavigation = {
  previous?: {
    label: string;
    href: string;
  };
  next?: {
    label: string;
    href: string;
  };
};
```

## Calendar Theme Preservation

Calendar date links must keep the current theme:

```text
/newsletters?slug=<slug>&theme=<theme>
```

This remains required even though the theme is also stored in a cookie. Explicit query preservation makes direct navigation and tests deterministic.

## Admin Login Review

Admin login should remain.

Reasons:

- Admin routes can create, update, and soft-delete Newsletter records.
- Import / Sync can change local Newsletter records.
- Thumbnail upload and taxonomy mutations require CSRF protection.
- Backend admin APIs already depend on `get_current_admin` and `require_csrf`.

Current development credentials come from `backend/.env`:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

Public `/newsletters` viewing should remain unauthenticated.

## Testing

Add or update tests for:

- home page renders `Newsletter` and does not render the old public "service" label
- nav renders `Newsletter`
- `/newsletters` page title renders `Newsletter`
- preview panel renders the selected issue date
- previous/next links are generated from calendar entries
- previous/next links preserve theme
- boundary states disable missing previous or next links
- admin login remains required for admin pages

## Acceptance Criteria

- Public user-facing label is `Newsletter`.
- Preview header shows the selected issue date.
- Preview header provides previous/next issue-date navigation.
- Date navigation keeps the current theme.
- Calendar date links keep the current theme.
- Admin login remains in place and documented as necessary.
- Tests, typecheck, build, and runtime checks pass.
