# Newsletters Preview Page-Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/newsletters` so the route itself clearly renders a calendar panel, a format selector panel, and a dominant preview panel, making the page feel structurally like a preview workspace.

**Architecture:** Keep the current server-side newsletter data flow, but move the information hierarchy into the route shell. Add a dedicated route-owned client workspace component plus two presentational panel components (`NewsletterAssetSelector`, `NewsletterPreviewPanel`), and reduce `NewsletterDetailClient` to preview-only responsibilities. Keep PDF preview-first with fallback.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Testing Library

---

## File Structure

- `frontend/app/newsletters/page.tsx`
  - Server route.
  - Must explicitly render the route-level panel order.
- `frontend/components/newsletter/newsletters-workspace.tsx`
  - New client shell.
  - Owns selected asset state and composes selector + preview.
- `frontend/components/newsletter/newsletter-asset-selector.tsx`
  - New format-selection panel.
- `frontend/components/newsletter/newsletter-preview-panel.tsx`
  - New large preview surface wrapper.
- `frontend/components/newsletter/newsletter-detail-client.tsx`
  - Must become preview-only logic.
- `frontend/components/newsletter/newsletter-date-calendar.tsx`
  - Remains the top calendar panel.
- `frontend/tests/app/newsletters-layout.test.tsx`
  - New route-level structure test.
- `frontend/tests/app/newsletters-page.test.tsx`
  - Existing server data-flow test.
- `frontend/tests/components/newsletter-asset-selector.test.tsx`
  - New selector-panel test.
- `frontend/tests/components/newsletter-preview-panel.test.tsx`
  - New preview-panel test.
- `frontend/tests/components/newsletter-detail-client.test.tsx`
  - Update to preview-only contract.
- `frontend/tests/components/newsletter-date-calendar.test.tsx`
  - Preserve always-open coverage.

---

### Task 1: Add Route-Level Failing Tests

**Files:**
- Create: `frontend/tests/app/newsletters-layout.test.tsx`
- Create: `frontend/tests/components/newsletter-asset-selector.test.tsx`
- Create: `frontend/tests/components/newsletter-preview-panel.test.tsx`

- [ ] **Step 1: Create the failing route-shell test**

Create `frontend/tests/app/newsletters-layout.test.tsx`:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import NewslettersPage from '@/app/newsletters/page';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

const {
  fetchLatestNewsletterMock,
  fetchNewsletterAssetContentMock,
  fetchNewsletterCalendarMock,
  fetchNewsletterDetailMock,
  fetchNewslettersMock,
} = vi.hoisted(() => ({
  fetchLatestNewsletterMock: vi.fn(),
  fetchNewsletterAssetContentMock: vi.fn(),
  fetchNewsletterCalendarMock: vi.fn(),
  fetchNewsletterDetailMock: vi.fn(),
  fetchNewslettersMock: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchLatestNewsletter: fetchLatestNewsletterMock,
    fetchNewsletterAssetContent: fetchNewsletterAssetContentMock,
    fetchNewsletterCalendar: fetchNewsletterCalendarMock,
    fetchNewsletterDetail: fetchNewsletterDetailMock,
    fetchNewsletters: fetchNewslettersMock,
  };
});

const detail: NewsletterDetail = {
  id: 1,
  title: 'Newsletter 2026-03-30',
  slug: 'newsletter-20260330',
  description: 'Summary',
  source_type: 'html',
  tags: [],
  available_assets: [
    { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
    { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: false },
  ],
  default_asset_type: 'html',
  summary: 'Summary',
  category: null,
  thumbnail_url: null,
};

const items: NewsletterItem[] = [{
  id: 1,
  title: detail.title,
  slug: detail.slug,
  description: detail.description,
  source_type: detail.source_type,
  tags: [],
  available_assets: detail.available_assets,
  category: null,
}];

const calendarEntries: NewsletterCalendarEntry[] = [{
  date: '2026-03-30',
  slug: detail.slug,
  title: detail.title,
  source_type: detail.source_type,
}];

beforeEach(() => {
  fetchLatestNewsletterMock.mockResolvedValue(detail);
  fetchNewsletterAssetContentMock.mockResolvedValue({ asset_type: 'html', content_html: '<h1>hello</h1>' });
  fetchNewsletterCalendarMock.mockResolvedValue(calendarEntries);
  fetchNewsletterDetailMock.mockResolvedValue(detail);
  fetchNewslettersMock.mockResolvedValue(items);
});

afterEach(() => {
  vi.restoreAllMocks();
  fetchLatestNewsletterMock.mockReset();
  fetchNewsletterAssetContentMock.mockReset();
  fetchNewsletterCalendarMock.mockReset();
  fetchNewsletterDetailMock.mockReset();
  fetchNewslettersMock.mockReset();
});

test('renders calendar, format, and preview panels in order', async () => {
  render(await NewslettersPage({ searchParams: Promise.resolve({}) }));

  const calendarPanel = screen.getByTestId('newsletters-calendar-panel');
  const formatPanel = screen.getByTestId('newsletters-format-panel');
  const previewPanel = screen.getByTestId('newsletters-preview-panel');

  expect(calendarPanel.compareDocumentPosition(formatPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(formatPanel.compareDocumentPosition(previewPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
```

- [ ] **Step 2: Create the failing selector-panel test**

Create `frontend/tests/components/newsletter-asset-selector.test.tsx`:

```tsx
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import type { AssetType } from '@/lib/types';

test('renders explicit asset choices and reports selection changes', () => {
  const onChange = vi.fn();

  render(
    <NewsletterAssetSelector
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="markdown"
      onChange={onChange}
    />,
  );

  expect(screen.getByRole('heading', { name: '형식 선택' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));
  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});
```

- [ ] **Step 3: Create the failing preview-panel test**

Create `frontend/tests/components/newsletter-preview-panel.test.tsx`:

```tsx
import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';

test('renders a dominant preview panel with title and asset badge', () => {
  render(
    <NewsletterPreviewPanel title="Preview Title" selectedAsset="html">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByRole('heading', { name: 'Preview Title' })).toBeInTheDocument();
  expect(screen.getByText('HTML')).toBeInTheDocument();
  expect(screen.getByTestId('preview-body')).toBeInTheDocument();
});
```

- [ ] **Step 4: Run the new route-shell tests to verify RED**

Run:

```powershell
npm run test -- tests/app/newsletters-layout.test.tsx tests/components/newsletter-asset-selector.test.tsx tests/components/newsletter-preview-panel.test.tsx
```

Expected:

- FAIL because the route shell does not yet expose the three panels directly
- FAIL because the new selector/preview components do not exist yet

- [ ] **Step 5: Commit the failing checkpoint**

Run:

```powershell
git add frontend/tests/app/newsletters-layout.test.tsx frontend/tests/components/newsletter-asset-selector.test.tsx frontend/tests/components/newsletter-preview-panel.test.tsx
git commit -m "뉴스레터 페이지 셸 재구성 계약을 먼저 테스트로 고정한다"
```

---

### Task 2: Add Selector and Preview Panel Components

**Files:**
- Create: `frontend/components/newsletter/newsletter-asset-selector.tsx`
- Create: `frontend/components/newsletter/newsletter-preview-panel.tsx`

- [ ] **Step 1: Create `newsletter-asset-selector.tsx`**

Create `frontend/components/newsletter/newsletter-asset-selector.tsx`:

```tsx
import React from 'react';

import type { AssetType } from '@/lib/types';

export function NewsletterAssetSelector({
  availableAssetTypes,
  selectedAsset,
  onChange,
}: {
  availableAssetTypes: AssetType[];
  selectedAsset: AssetType;
  onChange: (asset: AssetType) => void;
}) {
  return (
    <section data-testid="newsletters-format-panel" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Format</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">형식 선택</h2>
      </div>
      <div className="flex flex-wrap gap-2">
        {availableAssetTypes.map((assetType) => {
          const active = assetType === selectedAsset;
          return (
            <button
              key={assetType}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(assetType)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
            >
              {assetType.toUpperCase()}
            </button>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Create `newsletter-preview-panel.tsx`**

Create `frontend/components/newsletter/newsletter-preview-panel.tsx`:

```tsx
import React from 'react';

import type { AssetType } from '@/lib/types';

export function NewsletterPreviewPanel({
  title,
  selectedAsset,
  children,
}: {
  title: string;
  selectedAsset: AssetType;
  children: React.ReactNode;
}) {
  return (
    <section data-testid="newsletters-preview-panel" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Preview</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">{title}</h2>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
          {selectedAsset.toUpperCase()}
        </span>
      </div>
      {children}
    </section>
  );
}
```

- [ ] **Step 3: Run the new component tests**

Run:

```powershell
npm run test -- tests/components/newsletter-asset-selector.test.tsx tests/components/newsletter-preview-panel.test.tsx
```

Expected:

- PASS.

- [ ] **Step 4: Commit the new panel components**

Run:

```powershell
git add frontend/components/newsletter/newsletter-asset-selector.tsx frontend/components/newsletter/newsletter-preview-panel.tsx frontend/tests/components/newsletter-asset-selector.test.tsx frontend/tests/components/newsletter-preview-panel.test.tsx
git commit -m "뉴스레터 선택 패널과 미리보기 패널을 분리한다"
```

---

### Task 3: Introduce a Route-Owned Workspace Shell

**Files:**
- Create: `frontend/components/newsletter/newsletters-workspace.tsx`
- Modify: `frontend/app/newsletters/page.tsx`

- [ ] **Step 1: Create `newsletters-workspace.tsx`**

Create `frontend/components/newsletter/newsletters-workspace.tsx`:

```tsx
'use client';

import React, { useMemo, useState } from 'react';

import type { NewsletterDetail } from '@/lib/types';
import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';
import { NewsletterDetailClient } from '@/components/newsletter/newsletter-detail-client';

export function NewslettersWorkspace({
  newsletter,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  initialContentHtml?: string;
}) {
  const availableAssetTypes = useMemo(
    () => newsletter.available_assets.map((asset) => asset.asset_type),
    [newsletter.available_assets],
  );
  const [selectedAsset, setSelectedAsset] = useState(newsletter.default_asset_type);

  return (
    <div className="space-y-6">
      <NewsletterAssetSelector
        availableAssetTypes={availableAssetTypes}
        selectedAsset={selectedAsset}
        onChange={setSelectedAsset}
      />

      <NewsletterPreviewPanel title={newsletter.title} selectedAsset={selectedAsset}>
        <NewsletterDetailClient
          key={`${newsletter.slug}:${selectedAsset}`}
          newsletter={newsletter}
          selectedAsset={selectedAsset}
          initialContentHtml={initialContentHtml}
        />
      </NewsletterPreviewPanel>
    </div>
  );
}
```

- [ ] **Step 2: Rebuild `page.tsx` to render the route-level shell**

Replace `frontend/app/newsletters/page.tsx`:

```tsx
import React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';
import { NewslettersWorkspace } from '@/components/newsletter/newsletters-workspace';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import {
  fetchLatestNewsletter,
  fetchNewsletterAssetContent,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
  fetchNewsletters,
} from '@/lib/api';
import type { NewsletterCalendarEntry, NewsletterDetail, NewsletterItem } from '@/lib/types';

export const dynamic = 'force-dynamic';

type SearchParams = {
  slug?: string;
};

export default async function NewslettersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let detail: NewsletterDetail | null = null;
  let calendarEntries: NewsletterCalendarEntry[] = [];
  let fallbackItems: NewsletterItem[] = [];
  let initialContentHtml = '';
  let errorMessage = '';

  try {
    [fallbackItems, calendarEntries] = await Promise.all([
      fetchNewsletters(),
      fetchNewsletterCalendar(),
    ]);

    if (params.slug) {
      detail = await fetchNewsletterDetail(params.slug);
    } else {
      detail = await fetchLatestNewsletter();
    }

    if (detail && detail.default_asset_type !== 'pdf') {
      const asset = detail.available_assets.find((item) => item.asset_type === detail.default_asset_type);
      if (asset) {
        try {
          const payload = await fetchNewsletterAssetContent(asset.content_url);
          initialContentHtml = payload.content_html;
        } catch {
          initialContentHtml = '';
        }
      }
    }
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : '뉴스레터 목록을 불러오지 못했습니다.';
  }

  return (
    <AppShell title="뉴스레터 서비스" contentClassName="max-w-[1600px]">
      {errorMessage ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          뉴스레터 목록을 불러오지 못했습니다. 백엔드 실행 상태와 포트(18437)를 확인해주세요.
          <div className="mt-1 text-xs text-red-600">{errorMessage}</div>
        </div>
      ) : null}

      {detail ? (
        <div className="space-y-6">
          <section data-testid="newsletters-calendar-panel">
            <NewsletterDateCalendar entries={calendarEntries} selectedSlug={detail.slug} />
          </section>

          <NewslettersWorkspace newsletter={detail} initialContentHtml={initialContentHtml} />
        </div>
      ) : (
        <NewsletterList items={fallbackItems} />
      )}
    </AppShell>
  );
}
```

- [ ] **Step 3: Run the route-level layout test**

Run:

```powershell
npm run test -- tests/app/newsletters-layout.test.tsx
```

Expected:

- PASS.

- [ ] **Step 4: Commit the route-owned shell**

Run:

```powershell
git add frontend/app/newsletters/page.tsx frontend/components/newsletter/newsletters-workspace.tsx frontend/tests/app/newsletters-layout.test.tsx
git commit -m "뉴스레터 페이지 셸을 세 패널 구조로 드러낸다"
```

---

### Task 4: Slim `NewsletterDetailClient` Down To Preview Logic

**Files:**
- Modify: `frontend/components/newsletter/newsletter-detail-client.tsx`
- Modify: `frontend/tests/components/newsletter-detail-client.test.tsx`

- [ ] **Step 1: Replace `newsletter-detail-client.tsx` with preview-only logic**

Replace `frontend/components/newsletter/newsletter-detail-client.tsx`:

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
  selectedAsset,
  initialContentHtml = '',
}: {
  newsletter: NewsletterDetail;
  selectedAsset: AssetType;
  initialContentHtml?: string;
}) {
  const [contentHtml, setContentHtml] = useState(initialContentHtml);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewState, setPdfPreviewState] = useState<PdfPreviewState>('idle');
  const currentAsset = useMemo(
    () => newsletter.available_assets.find((asset) => asset.asset_type === selectedAsset),
    [newsletter.available_assets, selectedAsset],
  );

  useEffect(() => {
    setContentHtml(initialContentHtml);
  }, [newsletter.slug, initialContentHtml]);

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
          if (typeof URL.revokeObjectURL === 'function') {
            URL.revokeObjectURL(objectUrl);
          }
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
      if (objectUrl && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [currentAsset, selectedAsset]);

  if (!currentAsset) {
    return <p className="text-sm text-slate-500">표시할 형식이 없습니다.</p>;
  }

  if (selectedAsset === 'html') {
    return <HtmlViewer title={newsletter.title} html={contentHtml} />;
  }

  if (selectedAsset === 'markdown') {
    return <MarkdownViewer html={contentHtml} />;
  }

  if (pdfPreviewState === 'loading') {
    return <p className="text-sm text-slate-500">PDF 미리보기를 불러오는 중입니다.</p>;
  }

  if (pdfPreviewState === 'success' && pdfPreviewUrl) {
    return <PdfViewer src={pdfPreviewUrl} />;
  }

  return (
    <section data-testid="newsletter-pdf-fallback" className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
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
  );
}
```

- [ ] **Step 2: Replace `newsletter-detail-client.test.tsx` with preview-only contract tests**

Replace `frontend/tests/components/newsletter-detail-client.test.tsx`:

```tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

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

test('renders html preview when html is selected', () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'HTML Preview',
        slug: 'html-preview',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'html', content_url: '/api/v1/newsletters/1/content/html', download_url: '/api/v1/newsletters/1/download/html', is_primary: true },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      selectedAsset="html"
      initialContentHtml="<h1>hello</h1>"
    />,
  );

  expect(screen.getByTitle('HTML Preview')).toHaveAttribute('srcdoc', '<h1>hello</h1>');
});

test('renders markdown preview when markdown is selected', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'Markdown Preview',
        slug: 'markdown-preview',
        description: 'desc',
        source_type: 'html',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'markdown', content_url: '/api/v1/newsletters/1/content/markdown', download_url: '/api/v1/newsletters/1/download/markdown', is_primary: true },
        ],
        summary: 'summary',
        default_asset_type: 'html',
      }}
      selectedAsset="markdown"
    />,
  );

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/markdown');
  });
});

test('shows inline pdf preview when pdf is selected', async () => {
  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Preview',
        slug: 'pdf-preview',
        description: 'desc',
        source_type: 'pdf',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: true },
        ],
        summary: 'summary',
        default_asset_type: 'pdf',
      }}
      selectedAsset="pdf"
    />,
  );

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith('/api/frontend/newsletters/1/content/pdf');
  });
  await waitFor(() => {
    expect(screen.getByTitle('PDF viewer')).toHaveAttribute('src', 'blob:newsletter-pdf-preview');
  });
});

test('shows fallback when pdf preview fails', async () => {
  vi.mocked(global.fetch).mockResolvedValueOnce({ ok: false, status: 500 } as Response);

  render(
    <NewsletterDetailClient
      newsletter={{
        id: 1,
        title: 'PDF Fallback',
        slug: 'pdf-fallback',
        description: 'desc',
        source_type: 'pdf',
        thumbnail_url: null,
        category: null,
        tags: [],
        available_assets: [
          { asset_type: 'pdf', content_url: '/api/v1/newsletters/1/content/pdf', download_url: '/api/v1/newsletters/1/download/pdf', is_primary: true },
        ],
        summary: 'summary',
        default_asset_type: 'pdf',
      }}
      selectedAsset="pdf"
    />,
  );

  await waitFor(() => {
    expect(screen.getByTestId('newsletter-pdf-fallback')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
npm run test -- tests/app/newsletters-layout.test.tsx tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-detail-client.test.tsx tests/components/newsletter-asset-selector.test.tsx tests/components/newsletter-preview-panel.test.tsx
```

Expected:

- PASS.

- [ ] **Step 4: Commit the preview-only refactor**

Run:

```powershell
git add frontend/components/newsletter/newsletter-detail-client.tsx frontend/tests/components/newsletter-detail-client.test.tsx
git commit -m "뉴스레터 미리보기 로직을 페이지 셸 아래의 전용 패널로 축소한다"
```

---

### Task 5: Final Verification and Existing Page-Test Alignment

**Files:**
- Modify: `frontend/tests/app/newsletters-page.test.tsx` (only if needed)

- [ ] **Step 1: Adjust the existing page data-flow test only if needed**

If `frontend/tests/app/newsletters-page.test.tsx` fails because the route now renders `NewslettersWorkspace`, update the mock contract minimally so it still verifies:

- calendar data flows
- selected newsletter data flows
- initial HTML still reaches the preview logic

Do not duplicate the new route-level structure test.

- [ ] **Step 2: Run final verification**

Run:

```powershell
npm run test
npm run typecheck
npm run build
```

Expected:

- all frontend tests pass
- typecheck passes
- build passes

- [ ] **Step 3: Commit a minimal page-test alignment only if needed**

Run only if `frontend/tests/app/newsletters-page.test.tsx` changed:

```powershell
git add frontend/tests/app/newsletters-page.test.tsx
git commit -m "뉴스레터 페이지 데이터 흐름 테스트를 새 셸 구조에 맞춰 정렬한다"
```

---

## Final Verification Checklist

- [ ] `git status --short`
- [ ] `npm run test -- tests/app/newsletters-layout.test.tsx tests/components/newsletter-asset-selector.test.tsx tests/components/newsletter-preview-panel.test.tsx tests/components/newsletter-date-calendar.test.tsx tests/components/newsletter-detail-client.test.tsx`
- [ ] `npm run test`
- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] Manual check of `/newsletters`
- [ ] Confirm the route shell visibly renders calendar panel, format selector panel, and preview panel
- [ ] Confirm PDF preview-first and fallback still work
- [ ] Confirm no `Newsletter_AI` run-history/file-index concepts leaked into the UI
