# AeroOne Home Hero Removal Design

Date: 2026-04-04
Status: Approved for planning

## Summary

The current home page displays a top hero section above the newsletter service card. The request is to remove that hero content completely, with no replacement text and no leftover blank area, so the newsletter service card becomes the first visible content on the page.

The approved design keeps the change intentionally small. It removes the hero section from `frontend/app/page.tsx` and adds a focused home-page regression test to confirm that the removed copy no longer appears while the newsletter service card remains visible and linked.

## Goals

- Remove the home-page hero section completely.
- Leave no placeholder or intentional blank area where the hero used to be.
- Keep the newsletter service card visible as the first main content on the page.
- Add a regression test so the removed copy does not reappear accidentally.

## Non-Goals

- Replacing the hero with new text or a new design.
- Refactoring the dashboard card component.
- Changing newsletter routing or page behavior.
- Redesigning the rest of the home page.

## Current State

- `frontend/app/page.tsx` renders:
  - an `AppShell`
  - a hero `<section>` containing:
    - `AeroOne Internal Platform`
    - `사내 문서형 서비스 시작점`
    - explanatory copy about starting with the newsletter service
  - a second `<section>` containing the newsletter service card grid
- There is currently no focused home-page regression test that locks down the presence or removal of this hero section.

## Approved Approach

### 1. Remove the hero section entirely

Delete the top hero `<section>` from `frontend/app/page.tsx`.

The newsletter service card grid remains in place and becomes the first rendered page content inside `AppShell`.

This is a true removal, not a hide/show toggle and not a copy replacement.

### 2. Keep the service card section unchanged

The newsletter service card should keep its current route target and visibility.

This ensures the user still lands on a useful home page and can immediately navigate to the newsletter service.

### 3. Add a focused home-page regression test

Add a test for the home page that verifies:

- the removed hero copy is absent
- the newsletter service link remains present

This protects the deletion from being accidentally reverted during later UI work.

## Files Expected To Change

- `frontend/app/page.tsx`
- `frontend/tests/app/home-page.test.tsx` (new) or an equivalent focused home-page test file

## Verification Plan

### Static verification

- confirm the hero `<section>` no longer exists in `frontend/app/page.tsx`
- confirm the newsletter service card section still exists

### Automated verification

- run a focused home-page test
- run the frontend test suite
- run frontend typecheck

Recommended commands:

```bash
npm run test -- tests/app/home-page.test.tsx
npm run test
npm run typecheck
```

### Functional verification

- open the home page
- confirm the hero copy is gone
- confirm the newsletter card is the first main content shown

## Rationale

The request is a pure deletion task. The safest and clearest implementation is to remove the hero section outright rather than introduce conditional rendering or placeholder layout. That keeps the diff small, leaves no dead UI branch behind, and matches the requested outcome exactly.
