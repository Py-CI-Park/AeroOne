# Newsletters Preview Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `/newsletters` into a clearer calendar -> format selector -> preview layout, keep the calendar open by default, and make PDF use inline preview first with a download fallback.

**Architecture:** Reuse AeroOne’s existing newsletter primitives instead of importing `Newsletter_AI` report features. Keep `NewsletterDateCalendar` as the top control layer, refactor `NewsletterDetailClient` so it reads as a separate asset-selector panel plus a dedicated preview panel, and reuse the existing `PdfViewer` for successful inline PDF rendering while falling back to the current download-oriented panel when PDF preview cannot be loaded.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library

---

## File Structure

- `frontend/app/newsletters/page.tsx`
  - Public newsletters page.
  - Should remain the top-level data-fetching route and continue rendering calendar + selected newsletter experience.
  - May need only light structural touch if the client component fully owns the middle/bottom layout.
- `frontend/components/newsletter/newsletter-date-calendar.tsx`
  - Current top-level date selector.
  - Needs to become always-open and no longer depend on a “달력 열기/닫기” toggle for the main browsing flow.
- `frontend/components/newsletter/newsletter-detail-client.tsx`
  - Current combined asset-selector + preview component.
  - Needs to be restructured so the asset selector reads as a distinct middle panel and the preview reads as a distinct lower panel.
  - Will also own PDF preview state unless that becomes too tangled.
- `frontend/components/newsletter/pdf-viewer.tsx`
  - Existing iframe-based PDF viewer.
  - Should be reused rather than replaced if possible.
- `frontend/tests/components/newsletter-date-calendar.test.tsx`
  - Existing calendar behavior test.
  - Needs to change from “toggle to open” behavior to “visible by default” behavior.
- `frontend/tests/components/newsletter-detail-client.test.tsx`
  - Existing detail/asset switching coverage.
  - Needs to cover the new selector/panel structure and PDF preview/fallback behavior.
- `frontend/tests/app/newsletters-page.test.tsx`
  - Existing page-level test.
  - May only need light updates if mock expectations change, but should remain a guard that the page still renders the calendar and detail client.

## Notes Before Editing

- The current root branch is `initial-development`.
- This change is layout-focused; do not add `Newsletter_AI` run-history, file-browser, or report-session concepts.
- The existing `frontend/vitest.config.ts` already contains the JSX inject needed for page-component tests. Do not remove it as part of this work.

---

### Task 1: Lock the New Layout Contract With Failing Tests

**Files:**
- Modify: `frontend/tests/components/newsletter-date-calendar.test.tsx`
- Modify: `frontend/tests/components/newsletter-detail-client.test.tsx`

- [ ] **Step 1: Replace the calendar toggle test with an always-open test**

Replace `frontend/tests/components/newsletter-date-calendar.test.tsx` with this content:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';

it('shows the calendar grid by default without a dedicated open toggle', () => {
  render(
    <NewsletterDateCalendar
      selectedSlug="newsletter-20260326"
      entries={[
        { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
        { date: '2026-03-25', slug: 'newsletter-20260325', title: '2026-03-25 뉴스레터', source_type: 'html' },
      ]}
    />,
  );

  expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326',
  );
  expect(screen.getByRole('link', { name: /25/ })).toBeInTheDocument();
  expect(screen.getAllByRole('button')).toHaveLength(2);
  expect(screen.queryByRole('button', { name: /달력 열기|달력 닫기/ })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Extend the detail client test file with layout and PDF preview expectations**

Replace `frontend/tests/components/newsletter-detail-client.test.tsx` with this content:

```tsx
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';

beforeEach(() => {
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:newsletter-pdf-preview'),
    revokeObjectURL: vi.fn(),
  });

  vi.spyOn(global, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes('/content/pdf')) {
      return {
        ok: true,
        status: 200,
        blob: async () => new Blob(['pdf'], { type: 'application/pdf' }),
      } as Response;
    }

    return {
      ok: true,
      status: 200,
      json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
    } as Response;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test('renders an explicit asset selector panel and preview panel', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Layout Newsletter',
        slug: 'layout-newsletter',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
          { asset_type: 'markdown', content_url: '/api/v1/newsletters/1/content/markdown', download_url: '/api/v1/newsletters/1/download/markdown', is_primary: false },
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  expect(screen.getByTestId('newsletter-asset-selector')).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-preview-panel')).toBeInTheDocument();
});

test('shows inline pdf preview when pdf tab is selected', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Preview',
        slug: 'pdf-preview',
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

  await waitFor(() => {
    expect(screen.getByTitle('PDF viewer')).toHaveAttribute('src', 'blob:newsletter-pdf-preview');
  });
});

test('shows a download fallback when pdf preview fails', async () => {
  vi.mocked(global.fetch).mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/content/pdf')) {
      return { ok: false, status: 500 } as Response;
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ asset_type: 'html', content_html: '<h1>hello</h1>' }),
    } as Response;
  });

  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Fallback',
        slug: 'pdf-fallback',
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

  await waitFor(() => {
    expect(screen.getByTestId('newsletter-pdf-fallback')).toBeInTheDocument();
  });

  expect(screen.getByRole('link', { name: /PDF/ })).toHaveAttribute(
    'href',
    '/api/frontend/newsletters/1/download/pdf',
  );
});
```

- [ ] **Step 3: Run the focused tests and verify they fail first**

Run:

```powershell
npm run test -- tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-detail-client.test.tsx
```

Expected:

- FAIL because the calendar is still toggle-based
- FAIL because the detail client does not yet render explicit selector/preview panels
- FAIL because PDF is still download-oriented rather than preview-first

- [ ] **Step 4: Commit the failing-test checkpoint**

Run:

```powershell
git add frontend/tests/components/newsletter-date-calendar.test.tsx frontend/tests/components/newsletter-detail-client.test.tsx
git commit -m "뉴스레터 미리보기 레이아웃 회귀 테스트를 먼저 고정한다"
```

Expected:

- A commit exists containing only the new failing test expectations.

---

### Task 2: Make the Calendar Always Open and Add PDF Preview-First Behavior

**Files:**
- Modify: `frontend/components/newsletter/newsletter-date-calendar.tsx`
- Modify: `frontend/components/newsletter/newsletter-detail-client.tsx`

- [ ] **Step 1: Remove the calendar open/close toggle and render the grid by default**

Update `frontend/components/newsletter/newsletter-date-calendar.tsx` with these changes:

1. Remove:

```tsx
const [isOpen, setIsOpen] = useState(false);
```

2. Remove the dedicated open/close button block:

```tsx
<button
  type="button"
  onClick={() => setIsOpen((current) => !current)}
  className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
>
  <span aria-hidden="true">📟</span>
  {isOpen ? '달력 닫기' : '달력 열기'}
</button>
```

3. Replace the conditional calendar rendering:

```tsx
{isOpen ? (
  <div className="mt-4">
    ...
  </div>
) : null}
```

with an unconditional block:

```tsx
<div className="mt-4">
  ...
</div>
```

- [ ] **Step 2: Refactor the detail client into explicit selector + preview sections**

Replace `frontend/components/newsletter/newsletter-detail-client.tsx` with this content:

```tsx
'use client';

import React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getNewsletterProxyPath } from '@/lib/api';
import type { AssetType, NewsletterDetail } from '@/lib/types';
import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { MarkdownViewer } from '@/components/newsletter/markdown-viewer';
import { PdfViewer } from '@/components/newsletter/pdf-viewer';

type HtmlResponse = {
  asset_type: AssetType;
  content_html: string;
};

type PdfPreviewState = 'idle' | 'loading' | 'success' | 'error';

export function NewsletterDetailClient({
  newsletter,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
}) {
  const [selectedAsset, setSelectedAsset] = useState<AssetType>(newsletter.default_asset_type);
  const [contentHtml, setContentHtml] = useState(initialContentHtml);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewState, setPdfPreviewState] = useState<PdfPreviewState>('idle');
  const currentAsset = useMemo(
    () => newsletter.available_assets.find((asset) => asset.asset_type === selectedAsset),
    [newsletter.available_assets, selectedAsset],
  );

  useEffect(() => {
    setSelectedAsset(newsletter.default_asset_type);
    setContentHtml(initialContentHtml);
  }, [newsletter.slug, newsletter.default_asset_type, initialContentHtml]);

  useEffect(() => {
    if (!currentAsset || selectedAsset === 'pdf') {
      return;
    }
    if (selectedAsset === newsletter.default_asset_type && initialContentHtml) {
      return;
    }

    const assetPath = getNewsletterProxyPath(currentAsset.content_url);

    void (async () => {
      try {
        const response = await fetch(assetPath);
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const payload = (await response.json()) as HtmlResponse;
        setContentHtml(payload.content_html);
      } catch (error) {
        console.error(`[FRONTEND][FETCH] Failed to load newsletter asset ${assetPath}`, error);
      }
    })();
  }, [currentAsset, initialContentHtml, newsletter.default_asset_type, selectedAsset]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function loadPdfPreview() {
      if (!currentAsset || selectedAsset !== 'pdf') {
        setPdfPreviewState('idle');
        setPdfPreviewUrl(null);
        return;
      }

      const pdfPath = getNewsletterProxyPath(currentAsset.content_url);

      try {
        setPdfPreviewState('loading');
        const response = await fetch(pdfPath);
        if (!response.ok) {
          throw new Error(`Request failed: ${response.status}`);
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setPdfPreviewUrl(objectUrl);
        setPdfPreviewState('success');
      } catch (error) {
        if (cancelled) {
          return;
        }
        setPdfPreviewUrl(null);
        setPdfPreviewState('error');
        console.error(`[FRONTEND][FETCH] Failed to preview newsletter PDF ${pdfPath}`, error);
      }
    }

    void loadPdfPreview();

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [currentAsset, selectedAsset]);

  return (
    <section className="space-y-4">
      <section
        data-testid="newsletter-asset-selector"
        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="mb-3">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Format</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">형식 선택</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {newsletter.available_assets.map((asset) => (
            <button
              key={asset.asset_type}
              type="button"
              onClick={() => setSelectedAsset(asset.asset_type)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                selectedAsset === asset.asset_type ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {asset.asset_type.toUpperCase()}
            </button>
          ))}
        </div>
      </section>

      <section
        data-testid="newsletter-preview-panel"
        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Preview</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">{newsletter.title}</h2>
          </div>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
            {selectedAsset.toUpperCase()}
          </span>
        </div>

        {selectedAsset === 'html' ? <HtmlViewer title={newsletter.title} html={contentHtml} /> : null}
        {selectedAsset === 'markdown' ? <MarkdownViewer html={contentHtml} /> : null}
        {selectedAsset === 'pdf' && currentAsset ? (
          pdfPreviewState === 'loading' ? (
            <p className="text-sm text-slate-500">PDF 미리보기를 불러오는 중입니다.</p>
          ) : pdfPreviewState === 'success' && pdfPreviewUrl ? (
            <PdfViewer src={pdfPreviewUrl} />
          ) : (
            <section
              data-testid="newsletter-pdf-fallback"
              className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm"
            >
              <div className="mx-auto max-w-xl">
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">PDF</p>
                <h2 className="mt-3 text-2xl font-semibold text-slate-900">PDF 미리보기를 열 수 없습니다.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  브라우저 환경에 따라 PDF 미리보기가 제한될 수 있습니다. 아래 버튼으로 파일을 직접 내려받아 확인하세요.
                </p>
                <a
                  href={getNewsletterProxyPath(currentAsset.download_url)}
                  className="mt-6 inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-medium text-white"
                >
                  PDF 다운로드
                </a>
              </div>
            </section>
          )
        ) : null}
      </section>
    </section>
  );
}
```

- [ ] **Step 3: Re-run the focused tests**

Run:

```powershell
npm run test -- tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-detail-client.test.tsx
```

Expected:

- PASS.

- [ ] **Step 4: Commit the component/layout implementation**

Run:

```powershell
git add frontend/components/newsletter/newsletter-date-calendar.tsx frontend/components/newsletter/newsletter-detail-client.tsx frontend/tests/components/newsletter-date-calendar.test.tsx frontend/tests/components/newsletter-detail-client.test.tsx
git commit -m "뉴스레터 화면을 달력-형식-미리보기 구조로 재구성한다"
```

Expected:

- A commit exists containing the calendar open-by-default change, the selector/preview restructuring, and the PDF preview-first behavior.

---

### Task 3: Final Verification and Page-Level Guarding

**Files:**
- Modify: `frontend/tests/app/newsletters-page.test.tsx` (only if needed to keep current page-level expectations coherent)

- [ ] **Step 1: Update the page test only if the current mocks need to reflect the new preview-first structure**

If `frontend/tests/app/newsletters-page.test.tsx` breaks because the detail client mock contract changes, update only the minimum needed to keep the page-level test focused on:

- calendar still renders
- detail client still renders
- initial HTML still flows through when available

Do not turn the page test into a duplicate of the component layout tests.

- [ ] **Step 2: Run the full frontend test suite**

Run:

```powershell
npm run test
```

Expected:

- PASS for the full frontend test suite.

- [ ] **Step 3: Run frontend typecheck**

Run:

```powershell
npm run typecheck
```

Expected:

- PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm run build
```

Expected:

- PASS.

- [ ] **Step 5: Commit any minimal page-test adjustment only if one was needed**

If `frontend/tests/app/newsletters-page.test.tsx` required a real change, run:

```powershell
git add frontend/tests/app/newsletters-page.test.tsx
git commit -m "뉴스레터 미리보기 레이아웃 변경에 맞춰 페이지 테스트를 정렬한다"
```

If no page-test update was needed, do not create a new commit here.

---

## Final Verification Checklist

- [ ] `git status --short`
- [ ] `npm run test -- tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-detail-client.test.tsx`
- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] Manual check of `/newsletters`
- [ ] Confirm calendar is visible by default
- [ ] Confirm asset selector is a distinct middle panel
- [ ] Confirm HTML / Markdown / PDF each map to the lower preview area
- [ ] Confirm PDF shows inline preview when available and download fallback when not
