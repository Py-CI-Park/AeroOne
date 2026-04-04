# Frontend Newsletter Request Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frontend development terminal show meaningful newsletter request flow by logging server-side newsletter fetches and routing browser-side newsletter asset requests through Next.js before they reach the backend.

**Architecture:** Keep the backend unchanged. Add one focused frontend observability helper for newsletter request logging, add one Next.js catch-all Route Handler for newsletter read traffic, and update the newsletter UI to use same-origin proxy paths for browser-side asset fetches and downloads. This keeps the change narrow, improves frontend-terminal visibility, and avoids rewriting unrelated admin or auth flows.

**Tech Stack:** Next.js App Router, Next Route Handlers, React, TypeScript, Fetch API, Vitest

---

## File Structure

- `frontend/lib/newsletter-observability.ts`
  - New pure/helper module.
  - Owns proxy path building, upstream newsletter path building, and a logged server-side JSON fetch helper.
- `frontend/app/api/frontend/newsletters/[...segments]/route.ts`
  - New Next.js Route Handler for newsletter read traffic.
  - Logs inbound frontend-side requests and forwards them to the backend.
- `frontend/lib/api.ts`
  - Existing API helper surface.
  - Should keep its public shape where possible, but switch newsletter server-side reads to the new logged helper.
- `frontend/app/newsletters/page.tsx`
  - Server component for the newsletters landing page.
  - Should use a dedicated newsletter asset content helper instead of raw inline fetch.
- `frontend/app/newsletters/[slug]/page.tsx`
  - Server component for the newsletter detail page.
  - Same server-side asset-content logging boundary as the landing page.
- `frontend/components/newsletter/newsletter-detail-client.tsx`
  - Client-side asset switching and download links.
  - Should switch from direct backend URLs to same-origin proxy URLs.
- `frontend/tests/lib/api.test.ts`
  - Existing API helper regression file.
  - Extend it rather than creating another generic API test file.
- `frontend/tests/lib/newsletter-observability.test.ts`
  - New focused helper test file for path mapping and logged server fetch behavior.
- `frontend/tests/components/newsletter-detail-client.test.tsx`
  - Existing component test file.
  - Extend it to verify proxy-path usage for client-side fetches and download links.

## Notes Before Editing

- The current branch already contains unrelated launcher-script changes in:
  - `start.bat`
  - `scripts/start_frontend_dev.cmd`
  - `scripts/start_frontend_window.cmd`
  - `scripts/windows/wait_for_services.ps1`
- Do not stage or rewrite those files while implementing this plan.
- Before the first code change, inspect the working tree and keep later `git add` commands targeted:

```powershell
git status --short
```

Expected:

- You can see the pre-existing launcher changes and avoid staging them by accident.

---

### Task 1: Add Newsletter Observability Helpers With Failing Tests

**Files:**
- Create: `frontend/lib/newsletter-observability.ts`
- Create: `frontend/tests/lib/newsletter-observability.test.ts`

- [ ] **Step 1: Write the failing helper tests**

Create `frontend/tests/lib/newsletter-observability.test.ts` with this content:

```ts
import { vi } from 'vitest';

import {
  buildNewsletterProxyPath,
  buildNewsletterUpstreamPath,
  loggedServerFetchJson,
} from '@/lib/newsletter-observability';

afterEach(() => {
  vi.restoreAllMocks();
});

test('maps newsletter backend paths to same-origin proxy paths', () => {
  expect(buildNewsletterProxyPath('/api/v1/newsletters/13/content/html')).toBe(
    '/api/frontend/newsletters/13/content/html',
  );
  expect(buildNewsletterProxyPath('/api/v1/newsletters/13/download/pdf')).toBe(
    '/api/frontend/newsletters/13/download/pdf',
  );
});

test('rejects non-newsletter backend paths', () => {
  expect(() => buildNewsletterProxyPath('/api/v1/admin/newsletters')).toThrow(
    'Only newsletter read paths can be proxied',
  );
});

test('builds backend upstream path from catch-all route segments', () => {
  expect(buildNewsletterUpstreamPath(['latest'])).toBe('/api/v1/newsletters/latest');
  expect(buildNewsletterUpstreamPath(['13', 'content', 'html'], '?preview=1')).toBe(
    '/api/v1/newsletters/13/content/html?preview=1',
  );
});

test('loggedServerFetchJson logs request and response around backend fetch', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [{ id: 1 }],
  });
  const logger = vi.fn();

  const result = await loggedServerFetchJson<{ id: number }[]>({
    label: 'newsletters.list',
    baseUrl: 'http://localhost:18437',
    path: '/api/v1/newsletters',
    fetchImpl: fetchMock,
    log: logger,
  });

  expect(result).toEqual([{ id: 1 }]);
  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(logger).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
  expect(logger).toHaveBeenNthCalledWith(
    2,
    '[FRONTEND][FETCH] newsletters.list <- 200 /api/v1/newsletters',
  );
});
```

- [ ] **Step 2: Run the helper tests to verify they fail first**

Run:

```powershell
npm run test -- tests/lib/newsletter-observability.test.ts
```

Expected:

- FAIL because `@/lib/newsletter-observability` does not exist yet.

- [ ] **Step 3: Add the observability helper module**

Create `frontend/lib/newsletter-observability.ts` with this content:

```ts
type LoggedFetchOptions = {
  label: string;
  baseUrl: string;
  path: string;
  init?: RequestInit;
  fetchImpl?: typeof fetch;
  log?: (message: string) => void;
};

const NEWSLETTER_BACKEND_PREFIX = '/api/v1/newsletters';
const NEWSLETTER_PROXY_PREFIX = '/api/frontend/newsletters';

export function buildNewsletterProxyPath(path: string) {
  if (!path.startsWith(`${NEWSLETTER_BACKEND_PREFIX}/`)) {
    throw new Error('Only newsletter read paths can be proxied');
  }

  return path.replace(NEWSLETTER_BACKEND_PREFIX, NEWSLETTER_PROXY_PREFIX);
}

export function buildNewsletterUpstreamPath(segments: string[], search = '') {
  const cleanSegments = segments.filter(Boolean).map((segment) => encodeURIComponent(segment));
  const suffix = cleanSegments.length ? `/${cleanSegments.join('/')}` : '';
  return `${NEWSLETTER_BACKEND_PREFIX}${suffix}${search}`;
}

export async function loggedServerFetchJson<T>({
  label,
  baseUrl,
  path,
  init,
  fetchImpl = fetch,
  log = console.info,
}: LoggedFetchOptions): Promise<T> {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  log(`[FRONTEND][FETCH] ${label} -> ${normalizedPath}`);
  const response = await fetchImpl(`${normalizedBaseUrl}${normalizedPath}`, {
    cache: 'no-store',
    ...init,
  });
  log(`[FRONTEND][FETCH] ${label} <- ${response.status} ${normalizedPath}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${normalizedPath}`);
  }

  return (await response.json()) as T;
}
```

- [ ] **Step 4: Run the helper tests to verify they now pass**

Run:

```powershell
npm run test -- tests/lib/newsletter-observability.test.ts
```

Expected:

- PASS.

- [ ] **Step 5: Commit the helper checkpoint**

Run:

```powershell
git add frontend/lib/newsletter-observability.ts frontend/tests/lib/newsletter-observability.test.ts
git commit -m "feat: add newsletter observability helpers"
```

Expected:

- A commit exists containing only the new helper and its tests.

---

### Task 2: Add a Next.js Newsletter Proxy Route

**Files:**
- Create: `frontend/app/api/frontend/newsletters/[...segments]/route.ts`
- Modify: `frontend/tests/lib/newsletter-observability.test.ts`

- [ ] **Step 1: Add failing tests for upstream path forwarding**

Append this test to `frontend/tests/lib/newsletter-observability.test.ts`:

```ts
test('buildNewsletterUpstreamPath preserves nested newsletter asset paths', () => {
  expect(buildNewsletterUpstreamPath(['38', 'content', 'html'])).toBe(
    '/api/v1/newsletters/38/content/html',
  );
  expect(buildNewsletterUpstreamPath(['38', 'download', 'pdf'])).toBe(
    '/api/v1/newsletters/38/download/pdf',
  );
});
```

- [ ] **Step 2: Run the helper tests again**

Run:

```powershell
npm run test -- tests/lib/newsletter-observability.test.ts
```

Expected:

- PASS, confirming the helper covers the route-handler forwarding contract before the route exists.

- [ ] **Step 3: Create the newsletter proxy route**

Create `frontend/app/api/frontend/newsletters/[...segments]/route.ts` with this content:

```ts
import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';
import { buildNewsletterUpstreamPath } from '@/lib/newsletter-observability';

export const dynamic = 'force-dynamic';

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  const { segments } = await context.params;
  const upstreamPath = buildNewsletterUpstreamPath(segments, request.nextUrl.search);
  const upstreamUrl = `${getServerApiBase()}${upstreamPath}`;

  console.info(
    `[FRONTEND][API  ] GET ${request.nextUrl.pathname}${request.nextUrl.search} -> ${upstreamPath}`,
  );

  const upstreamResponse = await fetch(upstreamUrl, {
    method: 'GET',
    cache: 'no-store',
    headers: {
      accept: request.headers.get('accept') ?? '*/*',
    },
  });

  console.info(
    `[FRONTEND][API  ] ${upstreamResponse.status} ${upstreamPath}`,
  );

  const body = await upstreamResponse.arrayBuffer();
  const response = new NextResponse(body, {
    status: upstreamResponse.status,
  });

  const contentType = upstreamResponse.headers.get('content-type');
  if (contentType) {
    response.headers.set('content-type', contentType);
  }

  const contentDisposition = upstreamResponse.headers.get('content-disposition');
  if (contentDisposition) {
    response.headers.set('content-disposition', contentDisposition);
  }

  return response;
}
```

- [ ] **Step 4: Verify the route file type-checks**

Run:

```powershell
npm run typecheck
```

Expected:

- PASS.

- [ ] **Step 5: Commit the proxy-route checkpoint**

Run:

```powershell
git add frontend/app/api/frontend/newsletters/[...segments]/route.ts frontend/tests/lib/newsletter-observability.test.ts
git commit -m "feat: add newsletter proxy route"
```

Expected:

- A commit exists containing the route handler and its forwarding-contract test.

---

### Task 3: Route Newsletter UI Asset Traffic Through Next.js

**Files:**
- Modify: `frontend/components/newsletter/newsletter-detail-client.tsx`
- Modify: `frontend/tests/components/newsletter-detail-client.test.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Extend the client component tests with failing proxy expectations**

Update `frontend/tests/components/newsletter-detail-client.test.tsx` with these additions:

```ts
test('requests html assets through the frontend newsletter proxy', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Proxy Test',
        slug: 'proxy-test',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'pdf',
      }}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'HTML' }));

  expect(global.fetch).toHaveBeenCalledWith(
    '/api/frontend/newsletters/1/content/html',
  );
});

test('uses the frontend newsletter proxy for pdf downloads', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Proxy PDF',
        slug: 'proxy-pdf',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));

  expect(screen.getByRole('link', { name: 'PDF 다운로드' })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
```

- [ ] **Step 2: Run the component tests to verify they fail first**

Run:

```powershell
npm run test -- tests/components/newsletter-detail-client.test.tsx
```

Expected:

- FAIL because the component still uses backend paths directly.

- [ ] **Step 3: Add proxy-path usage to the newsletter UI**

Apply these changes.

In `frontend/lib/api.ts`, add this import and export:

```ts
import { buildNewsletterProxyPath, loggedServerFetchJson } from '@/lib/newsletter-observability';
```

```ts
export function getNewsletterProxyPath(path: string) {
  return buildNewsletterProxyPath(path);
}
```

In `frontend/components/newsletter/newsletter-detail-client.tsx`, update the imports:

```ts
import { getNewsletterProxyPath } from '@/lib/api';
```

Replace the asset fetch line:

```ts
    void fetch(getNewsletterProxyPath(currentAsset.content_url))
```

Replace the PDF download `href`:

```tsx
              href={getNewsletterProxyPath(currentAsset.download_url)}
```

- [ ] **Step 4: Re-run the client component tests**

Run:

```powershell
npm run test -- tests/components/newsletter-detail-client.test.tsx
```

Expected:

- PASS.

- [ ] **Step 5: Commit the UI proxy-routing checkpoint**

Run:

```powershell
git add frontend/components/newsletter/newsletter-detail-client.tsx frontend/tests/components/newsletter-detail-client.test.tsx frontend/lib/api.ts
git commit -m "feat: route newsletter asset traffic through frontend proxy"
```

Expected:

- A commit exists containing the UI proxy-path switch and updated component tests.

---

### Task 4: Add Logged Server-Side Newsletter Fetches

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/newsletters/page.tsx`
- Modify: `frontend/app/newsletters/[slug]/page.tsx`
- Modify: `frontend/tests/lib/api.test.ts`

- [ ] **Step 1: Add failing tests for logged newsletter server fetches**

Replace `frontend/tests/lib/api.test.ts` with this content:

```ts
import { vi } from 'vitest';

import {
  fetchLatestNewsletter,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
  fetchNewsletters,
  getNewsletterProxyPath,
  getPublicNewsletters,
} from '@/lib/api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test('requests newsletters list from backend api', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
  const infoMock = vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.stubGlobal('fetch', fetchMock);

  await getPublicNewsletters();

  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(infoMock).toHaveBeenCalledWith(
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
});

test('requests latest newsletter from backend api with logging', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ id: 1 }),
  });
  const infoMock = vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.stubGlobal('fetch', fetchMock);

  await fetchLatestNewsletter();

  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters/latest',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(infoMock).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.latest -> /api/v1/newsletters/latest',
  );
});

test('builds frontend newsletter proxy paths from backend asset urls', () => {
  expect(getNewsletterProxyPath('/api/v1/newsletters/9/content/html')).toBe(
    '/api/frontend/newsletters/9/content/html',
  );
});
```

- [ ] **Step 2: Run the API tests to verify they fail first**

Run:

```powershell
npm run test -- tests/lib/api.test.ts
```

Expected:

- FAIL because the newsletter server fetches do not yet emit logging.

- [ ] **Step 3: Switch newsletter read helpers to the logged fetch helper**

In `frontend/lib/api.ts`, replace the four newsletter read helpers with this shape:

```ts
export async function fetchNewsletters(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : '';
  return loggedServerFetchJson<NewsletterItem[]>({
    label: 'newsletters.list',
    baseUrl: getServerApiBase(),
    path: `/api/v1/newsletters${query}`,
  });
}

export async function fetchNewsletterDetail(slug: string) {
  return loggedServerFetchJson<NewsletterDetail>({
    label: 'newsletters.detail',
    baseUrl: getServerApiBase(),
    path: `/api/v1/newsletters/${slug}`,
  });
}

export async function fetchLatestNewsletter() {
  return loggedServerFetchJson<NewsletterDetail>({
    label: 'newsletters.latest',
    baseUrl: getServerApiBase(),
    path: '/api/v1/newsletters/latest',
  });
}

export async function fetchNewsletterCalendar() {
  return loggedServerFetchJson<NewsletterCalendarEntry[]>({
    label: 'newsletters.calendar',
    baseUrl: getServerApiBase(),
    path: '/api/v1/newsletters/calendar',
  });
}
```

Still in `frontend/lib/api.ts`, add a helper for server-side asset content fetches:

```ts
export async function fetchNewsletterAssetContent(path: string) {
  return loggedServerFetchJson<{ asset_type: AssetType; content_html: string }>({
    label: 'newsletters.asset',
    baseUrl: getServerApiBase(),
    path,
  });
}
```

Update `frontend/app/newsletters/page.tsx`:

```ts
import {
  fetchLatestNewsletter,
  fetchNewsletterAssetContent,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
  fetchNewsletters,
} from '@/lib/api';
```

Replace the inline asset fetch block with:

```ts
        const payload = await fetchNewsletterAssetContent(asset.content_url);
        initialContentHtml = payload.content_html;
```

Update `frontend/app/newsletters/[slug]/page.tsx` similarly:

```ts
import { fetchNewsletterAssetContent, fetchNewsletterDetail } from '@/lib/api';
```

```ts
      const payload = await fetchNewsletterAssetContent(asset.content_url);
      initialContentHtml = payload.content_html;
```

- [ ] **Step 4: Run API, page, and type checks**

Run:

```powershell
npm run test -- tests/lib/api.test.ts tests/app/newsletters-page.test.tsx
npm run typecheck
```

Expected:

- PASS.

- [ ] **Step 5: Commit the logged server-fetch checkpoint**

Run:

```powershell
git add frontend/lib/api.ts frontend/app/newsletters/page.tsx frontend/app/newsletters/[slug]/page.tsx frontend/tests/lib/api.test.ts
git commit -m "feat: log newsletter server fetches in frontend runtime"
```

Expected:

- A commit exists containing the server-side newsletter logging changes and updated tests.

---

### Task 5: Final Verification

**Files:**
- No new files in this task.

- [ ] **Step 1: Run the full frontend test suite**

Run:

```powershell
npm run test
```

Expected:

- PASS.

- [ ] **Step 2: Run the frontend type check**

Run:

```powershell
npm run typecheck
```

Expected:

- PASS.

- [ ] **Step 3: Run the frontend dev server and observe the terminal**

Run:

```powershell
cd frontend
npm run dev
```

Expected:

- Startup logs still appear normally.
- Visiting `/newsletters` emits `console.info` lines such as:

```text
[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters
[FRONTEND][FETCH] newsletters.calendar -> /api/v1/newsletters/calendar
[FRONTEND][FETCH] newsletters.latest -> /api/v1/newsletters/latest
```

- Switching newsletter assets emits proxy-route log lines such as:

```text
[FRONTEND][API  ] GET /api/frontend/newsletters/38/content/html -> /api/v1/newsletters/38/content/html
[FRONTEND][API  ] 200 /api/v1/newsletters/38/content/html
```

- [ ] **Step 4: Verify the backend still receives the forwarded requests**

While the frontend server is running, browse the newsletter UI and confirm the backend terminal still shows the underlying `/api/v1/newsletters/...` requests.

Expected:

- Frontend terminal becomes more explanatory.
- Backend terminal still remains the source of truth for upstream API traffic.

- [ ] **Step 5: Commit the final verified state**

Run:

```powershell
git status --short
```

Expected:

- Only the planned frontend files are changed.
- The pre-existing launcher-file changes remain unstaged unless intentionally preserved in a separate branch workflow.

Then run:

```powershell
git add frontend/lib/newsletter-observability.ts frontend/app/api/frontend/newsletters/[...segments]/route.ts frontend/lib/api.ts frontend/app/newsletters/page.tsx frontend/app/newsletters/[slug]/page.tsx frontend/components/newsletter/newsletter-detail-client.tsx frontend/tests/lib/newsletter-observability.test.ts frontend/tests/lib/api.test.ts frontend/tests/components/newsletter-detail-client.test.tsx
git commit -m "feat: improve frontend newsletter request visibility"
```

Expected:

- A final feature commit exists for the logging/proxy work only.

---

## Final Verification Checklist

- [ ] `git status --short`
- [ ] `npm run test -- tests/lib/newsletter-observability.test.ts`
- [ ] `npm run test -- tests/components/newsletter-detail-client.test.tsx`
- [ ] `npm run test -- tests/lib/api.test.ts tests/app/newsletters-page.test.tsx`
- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] Manual check of `/newsletters`
- [ ] Manual check of newsletter asset switching
- [ ] Confirm frontend terminal shows `[FRONTEND][FETCH]` and `[FRONTEND][API  ]` lines
- [ ] Confirm backend terminal still shows upstream `/api/v1/newsletters/...` traffic
