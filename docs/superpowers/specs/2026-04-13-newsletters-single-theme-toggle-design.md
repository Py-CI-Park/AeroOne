# Newsletters Single Theme Toggle Design

Date: 2026-04-13
Status: Approved for implementation

## Summary

The navigation currently shows two small theme icons. The requested behavior is a single icon next to `로그인` that switches to the opposite theme.

## Behavior

- Current theme `light`
  - visible icon: `☾`
  - aria label: `다크 테마로 전환`
  - href: `/newsletters?theme=dark`
- Current theme `dark`
  - visible icon: `☀`
  - aria label: `라이트 테마로 전환`
  - href: `/newsletters?theme=light`

If a newsletter slug is active, preserve it:

- `/newsletters?slug=<slug>&theme=dark`
- `/newsletters?slug=<slug>&theme=light`

## Scope

Change only the selector rendering and related tests. Keep:

- single frontend port `29501`
- query-string theme switching
- `AppShell` nav placement next to `로그인`
- report-style newsletter layout
- calendar collapse/expand

## Acceptance Criteria

- Only one theme icon is visible.
- The icon always links to the opposite theme.
- The icon preserves slug.
- The icon remains next to `로그인`.
- Tests, typecheck, build, and single-port runtime probes pass.
