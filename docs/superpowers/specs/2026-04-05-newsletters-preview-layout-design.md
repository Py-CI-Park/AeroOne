# AeroOne Newsletters Preview Layout Design

Date: 2026-04-05
Status: Approved for planning

## Summary

The earlier implementation improved individual newsletter components, but it did not make the `/newsletters` route feel structurally similar to `Newsletter_AI`'s report preview screen. The user feedback is valid: the page still reads like “calendar plus a generic detail component” rather than a staged preview workflow.

The approved revision is to move the layout responsibility up to the route level. `AeroOne` should restructure `/newsletters` so the page clearly reads as:

1. calendar/date selection
2. format selection (`HTML`, `Markdown`, `PDF`)
3. one large preview surface below

The goal is not to copy `Newsletter_AI` feature-for-feature, but to reproduce its information hierarchy and visual flow on the public newsletter page.

## Goals

- Make `/newsletters` visibly read as a preview workspace rather than a generic detail page.
- Give the route a clear page-level structure:
  - calendar panel
  - asset selector panel
  - dominant preview panel
- Keep the current newsletter data flow and route behavior.
- Keep the calendar open by default.
- Make PDF preview-first, with download fallback when inline preview cannot be shown.
- Reuse existing AeroOne components where possible, but restructure them so the page-level hierarchy is obvious.

## Non-Goals

- Importing `Newsletter_AI` report-session history, file index, or run browser concepts.
- Rebuilding AeroOne around the `Newsletter_AI` reporting architecture.
- Changing newsletter APIs.
- Adding admin/report-generation concerns to the public newsletter page.
- Introducing new unrelated dashboard patterns outside `/newsletters`.

## Root Cause Of The Previous Mismatch

The previous work improved behavior inside child components, but did not materially change the route-level page shell.

Specifically:

- `NewsletterDateCalendar` was opened by default
- `NewsletterDetailClient` gained more explicit internal panels
- PDF became preview-first with fallback

But `/newsletters` itself still rendered the same high-level structure:

- page shell
- calendar component
- detail component

That means the user still perceived the same page, only with local improvements inside the detail component. The missing step was a route-level layout migration.

## Current State

- `frontend/app/newsletters/page.tsx` still owns the page shell, data fetching, and composition.
- `frontend/components/newsletter/newsletter-date-calendar.tsx` already serves as the date selector.
- `frontend/components/newsletter/newsletter-detail-client.tsx` currently mixes:
  - selected asset controls
  - preview rendering
  - PDF fallback behavior
- Existing viewer components already exist:
  - `HtmlViewer`
  - `MarkdownViewer`
  - `PdfViewer`

This means the primitives are available, but the page-level composition is still too implicit.

## Reference Pattern From `Newsletter_AI`

The relevant reference is:

- `D:\Chanil_Park\Project\Programming\Newsletter_AI\frontend\src\app\(dashboard)\reports\page.tsx`

The important part to copy is not the report-history model. The transferable part is the route’s visual hierarchy:

- a top selection panel
- a second selection layer for output format
- a large lower preview area that visibly acts as the page’s main surface

That hierarchy is what users recognize, and that is what AeroOne currently lacks.

## Approved Approach

### 1. Rebuild the `/newsletters` page shell around three explicit sections

`frontend/app/newsletters/page.tsx` should explicitly render three recognizable sections in order:

- calendar panel
- format selector panel
- large preview panel

The route itself should make this structure obvious. It should not rely on a generic detail component to imply the page hierarchy indirectly.

### 2. Keep the calendar as the top panel and make it always visible

`NewsletterDateCalendar` remains the top-level date selector.

Approved behavior:

- always open by default
- no dedicated open/close toggle
- month navigation retained
- selecting a date continues to drive the selected newsletter

This keeps the existing behavior while making the route read more like a browsing workspace.

### 3. Break the middle selection layer out as a clear format selector panel

The format selector should be a first-class section at the page level, not just a set of buttons embedded inside a generic detail header.

Recommended shape:

- one selector panel that lists the available asset types
- one active state that clearly indicates the chosen representation
- the selector should visually sit between calendar selection and preview rendering

This is the main structural difference users are asking for.

### 4. Make the lower preview surface visually dominant

The lower panel should own the visual weight of the page.

Approved behavior:

- `HTML` -> render in `HtmlViewer`
- `Markdown` -> render in `MarkdownViewer`
- `PDF` -> try inline preview in `PdfViewer`
- if PDF preview fails -> show a fallback state with a direct download action

The preview panel should read as one destination surface. If necessary, inner viewer card chrome should be reduced so the page does not feel like “a card inside another card inside another card.”

### 5. Re-scope `NewsletterDetailClient`

`NewsletterDetailClient` should no longer be the place where the whole page hierarchy is implied.

Approved direction:

- either shrink it into a smaller presentational component
- or split its responsibilities into clearer units such as:
  - asset selector panel
  - preview panel

The important rule is that the route-level layout must become explicit.

### 6. Do not import `Newsletter_AI` report complexity

The following remain out of scope:

- run/session list
- artifact index
- file path browser
- report history
- generation/operations concepts

This is a public newsletter consumption screen, not a report artifact management UI.

## Design Constraints

- Preserve current newsletter route behavior and API usage.
- Prefer reusing existing AeroOne data and viewer components.
- Move page hierarchy into the route shell rather than hiding it inside one child component.
- Keep PDF preview-first with fallback.
- Avoid bringing in unrelated `Newsletter_AI` complexity.

## PDF Decision

PDF should remain:

- preview first
- download fallback second

That decision stays unchanged.

What changes is not the PDF policy, but where it sits in the page hierarchy: PDF should now feel like one of the three preview modes in a shared lower preview surface.

## Files Expected To Change

Primary files:

- `frontend/app/newsletters/page.tsx`
- `frontend/components/newsletter/newsletter-detail-client.tsx`

Likely supporting additions:

- `frontend/components/newsletter/newsletter-asset-selector.tsx`
- `frontend/components/newsletter/newsletter-preview-panel.tsx`

Likely supporting updates:

- `frontend/components/newsletter/newsletter-date-calendar.tsx`
- `frontend/components/newsletter/html-viewer.tsx`
- `frontend/components/newsletter/markdown-viewer.tsx`
- `frontend/components/newsletter/pdf-viewer.tsx`

Likely tests to update:

- `frontend/tests/app/newsletters-page.test.tsx`
- `frontend/tests/components/newsletter-detail-client.test.tsx`
- `frontend/tests/components/newsletter-date-calendar.test.tsx`
- any new layout-focused test file if the selector/panel split becomes clearer with separate coverage

## Verification Plan

### Static verification

- confirm `/newsletters` explicitly renders calendar panel, selector panel, and preview panel
- confirm `Newsletter_AI` run-history or file-index concepts were not imported

### Automated verification

- update route-level tests so they assert page structure, not just mocked child presence
- ensure calendar default visibility is preserved
- ensure HTML / Markdown / PDF all map into the same lower preview area
- ensure PDF preview-first and fallback behavior are covered
- run the full frontend test suite
- run frontend typecheck
- run frontend build

### Functional verification

- open `/newsletters`
- confirm the page clearly reads as:
  - top calendar panel
  - middle format selector panel
  - large lower preview surface
- select dates and confirm preview updates
- switch between HTML / Markdown / PDF
- verify PDF preview appears inline when possible
- verify fallback download UI appears if inline preview cannot be shown

## Rationale

The user’s feedback is correct because the previous implementation solved the sub-behaviors without solving the visible route structure.

This revised design fixes that by moving the information hierarchy into the page shell itself. That preserves AeroOne’s simpler domain model while finally giving `/newsletters` the same structural clarity users recognize from `Newsletter_AI`.
