import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

import {
  HtmlViewer,
  applyViewerFitStyles,
  applyContentModeSidebarScrollStyles,
  expandNewsletterArticles,
  isElementFromDocument,
  normalizeHtmlForStandaloneWindow,
  normalizeSameDocumentHashLinks,
  clampWindowScrollTop,
  getScrollableWheelAncestor,
  resolveSameDocumentHashTarget,
  VIEWPORT_IFRAME_STYLE,
} from '@/components/newsletter/html-viewer';

it('renders sandboxed iframe that allows scripts for trusted newsletter content', () => {
  render(<HtmlViewer title="sample" html="<h1>hello</h1>" />);
  const iframe = screen.getByTitle('sample');
  // Newsletter_AI 산출 HTML 은 <script> 로 본문을 주입하므로 allow-scripts 필요.
  // 콘텐츠는 운영자 자체 파이프라인 산출물(신뢰 가능)이라 sandbox 에 허용.
  expect(iframe).toHaveAttribute('sandbox', 'allow-same-origin allow-scripts');
  expect(iframe.getAttribute('sandbox')).toContain('allow-scripts');
  // content(기본) 모드: 바깥 페이지가 스크롤하므로 iframe 자체 스크롤은 끈다.
  expect(iframe).toHaveAttribute('scrolling', 'no');
  // 토글 미요청 시 토글 버튼은 없다(뉴스레터 읽기 화면 외형 불변).
  expect(screen.queryByTestId('html-viewer-fit-toggle')).toBeNull();
});

it('viewport fit gives the iframe its own scroll (no scrolling=no) so a doc TOC stays fixed', () => {
  // 문서/카탈로그/NSA 는 자체 목차(position:fixed/sticky, 100vh)를 가진 HTML 이라
  // iframe 에 자체 viewport(내부 스크롤)가 있어야 단독 실행처럼 목차가 고정된다.
  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);
  const iframe = screen.getByTitle('doc');
  // viewport 모드: 내부 스크롤이 생기도록 scrolling 을 명시적으로 켠다.
  expect(iframe).toHaveAttribute('scrolling', 'yes');
  expect(iframe.getAttribute('style') ?? '').toContain('calc(100dvh - 96px)');
  expect(VIEWPORT_IFRAME_STYLE.minHeight).toBeGreaterThanOrEqual(640);
});
it('viewport fit does not lock the parent page scroll', async () => {
  const originalOverflow = document.body.style.overflow;
  document.body.style.overflow = 'auto';

  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);

  await waitFor(() => expect(screen.getByTitle('doc')).toBeInTheDocument());
  expect(document.body.style.overflow).toBe('auto');

  document.body.style.overflow = originalOverflow;
});

it('resolves same-page hash links including absolute app URLs', () => {
  expect(resolveSameDocumentHashTarget('#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('/nsa#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('http://localhost:29501/nsa#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('/documents#summary', 'http://localhost:29501/nsa')).toBeNull();
  expect(resolveSameDocumentHashTarget('https://example.com/nsa#summary', 'http://localhost:29501/nsa')).toBeNull();
});

it('recognizes iframe-document elements as valid click targets', () => {
  const iframe = document.createElement('iframe');
  document.body.appendChild(iframe);
  const iframeDoc = iframe.contentDocument;
  if (!iframeDoc) {
    throw new Error('iframe document unavailable');
  }
  iframeDoc.body.innerHTML = '<a href="#summary">Summary</a>';

  const iframeAnchor = iframeDoc.querySelector('a');
  expect(isElementFromDocument(iframeAnchor, iframeDoc)).toBe(true);
  expect(iframeAnchor instanceof Element).toBe(false);

  iframe.remove();
});

it('keeps same-document hash links in-place instead of target blank', () => {
  const doc = new DOMParser().parseFromString(
    `
    <a href="#summary" target="_blank" rel="noopener noreferrer">Summary</a>
    <h2 id="summary">Summary</h2>
    <a href="https://example.com" target="_blank" rel="noopener noreferrer">External</a>
  `,
    'text/html',
  );

  const anchors = doc.querySelectorAll('a');

  expect(normalizeSameDocumentHashLinks(doc, 'http://localhost:29501/documents')).toBe(1);
  expect(anchors[0].getAttribute('target')).toBeNull();
  expect(anchors[0].getAttribute('rel')).toBeNull();
  expect(anchors[1].getAttribute('target')).toBe('_blank');
});

it('normalizes raw HTML opened in a standalone blob window', () => {
  const normalized = normalizeHtmlForStandaloneWindow(
    '<html><body><a href="#toc" target="_blank" rel="noopener noreferrer">TOC</a><h2 id="toc">TOC</h2></body></html>',
  );

  expect(normalized).toContain('href="#toc"');
  expect(normalized).not.toContain('target="_blank"');
  expect(normalized).not.toContain('noopener noreferrer');
});
it('injects responsive content-fit CSS to avoid sidebar and table width overlap', () => {
  const doc = document.implementation.createHTMLDocument('doc');
  doc.body.innerHTML = `
    <nav class="sidebar"></nav>
    <div class="main"><div class="main-inner"><table><tbody><tr><td>wide</td></tr></tbody></table></div></div>
  `;

  applyViewerFitStyles(doc, 'content');

  const style = doc.getElementById('aeroone-viewer-fit-style');
  expect(doc.body.getAttribute('data-aeroone-viewer-fit')).toBe('content');
  expect(style?.textContent).toContain('@media (max-width: 1180px)');
  expect(style?.textContent).toContain('margin-left: 0 !important');
  expect(style?.textContent).toContain('overflow-x: auto !important');
  expect(style?.textContent).toContain('max-height: var(--aeroone-viewer-sidebar-max-height, 720px) !important');
  expect(style?.textContent).toContain('overflow-y: auto !important');
  expect(style?.textContent).toContain('overscroll-behavior: contain !important');

  applyViewerFitStyles(doc, 'viewport');
  expect(doc.body.getAttribute('data-aeroone-viewer-fit')).toBe('viewport');
});

it('pins content-mode sidebar scroll height to the parent viewport, not iframe 100vh', () => {
  const sidebar = document.createElement('aside');

  expect(applyContentModeSidebarScrollStyles(sidebar, 900)).toBe('816px');
  expect(sidebar.style.maxHeight).toBe('816px');
  expect(sidebar.style.overflowY).toBe('auto');
  expect(sidebar.style.getPropertyValue('overscroll-behavior')).toBe('contain');
  expect(sidebar.style.getPropertyValue('scrollbar-gutter')).toBe('stable');

  expect(applyContentModeSidebarScrollStyles(sidebar, 260)).toBe('240px');
});

it('detects iframe descendants that can consume vertical or horizontal wheel input', () => {
  const doc = document.implementation.createHTMLDocument('doc');
  doc.body.innerHTML = `
    <aside class="sidebar" style="overflow-y: auto"><button id="toc">TOC</button></aside>
    <div class="table-wrap" style="overflow-x: auto"><button id="cell">Cell</button></div>
  `;
  const sidebar = doc.querySelector('.sidebar') as HTMLElement;
  const tocButton = doc.getElementById('toc')!;
  Object.defineProperty(sidebar, 'scrollTop', { configurable: true, value: 10 });
  Object.defineProperty(sidebar, 'clientHeight', { configurable: true, value: 100 });
  Object.defineProperty(sidebar, 'scrollHeight', { configurable: true, value: 300 });

  const tableWrap = doc.querySelector('.table-wrap') as HTMLElement;
  const tableButton = doc.getElementById('cell')!;
  Object.defineProperty(tableWrap, 'scrollLeft', { configurable: true, value: 0 });
  Object.defineProperty(tableWrap, 'clientWidth', { configurable: true, value: 100 });
  Object.defineProperty(tableWrap, 'scrollWidth', { configurable: true, value: 300 });

  expect(getScrollableWheelAncestor(tocButton, doc, 0, -30)).toBe(sidebar);
  expect(getScrollableWheelAncestor(tableButton, doc, 24, 0)).toBe(tableWrap);
  expect(getScrollableWheelAncestor(tableButton, doc, 0, 24, true)).toBe(tableWrap);
  expect(getScrollableWheelAncestor(doc.body, doc, 0, 30)).toBeNull();
});

it('clamps parent hash-scroll targets to the document bounds', () => {
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 });
  Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, value: 2000 });
  Object.defineProperty(document.body, 'scrollHeight', { configurable: true, value: 1800 });

  expect(clampWindowScrollTop(-50)).toBe(0);
  expect(clampWindowScrollTop(1200)).toBe(1200);
  expect(clampWindowScrollTop(5000)).toBe(1400);
});

it('fit toggle switches between viewport(목차 고정) and content(전체 높이)', () => {
  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);
  const toggle = screen.getByTestId('html-viewer-fit-toggle');
  const iframe = screen.getByTitle('doc');

  // 시작은 viewport — 버튼은 content 로 가는 라벨을 보여준다.
  expect(toggle).toHaveTextContent('전체 높이로 보기');
  expect(iframe).toHaveAttribute('scrolling', 'yes');

  // content 로 전환 → 콘텐츠 높이 + scrolling="no".
  fireEvent.click(toggle);
  expect(toggle).toHaveTextContent('창 높이로 보기');
  expect(screen.getByTitle('doc')).toHaveAttribute('scrolling', 'no');

  // 다시 viewport 로 전환.
  fireEvent.click(toggle);
  expect(toggle).toHaveTextContent('전체 높이로 보기');
  expect(screen.getByTitle('doc')).toHaveAttribute('scrolling', 'yes');
});
it('renders optional HTML download next to the fit toggle with text only', () => {
  render(
    <HtmlViewer
      title="doc"
      html="<h1>hi</h1>"
      fit="viewport"
      showFitToggle
      downloadHref="/api/frontend/collections/document/download/html?path=doc.html"
    />,
  );

  const controls = screen.getByTestId('html-viewer-fit-toggle').parentElement;
  const download = screen.getByTestId('html-viewer-download');

  expect(download).toHaveAttribute('href', '/api/frontend/collections/document/download/html?path=doc.html');
  expect(download).toHaveTextContent('HTML 다운로드');
  expect(download.querySelector('svg')).toBeNull();
  expect(controls?.children[2]).toBe(screen.getByTestId('html-viewer-fit-toggle'));
  expect(controls?.children[3]).toBe(download);
});

it('opens the raw HTML in a blob URL instead of navigating to the gated app route', () => {
  const originalCreateObjectURL = window.URL.createObjectURL;
  const originalRevokeObjectURL = window.URL.revokeObjectURL;
  const openSpy = vi.spyOn(window, 'open').mockReturnValue({} as Window);
  const createObjectURLMock = vi.fn(() => 'blob:http://localhost:29501/raw-html');
  const revokeObjectURLMock = vi.fn();
  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: createObjectURLMock });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURLMock });

  render(<HtmlViewer title="doc" html="<h1>raw</h1>" />);
  fireEvent.click(screen.getByRole('button', { name: '새 창으로 열기' }));

  expect(createObjectURLMock).toHaveBeenCalled();
  expect(openSpy).toHaveBeenCalledWith('blob:http://localhost:29501/raw-html', '_blank');

  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: originalCreateObjectURL });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: originalRevokeObjectURL });
});

function buildArticleDoc(): Document {
  const doc = document.implementation.createHTMLDocument('news');
  doc.body.innerHTML = `
    <section data-article>
      <header class="article-head" data-accordion-trigger><button class="a-toggle"></button></header>
      <div class="article-body">body 1</div>
    </section>
    <section data-article>
      <header class="article-head" data-accordion-trigger><button class="a-toggle"></button></header>
      <div class="article-body">body 2</div>
    </section>
  `;
  return doc;
}

it('opens every article by default and marks them so they are only opened once', () => {
  const doc = buildArticleDoc();

  const opened = expandNewsletterArticles(doc);

  expect(opened).toBe(2);
  const articles = Array.from(doc.querySelectorAll('[data-article]'));
  for (const article of articles) {
    expect(article.getAttribute('data-open')).toBe('true');
    expect(article.getAttribute('data-aeroone-defopen')).toBe('1');
    expect(article.querySelector('[data-accordion-trigger]')?.getAttribute('aria-expanded')).toBe('true');
  }
});

it('does not re-open an article the user has collapsed (idempotent per article)', () => {
  const doc = buildArticleDoc();
  expandNewsletterArticles(doc);

  // 사용자가 첫 기사를 접음 — 기존 아코디언 토글이 data-open 을 뒤집은 상황.
  const [first] = Array.from(doc.querySelectorAll('[data-article]'));
  first.setAttribute('data-open', 'false');

  // 폴링/Observer 가 다시 호출돼도 마커가 있는 기사는 건드리지 않는다.
  const openedAgain = expandNewsletterArticles(doc);

  expect(openedAgain).toBe(0);
  expect(first.getAttribute('data-open')).toBe('false');
});

it('only expands newly rendered articles on later passes', () => {
  const doc = buildArticleDoc();
  expandNewsletterArticles(doc);

  // JS 가 기사 카드를 뒤늦게 추가 렌더한 경우.
  const late = doc.createElement('section');
  late.setAttribute('data-article', '');
  late.innerHTML = '<header data-accordion-trigger></header><div class="article-body">late</div>';
  doc.body.appendChild(late);

  const opened = expandNewsletterArticles(doc);

  expect(opened).toBe(1);
  expect(late.getAttribute('data-open')).toBe('true');
});

// --- D1-A: content-fit 높이 동기화(스크롤 점프 방지 / 폴링 조기 종료) ---

function getContentDoc(iframe: HTMLIFrameElement): Document {
  const doc = iframe.contentDocument ?? iframe.contentWindow?.document ?? null;
  if (!doc) {
    throw new Error('iframe document unavailable');
  }
  return doc;
}

// jsdom 은 실제 레이아웃이 없어 scrollHeight 가 0 이다. measureContentHeight 가
// 읽는 body/documentElement 의 scroll/offset 높이를 직접 정의해 측정값을 제어한다.
function setMeasuredHeight(iframe: HTMLIFrameElement, px: number) {
  const doc = getContentDoc(iframe);
  for (const el of [doc.documentElement, doc.body]) {
    if (!el) continue;
    Object.defineProperty(el, 'scrollHeight', { configurable: true, value: px });
    Object.defineProperty(el, 'offsetHeight', { configurable: true, value: px });
  }
}

it('content-fit skips the height write when the measured delta is within tolerance (no churn, no scroll yank)', () => {
  const scrollToSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  render(<HtmlViewer title="news" html="<h1>hi</h1>" />);
  const iframe = screen.getByTitle('news') as HTMLIFrameElement;

  // 초기 높이 상태 1800px. 측정값을 1805 로 둬도 1800 기준 5px 차(허용오차 8 이내).
  setMeasuredHeight(iframe, 1805);
  act(() => {
    fireEvent.load(iframe);
  });

  // setHeight 가 호출되지 않아 높이는 1800 그대로이고, 스크롤 보정도 일어나지 않는다.
  expect(iframe.getAttribute('style') ?? '').toContain('height: 1800px');
  expect(scrollToSpy).not.toHaveBeenCalled();

  scrollToSpy.mockRestore();
});

it('content-fit preserves window.scrollY across a real height write (restores after the reflow)', () => {
  const scrollToSpy = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  // syncHeight 의 requestAnimationFrame 콜백을 동기로 실행시켜 복원 호출을 검증한다.
  const rafSpy = vi
    .spyOn(window, 'requestAnimationFrame')
    .mockImplementation((cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });

  render(<HtmlViewer title="news" html="<h1>hi</h1>" />);
  const iframe = screen.getByTitle('news') as HTMLIFrameElement;

  // 사용자가 640px 스크롤한 상태에서 콘텐츠 높이가 실제로 크게 늘어난다.
  Object.defineProperty(window, 'scrollY', { configurable: true, value: 640 });
  Object.defineProperty(window, 'scrollX', { configurable: true, value: 0 });
  setMeasuredHeight(iframe, 5200);
  act(() => {
    fireEvent.load(iframe);
  });

  // 높이 쓰기 직전 위치(0, 640)로 되돌린다 → 바깥 페이지가 맨 위로 튀지 않는다.
  expect(scrollToSpy).toHaveBeenCalledWith(0, 640);

  rafSpy.mockRestore();
  scrollToSpy.mockRestore();
});

it('content-fit poll early-exits after stable measurements settle (timer cleared)', () => {
  // 실제 타이머/페이크 타이머의 teardown 레이스를 피하려고 setInterval/clearInterval 을
  // 직접 스텁한다. 300ms 추적 폴링 콜백을 손으로 호출해 조기 종료(clearInterval)를 검증.
  const realSetInterval = window.setInterval;
  const realClearInterval = window.clearInterval;
  const trackingCbs: Array<{ id: number; cb: () => void }> = [];
  let nextId = 1;
  const clearIntervalMock = vi.fn();
  // @ts-expect-error 테스트 스텁
  window.setInterval = (cb: () => void, delay?: number) => {
    const id = nextId++;
    if (delay === 300) {
      trackingCbs.push({ id, cb });
    }
    return id;
  };
  window.clearInterval = clearIntervalMock;

  try {
    render(<HtmlViewer title="news" html="<h1>hi</h1>" />);
    const iframe = screen.getByTitle('news') as HTMLIFrameElement;
    act(() => {
      fireEvent.load(iframe);
    });

    expect(trackingCbs.length).toBeGreaterThan(0);
    // 활성 폴링은 가장 최근에 생성된 300ms 인터벌이다(timerRef.current).
    const tracking = trackingCbs[trackingCbs.length - 1];

    // jsdom 측정값은 항상 1800(안정)이라 연속 허용오차 이내 → POLL_STABLE_LIMIT 회 후 종료.
    act(() => {
      for (let i = 0; i < 6; i += 1) {
        tracking.cb();
      }
    });

    expect(clearIntervalMock).toHaveBeenCalledWith(tracking.id);
  } finally {
    window.setInterval = realSetInterval;
    window.clearInterval = realClearInterval;
  }
});
