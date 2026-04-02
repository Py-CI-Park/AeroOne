# AeroOne Frontend Log Pattern Analysis Design

Date: 2026-04-03
Status: Approved for planning

## Summary

`AeroOne` uses separate Windows terminals for backend and frontend startup. The backend terminal appears to emit dense request-by-request logs, while the frontend terminal appears to emit fewer lines and a different pattern. The approved analysis concludes that this is expected behavior, not a launcher defect.

The root cause is architectural. The backend terminal runs `uvicorn`, which emits access logs for every API request it receives. The frontend terminal runs `next dev`, which emits development-server logs for compile events, hot reload activity, and requests handled directly by the Next.js server. In the current `AeroOne` structure, many user-facing data requests bypass the Next.js server and go directly to the backend, so they never appear in the frontend terminal.

## Goals

- Explain why the frontend terminal log pattern differs from the backend terminal log pattern.
- Ground the explanation in the current `AeroOne` request flow rather than generic framework behavior alone.
- Distinguish expected framework behavior from launcher or terminal misconfiguration.
- Define what kind of structural change would be required if matching log density were ever desired.

## Non-Goals

- Changing the current frontend or backend runtime commands.
- Modifying `start.bat`, `start_frontend_window.cmd`, or the launcher scripts to change log formatting.
- Adding frontend request logging, middleware, proxies, or route handlers.
- Converting this analysis into an implementation plan for logging changes.

## Current State

- The backend terminal launches `uvicorn app.main:app --host 0.0.0.0 --port 18437`.
- The frontend terminal launches `next dev -p 29501`.
- The backend terminal shows one log line per API request because `uvicorn` access logging is active by default in the current workflow.
- The frontend terminal shows:
  - Next.js startup information
  - compile activity such as `Compiling /newsletters ...`
  - requests handled directly by Next.js such as `GET /newsletters 200`
  - static asset handling such as `GET /icon.svg 200`
- Many newsletter data requests are not handled by the Next.js dev server and therefore do not appear in the frontend terminal.

## Approved Explanation

### 1. Different server processes produce different log styles

The backend and frontend windows do not run equivalent server types.

- Backend: `uvicorn`
- Frontend: `next dev`

`uvicorn` behaves like an API server with access logging and emits a line for each request it serves. `next dev` behaves like a development application server and emphasizes compile, rebuild, and direct route handling logs. This means the two windows should not be expected to produce the same line-for-line pattern even when both are healthy.

### 2. Server-rendered newsletter data fetches go straight to the backend

`frontend/lib/api.ts` defines two base URLs:

- `SERVER_BASE` for server-side fetches
- `BROWSER_BASE` for browser-side fetches

Both default to the backend host on port `18437`.

The newsletter server components use `fetch()` calls that go directly to `SERVER_BASE`, including:

- newsletter list
- calendar data
- latest newsletter detail
- specific newsletter detail
- initial newsletter HTML asset fetches

Because these fetches go directly from the Next.js server runtime to the backend, they produce backend logs but do not generate additional frontend terminal access-style lines beyond the original page request handled by Next.js.

### 3. Client-side newsletter asset fetches also go straight to the backend

`NewsletterDetailClient` uses `getBrowserApiBase()` for asset fetches triggered by client interaction. That means the browser directly requests the backend for asset content and downloads.

As a result:

- the backend terminal logs these requests
- the frontend terminal does not, because the request never traverses the Next.js server on `29501`

This is why selecting newsletter assets can visibly increase backend log volume without producing matching frontend lines.

### 4. Only requests handled by Next.js appear in the frontend terminal

The frontend terminal logs requests such as:

- `/`
- `/newsletters`
- `/newsletters?slug=...`
- `/icon.svg`

These are routes or assets actually served by Next.js. The frontend terminal therefore represents Next.js-handled traffic plus dev-server lifecycle events, not the full application request graph.

## Request Flow Map

### Newsletters landing page

1. Browser requests `http://localhost:29501/newsletters`
2. Next.js handles the route and logs the page request in the frontend terminal
3. During server rendering, Next.js fetches newsletter list, calendar data, and default detail data from the backend at `18437`
4. The backend logs those API calls in the backend terminal
5. The frontend terminal does not emit one line per internal backend fetch

### Newsletter detail page

1. Browser requests `http://localhost:29501/newsletters/[slug]`
2. Next.js handles the page route and logs the page request in the frontend terminal
3. The server component fetches detail metadata and initial HTML asset content directly from the backend
4. The backend terminal logs those fetches

### Client-side asset switching

1. User interacts with the rendered page
2. Browser fetches asset content directly from backend endpoints under `/api/v1/...`
3. Backend terminal logs those requests
4. Frontend terminal stays quiet unless the interaction also triggers a Next.js route transition or compile event

## Why Launcher Changes Alone Cannot Make The Logs Match

The observed difference is not caused by terminal colorization, `cmd /k` behavior, or launcher startup sequencing.

Even if launcher scripts are rewritten, the frontend terminal will still only show requests and lifecycle events visible to the Next.js dev server. To make the frontend terminal look more like the backend terminal, the architecture would need to change so that more application traffic is routed through Next.js first.

Examples of structural changes that would alter the logging pattern:

- introducing Next.js Route Handlers or a BFF layer for newsletter APIs
- proxying browser API traffic through Next.js instead of sending it directly to the backend
- adding explicit server-side fetch logging inside the Next.js application runtime

Those are architecture or observability changes, not launcher fixes.

## Expected Conclusion

The approved conclusion for this investigation is:

`The frontend terminal emits fewer and differently shaped logs than the backend terminal because it is running Next.js development-server logging while much of AeroOne's application data traffic goes directly to the backend. This is expected behavior in the current architecture, not evidence of a launcher defect.`

## Files Reviewed

- `frontend/package.json`
- `frontend/lib/api.ts`
- `frontend/app/newsletters/page.tsx`
- `frontend/app/newsletters/[slug]/page.tsx`
- `frontend/components/newsletter/newsletter-detail-client.tsx`
- `frontend/next.config.ts`
- `scripts/start_frontend_window.cmd`

## Verification Plan

### Static verification

- confirm the frontend runtime command is `next dev -p 29501`
- confirm the frontend API base helpers default to backend port `18437`
- confirm newsletter page server components call backend endpoints directly
- confirm newsletter client components call backend endpoints directly
- confirm there is no Next.js proxy or rewrite layer that would cause the frontend server to own those API requests

### Behavioral verification

- run the app and compare frontend terminal output with backend terminal output
- navigate to `/newsletters`
- open different newsletter details
- switch newsletter assets when available
- verify that backend logs grow with API activity while frontend logs primarily reflect route handling and compile events

## Rationale

This design intentionally stops at explanation instead of proposing code changes. The investigation request is about understanding the current behavior, and the evidence shows the visible log difference follows directly from the current request topology and the differing logging policies of `uvicorn` and `next dev`.

Any future effort to unify the log shape should be treated as a separate observability or routing design, not as a bug fix for the current launcher.
