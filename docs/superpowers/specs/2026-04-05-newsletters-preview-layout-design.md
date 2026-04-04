# AeroOne Newsletters Preview Layout Design

Date: 2026-04-05
Status: Approved for planning

## Summary

`AeroOne` already has the core building blocks needed for a report-style preview experience on `/newsletters`: a date calendar, multiple asset types (`html`, `markdown`, `pdf`), and preview renderers for HTML and Markdown. The request is to review whether the structural pattern used in `Newsletter_AI`'s report preview tab can be applied here.

The approved conclusion is yes, but only at the level of layout structure. `AeroOne` should adopt the same high-level interaction flow:

1. calendar/date selection
2. format selection (`HTML`, `Markdown`, `PDF`)
3. large preview area below

This should be implemented only for the public `/newsletters` screen. The `Newsletter_AI` report index, run history, artifact browser, and file-management behavior should not be copied.

## Goals

- Reorganize the `/newsletters` page into a clearer preview-first layout.
- Keep the current date calendar behavior.
- Keep the current HTML / Markdown / PDF asset model.
- Make the preview surface visually read as the primary destination of the page.
- Reuse current `AeroOne` data and components rather than importing `Newsletter_AI` report features wholesale.

## Non-Goals

- Rebuilding `AeroOne` around the `Newsletter_AI` report index architecture.
- Adding run history, report sessions, or output-file browser features.
- Adding admin/report-generation concerns to the public newsletter page.
- Replacing current newsletter APIs with `Newsletter_AI` APIs.
- Implementing PDF inline preview in this same step unless separately approved.

## Current State

- `frontend/app/newsletters/page.tsx` already renders:
  - `NewsletterDateCalendar`
  - `NewsletterDetailClient`
- `NewsletterDetailClient` already provides:
  - asset-type selector buttons
  - HTML preview via `HtmlViewer`
  - Markdown preview via `MarkdownViewer`
  - PDF handling as a download-oriented panel
- This means the current page already contains most of the required behavior, but the structure reads more like:
  - page shell
  - date selector
  - detail component

rather than a clearly staged:

- calendar
- format selector
- preview canvas

## Reference Pattern From `Newsletter_AI`

The relevant `Newsletter_AI` screen is the reports preview page under:

- `frontend/src/app/(dashboard)/reports/page.tsx`

The structure there is:

- left/top calendar area for choosing a date with artifacts
- run/session list for the selected date
- artifact-type selection (`HTML`, `Markdown`, `PDF`)
- large preview panel below that changes based on the currently selected artifact

For `AeroOne`, the transferable part is not the report-run model itself, but the layout hierarchy:

- a selection layer above
- a dedicated preview layer below

## Approved Approach

### 1. Apply the structure only to `/newsletters`

This work is intentionally scoped to:

- `frontend/app/newsletters/page.tsx`
- related newsletter preview components

No other pages should be reworked as part of this change.

### 2. Keep the existing calendar as the top control surface

`NewsletterDateCalendar` already fulfills the role of the top-level date selector and should remain the first major control region on the page.

It does not need to become identical to `Newsletter_AI`'s calendar implementation. It only needs to continue serving as the “choose a newsletter date” control layer.

### 3. Make asset-type selection read as an explicit middle panel

The existing HTML / Markdown / PDF buttons inside `NewsletterDetailClient` should be preserved, but visually and structurally they should be treated as a separate “format selection” layer rather than just a small header control.

This is the main transferable concept from `Newsletter_AI`:

- selected date chooses the newsletter
- selected asset chooses the representation

### 4. Make the lower preview area the clear primary surface

The preview area should be visually emphasized as the main content destination of the page.

Current behavior should remain:

- `html` → rendered in `HtmlViewer`
- `markdown` → rendered in `MarkdownViewer`
- `pdf` → download-oriented fallback panel

The page should read like:

- top: calendar/date
- middle: asset selection
- bottom: preview

### 5. Do not copy `Newsletter_AI` report complexity

The following should stay out of scope:

- report run/session list
- output artifact indexing
- file path awareness
- report-history navigation
- report-generation or operations concepts

Those are specific to the reporting workflow in `Newsletter_AI` and do not belong on the public newsletter consumption page unless separately requested.

## Design Constraints

- Keep current newsletter APIs and selection flow intact.
- Prefer recomposition of existing newsletter components over large new feature additions.
- If component boundaries become unclear, split them by responsibility:
  - calendar selection
  - asset selection
  - preview rendering
- Avoid mixing preview rendering concerns with data-fetch orchestration more than necessary.

## PDF Handling Decision

For this design, PDF should remain download-oriented.

Rationale:

- `Newsletter_AI` uses a richer report-artifact preview context where PDF preview is a core report browsing feature.
- `AeroOne` currently treats PDF as a downloadable representation.
- Expanding into inline PDF preview would enlarge scope and introduce a second design problem.

If PDF inline preview is desired later, it should be treated as a separate follow-up step after the layout restructuring lands.

## Files Expected To Change

Likely change set:

- `frontend/app/newsletters/page.tsx`
- `frontend/components/newsletter/newsletter-detail-client.tsx`

Possible supporting additions if clearer boundaries are needed:

- a new newsletter asset selector component
- a new newsletter preview panel component

Possible test updates:

- `frontend/tests/app/newsletters-page.test.tsx`
- `frontend/tests/components/newsletter-detail-client.test.tsx`
- any new focused layout test file if the component split warrants it

## Verification Plan

### Static verification

- confirm `/newsletters` still uses the same calendar + asset + preview data flow
- confirm no `Newsletter_AI`-specific run-history or file-index concepts were imported into `AeroOne`

### Automated verification

- update existing page/component tests for the new structure
- ensure HTML / Markdown / PDF selection behavior still works
- run the full frontend test suite
- run frontend typecheck

### Functional verification

- open `/newsletters`
- select dates from the calendar
- switch between `HTML`, `Markdown`, and `PDF`
- confirm the page visually reads as:
  - calendar
  - format selector
  - preview area

## Rationale

This is a strong fit for `AeroOne` because the needed primitives already exist. The right move is not to copy `Newsletter_AI` feature-for-feature, but to reuse its layout logic:

- staged selection
- explicit format switching
- dominant preview surface

That preserves the simplicity of `AeroOne` while making the newsletter page easier to understand and closer to a report-preview workflow.
