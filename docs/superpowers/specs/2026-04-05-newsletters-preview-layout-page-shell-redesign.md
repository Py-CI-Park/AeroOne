# AeroOne Newsletters Preview Page-Shell Redesign

Date: 2026-04-05
Status: Approved for planning

## Summary

The previous `/newsletters` work improved child components, but it did not make the route feel structurally close to `Newsletter_AI`'s report preview page. The user feedback is correct: the page still reads like a calendar followed by a generic detail component, not like a report-style preview workspace.

This design treats the next step as a new, explicitly route-level redesign. The `/newsletters` page shell itself should be rebuilt so the page clearly presents:

1. a calendar panel
2. a format selector panel
3. a large preview panel

The goal is to reproduce the visual hierarchy and interaction flow of `Newsletter_AI`'s preview page without copying its run-history or artifact-index features.

## Goals

- Make `/newsletters` visibly feel like a preview workspace at the route level.
- Move the layout hierarchy into `frontend/app/newsletters/page.tsx`.
- Make the page itself clearly render:
  - calendar panel
  - format selector panel
  - large preview panel
- Keep the calendar open by default.
- Keep PDF preview-first with download fallback.
- Preserve current AeroOne data flow and newsletter APIs.

## Non-Goals

- Copying `Newsletter_AI` report run history.
- Adding report/file browsing or artifact indexing.
- Rebuilding AeroOne around a report-management model.
- Adding unrelated dashboard features outside `/newsletters`.

## Why The Previous Attempt Was Insufficient

The previous implementation improved behavior inside child components:

- calendar default-open
- selector/panel labels inside `NewsletterDetailClient`
- PDF preview-first with fallback

But the route shell itself stayed almost the same:

- `NewsletterDateCalendar`
- `NewsletterDetailClient`

That meant the user still experienced the page as “calendar plus detail component,” not as a page with three distinct stages. The missing work was not inside a viewer; it was at the page-shell composition layer.

## Approved Approach

### 1. Rebuild the route shell, not just the child component

`frontend/app/newsletters/page.tsx` should directly express the page structure.

The route should render three explicit sections in order:

- calendar panel
- format selector panel
- large preview panel

This structure must be visible in the page shell itself, not only implied inside a child component.

### 2. Reduce or split `NewsletterDetailClient`

`NewsletterDetailClient` should no longer function as the page’s all-in-one container.

Approved direction:

- shrink it to a smaller stateful helper, or
- split it into units such as:
  - `NewsletterAssetSelector`
  - `NewsletterPreviewPanel`

The page shell should orchestrate panel order and hierarchy.

### 3. Keep the calendar as the top control layer

`NewsletterDateCalendar` remains the first panel.

Required behavior:

- visible by default
- no dedicated open/close toggle
- month navigation preserved
- selecting a date still drives the selected newsletter

### 4. Keep the middle selector panel distinct

The asset selector must be visibly separate from preview rendering.

It should no longer feel like “tabs inside the detail card.” It should read as the second step in the page flow:

- pick date
- pick format
- inspect preview

### 5. Keep the lower preview panel dominant

The preview panel should be the most visually prominent area on the page.

Approved behavior:

- `HTML` -> render in `HtmlViewer`
- `Markdown` -> render in `MarkdownViewer`
- `PDF` -> try inline preview in `PdfViewer`
- fallback -> download-oriented panel only when inline preview cannot be shown

If necessary, reduce redundant card chrome so the preview reads as one destination surface.

### 6. Keep scope aligned with AeroOne

Do not add:

- report runs
- artifact file lists
- output browser controls
- file-path surfaces
- `Newsletter_AI` operations/reporting concepts

This remains a public newsletter consumption page, not a report artifact explorer.

## Data Flow

### Route/server layer

- resolve selected newsletter from the current `slug`
- fetch calendar entries
- fetch detail data
- fetch initial HTML when the default asset is not PDF

### Page-level client layer

- own selected asset type
- coordinate the selector and preview relationship
- expose PDF preview state clearly

### Preview layer

- HTML and Markdown continue to use the current preview mechanisms
- PDF continues to use the current frontend proxy path and inline preview/fallback flow

The key change is not the raw data flow itself, but where the structure is expressed.

## Files Expected To Change

Primary:

- `frontend/app/newsletters/page.tsx`
- `frontend/components/newsletter/newsletter-detail-client.tsx`

Likely additions:

- `frontend/components/newsletter/newsletter-asset-selector.tsx`
- `frontend/components/newsletter/newsletter-preview-panel.tsx`

Possible supporting updates:

- `frontend/components/newsletter/newsletter-date-calendar.tsx`
- `frontend/components/newsletter/html-viewer.tsx`
- `frontend/components/newsletter/markdown-viewer.tsx`
- `frontend/components/newsletter/pdf-viewer.tsx`

Likely tests to update:

- `frontend/tests/app/newsletters-page.test.tsx`
- `frontend/tests/components/newsletter-detail-client.test.tsx`
- `frontend/tests/components/newsletter-date-calendar.test.tsx`
- new route-level layout test if that yields a cleaner contract

## Verification Plan

### Static verification

- confirm `/newsletters` directly renders the three panels in the route shell
- confirm no `Newsletter_AI` run-history or file-index concepts were introduced

### Automated verification

- add or update route-level tests so they assert actual panel hierarchy
- preserve component-level tests for calendar and preview behavior
- run full frontend test suite
- run frontend typecheck
- run frontend build

### Functional verification

- open `/newsletters`
- confirm the page visually reads as:
  - top calendar panel
  - middle format selector panel
  - large lower preview panel
- select dates and formats
- confirm PDF preview-first and fallback still work

## Rationale

The problem is no longer “can AeroOne technically preview the same formats?” It can. The problem is “does the page structurally read like the reference?” Right now it does not.

This redesign fixes that by making the page shell itself carry the interaction hierarchy. That is the missing step needed to make the result feel like `Newsletter_AI` in the way the user actually perceives it.
