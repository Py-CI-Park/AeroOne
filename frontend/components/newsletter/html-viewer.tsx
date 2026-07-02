import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/ui/icons';

// Newsletter_AI 산출 HTML 의 기사 카드는 [data-article] 아코디언으로 렌더되며,
// 기본값은 data-open 미설정(= .article-body { display:none } 으로 접힘)이다.
// 운영자는 "오늘의 기사" 진입 즉시 본문이 보이길 원하므로, iframe 로드 후 각
// 기사를 한 번만 data-open="true" 로 펼친다. 마커(data-aeroone-defopen)를 남겨
// "기본 펼침" 은 기사당 최초 1회만 적용하고, 이후 사용자가 헤더를 눌러 접는
// 기존 토글(initAccordion 이 data-open 을 뒤집음)은 그대로 동작하게 둔다.
export function expandNewsletterArticles(doc: Document): number {
  const articles = doc.querySelectorAll('[data-article]:not([data-aeroone-defopen])');
  articles.forEach((article) => {
    article.setAttribute('data-open', 'true');
    article.setAttribute('data-aeroone-defopen', '1');
    article.querySelector('[data-accordion-trigger]')?.setAttribute('aria-expanded', 'true');
  });
  return articles.length;
}

function safeDecodeURIComponent(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function resolveSameDocumentHashTarget(href: string | null, currentHref: string): string | null {
  if (!href) {
    return null;
  }
  if (href.startsWith('#')) {
    const target = safeDecodeURIComponent(href.substring(1));
    return target || null;
  }
  try {
    const url = new URL(href, currentHref);
    const current = new URL(currentHref);
    if (!url.hash || url.origin !== current.origin || url.pathname !== current.pathname) {
      return null;
    }
    const target = safeDecodeURIComponent(url.hash.substring(1));
    return target || null;
  } catch {
    return null;
  }
}
export function isElementFromDocument(target: EventTarget | null, doc: Document): target is Element {
  const elementCtor = doc.defaultView?.Element;
  return Boolean(elementCtor && target instanceof elementCtor);
}

export function normalizeSameDocumentHashLinks(doc: Document, currentHref: string): number {
  let normalized = 0;
  doc.querySelectorAll<HTMLAnchorElement>('a[href]').forEach((anchor) => {
    const targetId = resolveSameDocumentHashTarget(anchor.getAttribute('href'), currentHref);
    if (!targetId || !doc.getElementById(targetId)) {
      return;
    }
    anchor.removeAttribute('target');
    const rel = anchor.getAttribute('rel');
    if (rel === 'noopener noreferrer') {
      anchor.removeAttribute('rel');
    }
    normalized += 1;
  });
  return normalized;
}

export function normalizeHtmlForStandaloneWindow(html: string): string {
  if (typeof DOMParser === 'undefined') {
    return html;
  }

  const doc = new DOMParser().parseFromString(html, 'text/html');
  normalizeSameDocumentHashLinks(doc, doc.location?.href ?? 'about:blank');
  return `<!DOCTYPE html>\n${doc.documentElement.outerHTML}`;
}
const VIEWER_FIT_STYLE_ID = 'aeroone-viewer-fit-style';
export const VIEWPORT_IFRAME_STYLE: React.CSSProperties = {
  height: 'calc(100dvh - 96px)',
  minHeight: 680,
};
export const CONTENT_MODE_SIDEBAR_MIN_HEIGHT = 240;
export const CONTENT_MODE_SIDEBAR_VERTICAL_OFFSET = 84;
const VIEWER_FIT_STYLE = `
body[data-aeroone-viewer-fit="content"] {
  overflow-x: hidden !important;
}

body[data-aeroone-viewer-fit="content"] .main,
body[data-aeroone-viewer-fit="content"] .main-inner {
  box-sizing: border-box !important;
  max-width: 100% !important;
}

body[data-aeroone-viewer-fit="content"] table {
  display: block !important;
  max-width: 100% !important;
  overflow-x: auto !important;
  white-space: normal !important;
}

body[data-aeroone-viewer-fit="content"] .sidebar,
body[data-aeroone-viewer-fit="content"] #sidebar,
body[data-aeroone-viewer-fit="content"] [class*="sidebar"] {
  box-sizing: border-box !important;
  max-height: var(--aeroone-viewer-sidebar-max-height, 720px) !important;
  overflow-y: auto !important;
  overscroll-behavior: contain !important;
  scrollbar-gutter: stable !important;
}

@media (max-width: 1180px) {
  body[data-aeroone-viewer-fit="content"] .sidebar,
  body[data-aeroone-viewer-fit="content"] #sidebar,
  body[data-aeroone-viewer-fit="content"] [class*="sidebar"] {
    position: static !important;
    transform: none !important;
    width: 100% !important;
    height: auto !important;
    max-height: 280px !important;
    overflow-y: auto !important;
  }

  body[data-aeroone-viewer-fit="content"] .main {
    margin-left: 0 !important;
    width: 100% !important;
  }

  body[data-aeroone-viewer-fit="content"] .main-inner {
    padding-left: clamp(16px, 4vw, 34px) !important;
    padding-right: clamp(16px, 4vw, 34px) !important;
  }

  body[data-aeroone-viewer-fit="content"] .printbtn {
    position: absolute !important;
    right: 16px !important;
  }
}
`;
export function applyContentModeSidebarScrollStyles(sidebar: HTMLElement, viewportHeight: number): string {
  const maxHeight = `${Math.max(
    CONTENT_MODE_SIDEBAR_MIN_HEIGHT,
    viewportHeight - CONTENT_MODE_SIDEBAR_VERTICAL_OFFSET,
  )}px`;
  sidebar.style.maxHeight = maxHeight;
  sidebar.style.overflowY = 'auto';
  sidebar.style.setProperty('overscroll-behavior', 'contain');
  sidebar.style.setProperty('scrollbar-gutter', 'stable');
  return maxHeight;
}

function clearContentModeSidebarScrollStyles(sidebar: HTMLElement): void {
  sidebar.style.maxHeight = '';
  sidebar.style.overflowY = '';
  sidebar.style.removeProperty('overscroll-behavior');
  sidebar.style.removeProperty('scrollbar-gutter');
}


export function applyViewerFitStyles(doc: Document, fit: HtmlViewerFit): void {
  if (!doc.body || !doc.head) {
    return;
  }

  if (doc.body.getAttribute('data-aeroone-viewer-fit') !== fit) {
    doc.body.setAttribute('data-aeroone-viewer-fit', fit);
  }

  let style = doc.getElementById(VIEWER_FIT_STYLE_ID) as HTMLStyleElement | null;
  if (!style) {
    style = doc.createElement('style');
    style.id = VIEWER_FIT_STYLE_ID;
    doc.head.appendChild(style);
  }

  if (style.textContent !== VIEWER_FIT_STYLE) {
    style.textContent = VIEWER_FIT_STYLE;
  }
}




// scrolling="no" iframe 의 높이를 콘텐츠 전체 높이에 맞춘다. 본문이 JS 로 늦게
// 주입되고 이미지·폰트 로드로 레이아웃이 더 커지므로 측정 시점에 따라 값이
// 달라진다. body/documentElement 의 scroll/offset 높이 최댓값을 쓰고 최소 1800.
function measureContentHeight(doc: Document): number {
  const body = doc.body;
  const root = doc.documentElement;
  return Math.max(
    body?.scrollHeight ?? 0,
    body?.offsetHeight ?? 0,
    root?.scrollHeight ?? 0,
    root?.offsetHeight ?? 0,
    1800,
  );
}

export function getScrollableWheelAncestor(
  target: EventTarget | null,
  doc: Document,
  deltaX: number,
  deltaY: number,
  shiftKey = false,
): Element | null {
  const initialElement =
    isElementFromDocument(target, doc) || (target instanceof Element && target.ownerDocument === doc)
      ? target
      : null;
  if (!initialElement) {
    return null;
  }

  const effectiveDeltaX = shiftKey && deltaX === 0 ? deltaY : deltaX;
  let element: Element | null = initialElement;
  while (element && element !== doc.body && element !== doc.documentElement) {
    if (canElementConsumeWheel(element, doc, effectiveDeltaX, deltaY)) {
      return element;
    }
    element = element.parentElement;
  }

  return null;
}

function canElementConsumeWheel(element: Element, doc: Document, deltaX: number, deltaY: number): boolean {
  const view = doc.defaultView;
  const style = view?.getComputedStyle(element);
  const htmlElement = element as HTMLElement;
  const overflowX = style?.overflowX || htmlElement.style.overflowX || htmlElement.style.overflow || '';
  const overflowY = style?.overflowY || htmlElement.style.overflowY || htmlElement.style.overflow || '';
  const scrollableX = overflowX === 'auto' || overflowX === 'scroll' || overflowX === 'overlay';
  const scrollableY = overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay';
  const canScrollDown = htmlElement.scrollTop + htmlElement.clientHeight < htmlElement.scrollHeight - 1;
  const canScrollUp = htmlElement.scrollTop > 0;
  const canScrollRight = htmlElement.scrollLeft + htmlElement.clientWidth < htmlElement.scrollWidth - 1;
  const canScrollLeft = htmlElement.scrollLeft > 0;

  if (deltaY > 0 && scrollableY && canScrollDown) {
    return true;
  }
  if (deltaY < 0 && scrollableY && canScrollUp) {
    return true;
  }
  if (deltaX > 0 && scrollableX && canScrollRight) {
    return true;
  }
  if (deltaX < 0 && scrollableX && canScrollLeft) {
    return true;
  }

  return false;
}

export function clampWindowScrollTop(top: number): number {
  if (typeof document === 'undefined' || typeof window === 'undefined') {
    return Math.max(0, top);
  }
  const root = document.documentElement;
  const body = document.body;
  const scrollHeight = Math.max(root?.scrollHeight ?? 0, body?.scrollHeight ?? 0);
  const maxTop = scrollHeight > window.innerHeight ? scrollHeight - window.innerHeight : 0;
  const nonNegativeTop = Math.max(0, top);
  return maxTop > 0 ? Math.min(nonNegativeTop, maxTop) : nonNegativeTop;
}

export type HtmlViewerFit = 'content' | 'viewport';

// content-fit 높이 동기화 튜닝 상수.
// - HEIGHT_TOLERANCE_PX: 이 픽셀 이하의 미세 변화는 setHeight 를 건너뛴다(리플로우/churn 방지).
// - POLL_STABLE_LIMIT: 폴링에서 이 횟수만큼 연속으로 허용오차 이내면 콘텐츠가 안정된 것으로 보고 타이머를 멈춘다.
export const HEIGHT_TOLERANCE_PX = 8;
export const POLL_STABLE_LIMIT = 5;

// fit 모드 두 가지.
// - 'content'(뉴스레터 기본): iframe 높이를 콘텐츠 전체에 맞추고 scrolling="no" →
//   바깥 페이지가 스크롤. 기사 아코디언/lazy 이미지 높이 보정이 함께 동작한다.
// - 'viewport'(문서·카탈로그·NSA 기본): iframe 을 "창 높이"로 고정하고 내부
//   스크롤을 켠다. 그러면 문서가 단독 실행될 때처럼 자체 viewport 가 생겨
//   목차의 position:fixed/sticky, height:100vh, 내부 overflow 스크롤이 그대로
//   동작한다(콘텐츠 높이 동기화는 하지 않는다 — 자체 viewport 가 핵심이므로).
export function HtmlViewer({
  title,
  html,
  fit = 'content',
  showFitToggle = false,
  downloadHref,
  downloadLabel = 'HTML 다운로드',
  onDownload,
}: {
  title: string;
  html: string;
  fit?: HtmlViewerFit;
  showFitToggle?: boolean;
  downloadHref?: string;
  downloadLabel?: string;
  onDownload?: () => void;
}) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1800);
  const [mode, setMode] = useState<HtmlViewerFit>(fit);
  const [showHelp, setShowHelp] = useState(false);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const mutationObserverRef = useRef<MutationObserver | null>(null);
  const timerRef = useRef<number | null>(null);

  const heightRef = useRef(height);
  const handleScrollRef = useRef<(() => void) | null>(null);
  // 폴링이 연속으로 허용오차 이내(안정)였던 횟수. POLL_STABLE_LIMIT 도달 시 폴링 조기 종료.
  const stableCountRef = useRef(0);

  useEffect(() => {
    heightRef.current = height;
    if (handleScrollRef.current) {
      handleScrollRef.current();
    }
  }, [height]);
  function getDoc(): Document | null {
    return iframeRef.current?.contentWindow?.document ?? null;
  }

  // iframe 내부의 해시(목차) 링크 클릭 이벤트를 감지하여 적절한 스크롤 효과를 줍니다.
  function setupAnchorLinks() {
    const doc = getDoc();
    if (!doc || !doc.body) {
      return;
    }

    normalizeSameDocumentHashLinks(doc, window.location.href);

    if (doc.body.hasAttribute('data-aeroone-anchors-bound')) {
      return;
    }

    const handleClick = (e: MouseEvent) => {
      const target = e.target;
      if (!isElementFromDocument(target, doc)) return;
      const anchor = target.closest('a');
      if (!anchor) return;

      const href = anchor.getAttribute('href');
      const targetId = resolveSameDocumentHashTarget(href, window.location.href);
      if (!targetId) {
        return;
      }

      const targetEl = doc.getElementById(targetId);
      if (!targetEl) {
        return;
      }

      e.preventDefault();
      e.stopPropagation();

      const isContentMode = iframeRef.current?.getAttribute('scrolling') === 'no';
      if (isContentMode) {
        const iframeEl = iframeRef.current;
        if (iframeEl) {
          const iframeRect = iframeEl.getBoundingClientRect();
          const targetRect = targetEl.getBoundingClientRect();
          const innerScrollY = iframeEl.contentWindow?.scrollY ?? 0;
          // 부모 창 기준 절대 y 좌표 계산
          const absoluteTop = window.scrollY + iframeRect.top + targetRect.top + innerScrollY;
          // sticky 헤더(60px) + 여유(10px) = 70px 오프셋 차감
          const offset = 70;
          const requestedTop = absoluteTop - offset;
          window.scrollTo({
            top: clampWindowScrollTop(requestedTop),
            behavior: 'smooth',
          });
        }
      } else {
        const iframeWindow = iframeRef.current?.contentWindow;
        if (iframeWindow) {
          const targetRect = targetEl.getBoundingClientRect();
          iframeWindow.scrollTo({
            top: iframeWindow.scrollY + targetRect.top - 12,
            behavior: 'smooth',
          });
        } else {
          targetEl.scrollIntoView({ behavior: 'smooth' });
        }
      }
    };

    doc.addEventListener('click', handleClick, true);
    doc.body.setAttribute('data-aeroone-anchors-bound', '1');
  }

  function setupContentModeWheelScroll() {
    const doc = getDoc();
    if (!doc?.body) {
      return;
    }

    if (doc.body.hasAttribute('data-aeroone-wheel-bound')) {
      return;
    }

    const handleWheel = (e: WheelEvent) => {
      if (iframeRef.current?.getAttribute('scrolling') !== 'no') {
        return;
      }
      if (e.deltaX === 0 && e.deltaY === 0) {
        return;
      }
      if (getScrollableWheelAncestor(e.target, doc, e.deltaX, e.deltaY, e.shiftKey)) {
        return;
      }
      e.preventDefault();
      window.scrollBy({
        left: e.deltaX,
        top: e.deltaY,
        behavior: 'auto',
      });
    };

    doc.addEventListener('wheel', handleWheel, { passive: false });
    doc.body.setAttribute('data-aeroone-wheel-bound', '1');
  }

  // 높이를 측정값으로 맞춘다(증가뿐 아니라 사용자가 기사를 접어 줄어든 경우도 반영).
  // D1-A: (1) 허용오차(HEIGHT_TOLERANCE_PX) 이하의 미세 변화는 setHeight 를 건너뛴다 →
  //   매 측정마다 바깥 페이지 리플로우가 발생해 스크롤이 위로 튀던 churn 을 막는다.
  // (2) 실제 높이 변경 시에도 쓰기 직전 window.scrollY 를 잡아두고, DOM 높이가 반영되는
  //   다음 애니메이션 프레임에서 복원해 읽던 위치가 맨 위로 점프하지 않게 한다.
  // (3) 연속으로 허용오차 이내면 stableCountRef 를 올려 폴링 조기 종료(startTracking)에 쓴다.
  function syncHeight() {
    const doc = getDoc();
    if (!doc) {
      return;
    }
    const next = measureContentHeight(doc);
    if (Math.abs(next - heightRef.current) <= HEIGHT_TOLERANCE_PX) {
      stableCountRef.current += 1;
      return;
    }
    stableCountRef.current = 0;
    const prevScrollY = typeof window !== 'undefined' ? window.scrollY : 0;
    const prevScrollX = typeof window !== 'undefined' ? window.scrollX : 0;
    setHeight(next);
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => {
        // 높이 반영으로 바깥 페이지가 맨 위로 튀어도 직전 스크롤 위치로 되돌린다.
        // 동일 위치면 브라우저상 no-op 이라 무해하다.
        window.scrollTo(prevScrollX, prevScrollY);
      });
    }
  }

  // 기사 본문이 JS 로 비동기 주입되므로 같은 문서(allow-same-origin)에서 펼친다.
  // :not([data-aeroone-defopen]) 로 처리한 기사는 건너뛰어, 재호출돼도 사용자가
  // 접은 기사를 다시 펼치지 않는다.
  function expandArticles() {
    const doc = getDoc();
    if (!doc) {
      return;
    }
    expandNewsletterArticles(doc);
  }

  // 기사 카드 이미지는 loading="lazy" 라, 높이가 작게 잡힌 iframe 의 뷰포트
  // 밖에 있으면 영영 로드되지 않는다(고정 높이 iframe ↔ lazy 의 교착). 그러면
  // 카드 높이가 안 늘어 본문이 잘리고, 새로고침 때만(이미지 캐시로 즉시 complete)
  // 정상으로 보인다. 이를 끊으려 lazy 이미지를 eager 로 바꿔 위치와 무관하게
  // 로드시키고, 아직 로드 전인 이미지엔 load/error 핸들러를 1회 달아 로드 완료
  // 시 높이를 다시 맞춘다.
  function prepareImages() {
    const doc = getDoc();
    if (!doc) {
      return;
    }
    doc.querySelectorAll<HTMLImageElement>('img:not([data-aeroone-img])').forEach((img) => {
      img.setAttribute('data-aeroone-img', '1');
      if (img.loading === 'lazy') {
        img.loading = 'eager';
      }
      if (!img.complete) {
        img.addEventListener('load', syncHeight);
        img.addEventListener('error', syncHeight);
      }
    });
  }

  function stopTracking() {
    resizeObserverRef.current?.disconnect();
    mutationObserverRef.current?.disconnect();
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function refresh() {
    expandArticles();
    prepareImages();
    const doc = getDoc();
    if (doc) {
      applyViewerFitStyles(doc, mode);
    }
    setupContentModeWheelScroll();
    setupAnchorLinks();
    syncHeight();
  }

  function startTracking() {
    const doc = getDoc();
    if (!doc?.body || !doc.documentElement) {
      return;
    }

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = new ResizeObserver(() => syncHeight());
      resizeObserverRef.current.observe(doc.body);
      resizeObserverRef.current.observe(doc.documentElement);
    }

    // 콘텐츠 주입·기사 펼침 등 DOM 변화를 즉시 잡아 높이를 다시 맞춘다.
    // 첫(콜드) 로드에서 본문이 잘리던 원인(과소측정)을 직접 해소하는 핵심 트리거.
    if (typeof MutationObserver !== 'undefined') {
      mutationObserverRef.current?.disconnect();
      mutationObserverRef.current = new MutationObserver(() => refresh());
      mutationObserverRef.current.observe(doc.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
      });
    }

    // 폰트 로드 완료 후 리플로우로 높이가 바뀔 수 있어 한 번 더 맞춘다.
    const fonts = (doc as Document & { fonts?: { ready?: Promise<unknown> } }).fonts;
    fonts?.ready?.then(() => syncHeight()).catch(() => undefined);

    // Observer 가 못 잡는 틈(폰트 리플로우 등)을 메우는 안전망 폴링.
    // 12초(40 * 300ms)까지 재측정하되, D1-A: 연속 POLL_STABLE_LIMIT 회 허용오차 이내로
    // 측정되면(콘텐츠 안정) 폴링을 조기 종료한다. ResizeObserver/MutationObserver/이미지
    // load 핸들러는 계속 살아있어 lazy 이미지 등 실제 후속 성장은 여전히 높이를 다시 맞춘다.
    let runs = 0;
    stableCountRef.current = 0;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
    }
    timerRef.current = window.setInterval(() => {
      refresh();
      runs += 1;
      if (
        (runs >= 40 || stableCountRef.current >= POLL_STABLE_LIMIT) &&
        timerRef.current
      ) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 300);
  }

  function handleOpenNewWindow() {
    const blob = new Blob([normalizeHtmlForStandaloneWindow(html)], { type: 'text/html;charset=utf-8' });
    const objectUrl = window.URL.createObjectURL(blob);
    const newWindow = window.open(objectUrl, '_blank');
    if (!newWindow) {
      window.URL.revokeObjectURL(objectUrl);
      alert('팝업 차단이 설정되어 있습니다. 브라우저의 팝업 차단을 해제하고 다시 시도해주세요.');
      return;
    }
    window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 60_000);
  }

  // 콘텐츠 로드 직후 + 모드 전환 시 처리. content 모드만 높이 동기화/추적을 켜고,
  // viewport 모드는 자체 스크롤에 맡기므로 추적을 끈다(기사 펼침/이미지 준비는
  // 두 모드 모두 1회 적용 — 문서엔 보통 no-op 이라 무해).
  function applyMode() {
    expandArticles();
    prepareImages();
    const doc = getDoc();
    if (doc) {
      applyViewerFitStyles(doc, mode);
    }
    setupAnchorLinks();
    setupContentModeWheelScroll();
    if (mode === 'content') {
      syncHeight();
      startTracking();
    } else {
      stopTracking();
    }
  }

  // 사용자가 토글로 모드를 바꾸면 onLoad 가 다시 안 뜨므로 여기서 반영한다.
  useEffect(() => {
    applyMode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // content 모드(전체 높이)에서도 목차가 화면에 고정되어 따라오도록 스크롤 동기화 처리를 수행합니다.
  useEffect(() => {
    if (mode !== 'content') {
      const doc = getDoc();
      const sidebar = doc?.querySelector('.sidebar, #sidebar, [class*="sidebar"]') as HTMLElement | null;
      if (sidebar) {
        sidebar.style.position = '';
        sidebar.style.transform = '';
        sidebar.style.willChange = '';
        clearContentModeSidebarScrollStyles(sidebar);
      }
      handleScrollRef.current = null;
      return;
    }

    let ticking = false;

    const handleScroll = () => {
      if (ticking) return;
      ticking = true;

      window.requestAnimationFrame(() => {
        const doc = getDoc();
        const iframeEl = iframeRef.current;
        if (!doc || !iframeEl) {
          ticking = false;
          return;
        }

        const sidebar = doc.querySelector('.sidebar, #sidebar, [class*="sidebar"]') as HTMLElement | null;
        if (!sidebar) {
          ticking = false;
          return;
        }

        // 모바일 화면 크기(768px 이하)인 경우에는 스타일 조작을 하지 않고 원본 레이아웃(static 등)을 유지합니다.
        const isMobile = doc.defaultView ? doc.defaultView.innerWidth <= 768 : false;
        if (isMobile) {
          sidebar.style.position = '';
          sidebar.style.transform = '';
          sidebar.style.willChange = '';
          clearContentModeSidebarScrollStyles(sidebar);
          ticking = false;
          return;
        }

        // 데스크톱 뷰에서 iframe의 position:fixed는 content(전체높이) 모드 시 화면 밖으로 밀리게 되므로
        // absolute로 강제 변환하며, will-change를 적용하여 GPU 렌더링 레이어 격리를 유도합니다.
        if (sidebar.style.position !== 'absolute') {
          sidebar.style.position = 'absolute';
        }
        if (sidebar.style.willChange !== 'transform') {
          sidebar.style.willChange = 'transform';
        }
        const sidebarMaxHeight = applyContentModeSidebarScrollStyles(sidebar, window.innerHeight);
        doc.documentElement.style.setProperty('--aeroone-viewer-sidebar-max-height', sidebarMaxHeight);

        const scrollY = window.scrollY;
        const iframeRect = iframeEl.getBoundingClientRect();
        const iframeAbsoluteTop = scrollY + iframeRect.top;

        // 부모 창 고정 헤더 높이 60px 아래에 목차가 붙도록 설정
        const headerHeight = 60;
        const stickyTop = Math.max(0, scrollY + headerHeight - iframeAbsoluteTop);

        // DOM 리플로우(offsetHeight 호출)를 유발하지 않도록, 브라우저 뷰포트 높이와 상태값 heightRef.current로 제한치를 계산합니다.
        // 이로써 스크롤 시 목차의 덜덜 떨림 및 깜빡거림, 사라짐 버그를 원천 방어합니다.
        const sidebarHeight = window.innerHeight;
        const iframeHeight = heightRef.current; 
        const maxStickyTop = Math.max(0, iframeHeight - sidebarHeight - 30);
        const finalStickyTop = Math.min(stickyTop, maxStickyTop);

        // 하드웨어 3D 가속(translate3d)을 활용하여 스크롤 주사율(60fps)과 완벽하게 동기화하고 깜빡임을 차단합니다.
        sidebar.style.transform = `translate3d(0, ${finalStickyTop}px, 0)`;
        
        ticking = false;
      });
    };

    handleScrollRef.current = handleScroll;
    // 초기 렌더 및 모드 진입 직후 위치 지정을 위해 즉시 한 번 호출합니다.
    handleScroll();

    window.addEventListener('scroll', handleScroll);
    const interval = setInterval(handleScroll, 500); // 폰트 로드나 레이아웃 변경 대응을 위한 안전망

    return () => {
      window.removeEventListener('scroll', handleScroll);
      clearInterval(interval);
      const doc = getDoc();
      const sidebar = doc?.querySelector('.sidebar, #sidebar, [class*="sidebar"]') as HTMLElement | null;
      if (sidebar) {
        sidebar.style.position = '';
        sidebar.style.transform = '';
        sidebar.style.willChange = '';
        clearContentModeSidebarScrollStyles(sidebar);
      }
      handleScrollRef.current = null;
    };
  }, [mode]);

  useEffect(() => {
    return () => stopTracking();
  }, []);

  const isViewport = mode === 'viewport';

  const iframe = (
    <iframe
      ref={iframeRef}
      title={title}
      // allow-scripts 포함: Newsletter_AI 산출 HTML 은 <script> 로 본문(기사
      // 카드)을 innerHTML 주입하는 JS 렌더 방식이라, 스크립트가 막히면 본문이
      // 빈 화면으로 보인다. 콘텐츠는 운영자 자신의 파이프라인 산출물(신뢰
      // 가능)이므로 Newsletter_AI 의 report preview 와 동일하게 allow-scripts
      // 를 허용한다. 폐쇄망에서 외부 폰트/CDN 은 차단되지만 본문 주입 JS 는
      // 페이지 내 데이터만 쓰므로 정상 동작한다.
      sandbox="allow-same-origin allow-scripts"
      // content 모드는 바깥 페이지가 스크롤하므로 iframe 자체 스크롤을 끈다.
      // viewport 모드는 iframe 이 자체 viewport 로 내부 스크롤해야 하므로 명시적으로 켠다.
      scrolling={isViewport ? 'yes' : 'no'}
      srcDoc={html}
      onLoad={applyMode}
      // content: 측정한 콘텐츠 전체 높이. viewport: 창 높이로 고정(내부 스크롤).
      style={isViewport ? VIEWPORT_IFRAME_STYLE : { height }}
      className={`w-full ${isViewport ? 'overflow-auto' : 'overflow-hidden'} rounded-2xl border border-slate-200 bg-white shadow-sm`}
    />
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:justify-end">
        <button
          type="button"
          onClick={() => setShowHelp((prev) => !prev)}
          className={`inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border px-2.5 py-1.5 text-sm transition-colors ${
            showHelp
              ? 'border-blue-300 bg-blue-50 text-blue-800 hover:bg-blue-100 hover:text-blue-900 dark:border-blue-800 dark:bg-blue-950/45 dark:text-blue-200'
              : 'border-line-subtle bg-surface-raised text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
          }`}
          title="문서 뷰어 조작 방법에 대한 설명을 봅니다"
        >
          <Icon.doc size={13} />
          {showHelp ? '설명 닫기' : '설명 보기'}
        </button>
        <button
          type="button"
          onClick={handleOpenNewWindow}
          className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-line-subtle bg-surface-raised px-2.5 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
          title="문서를 새 창에서 원본 크기 그대로 엽니다"
        >
          <Icon.external size={13} />
          새 창으로 열기
        </button>
        {showFitToggle ? (
          <button
            type="button"
            data-testid="html-viewer-fit-toggle"
            aria-pressed={isViewport}
            onClick={() => setMode((current) => (current === 'viewport' ? 'content' : 'viewport'))}
            className="col-span-2 inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-line-subtle bg-surface-raised px-2.5 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1 sm:col-span-1"
            title={isViewport ? '문서 전체를 한 페이지로 펼쳐 봅니다' : '창 높이에 맞춰 문서 자체 스크롤(목차 고정)로 봅니다'}
          >
            {isViewport ? '전체 높이로 보기' : '창 높이로 보기 (목차 고정)'}
          </button>
        ) : null}
        {downloadHref ? (
          <a
            href={downloadHref}
            download
            data-testid="html-viewer-download"
            onClick={onDownload}
            className="inline-flex min-h-10 items-center justify-center rounded-md border border-accent/60 bg-accent-soft px-3 py-1.5 text-sm font-semibold text-accent shadow-md shadow-accent/20 ring-1 ring-accent/15 transition-colors hover:bg-accent hover:text-accent-on focus-visible:shadow-focus focus-visible:outline-none"
            title={`${title} HTML 다운로드`}
            aria-label={`${title} HTML 다운로드`}
          >
            {downloadLabel}
          </a>
        ) : null}
      </div>

      {showHelp && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/30 p-4 text-sm text-blue-900 shadow-sm transition-all dark:border-blue-900/30 dark:bg-blue-950/20 dark:text-blue-200">
          <h4 className="mb-2 flex items-center gap-1.5 font-bold text-blue-800 dark:text-blue-300">
            AeroOne 문서 뷰어 조작 가이드
          </h4>
          <ul className="space-y-1.5 list-disc list-inside text-xs leading-relaxed text-ink-2">
            <li>
              <span className="font-semibold text-blue-800 dark:text-blue-300">설명 보기</span>: 
              뷰어 조작 가이드를 켜고 끕니다.
            </li>
            <li>
              <span className="font-semibold text-blue-800 dark:text-blue-300">새 창으로 열기</span>: 
              문서 원본을 새 탭에서 온전히 로딩합니다. 브라우저 전체 화면에서 원본 그대로 목차 고정을 감상할 수 있습니다.
            </li>
            <li>
              <span className="font-semibold text-blue-800 dark:text-blue-300">전체 높이로 보기</span>: 
              문서 본문을 접지 않고 페이지 전체 크기로 길게 펼칩니다. 부모 창을 스크롤할 때 목차가 부드럽게 고정되어 따라다닙니다.
            </li>
            <li>
              <span className="font-semibold text-blue-800 dark:text-blue-300">창 높이로 보기 (목차 고정)</span>: 
              문서 뷰어의 세로 길이를 브라우저 화면 높이에 고정하고 이중 스크롤바를 숨겨, 뷰어 내에서 단독 스크롤하며 목차가 네이티브로 고정되도록 동작합니다.
            </li>
          </ul>
        </div>
      )}

      {iframe}
    </div>
  );
}
