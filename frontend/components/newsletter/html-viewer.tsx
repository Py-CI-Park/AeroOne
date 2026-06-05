import React, { useEffect, useRef, useState } from 'react';

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

export type HtmlViewerFit = 'content' | 'viewport';

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
}: {
  title: string;
  html: string;
  fit?: HtmlViewerFit;
  showFitToggle?: boolean;
}) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1800);
  const [mode, setMode] = useState<HtmlViewerFit>(fit);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const mutationObserverRef = useRef<MutationObserver | null>(null);
  const timerRef = useRef<number | null>(null);

  function getDoc(): Document | null {
    return iframeRef.current?.contentWindow?.document ?? null;
  }

  // 높이를 측정값으로 맞춘다(증가뿐 아니라 사용자가 기사를 접어 줄어든 경우도 반영).
  function syncHeight() {
    const doc = getDoc();
    if (!doc) {
      return;
    }
    setHeight(measureContentHeight(doc));
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
    // 12초(40 * 300ms)까지 재측정하고 멈춘다.
    let runs = 0;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
    }
    timerRef.current = window.setInterval(() => {
      refresh();
      runs += 1;
      if (runs >= 40 && timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 300);
  }

  // 콘텐츠 로드 직후 + 모드 전환 시 처리. content 모드만 높이 동기화/추적을 켜고,
  // viewport 모드는 자체 스크롤에 맡기므로 추적을 끈다(기사 펼침/이미지 준비는
  // 두 모드 모두 1회 적용 — 문서엔 보통 no-op 이라 무해).
  function applyMode() {
    expandArticles();
    prepareImages();
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
      // viewport 모드는 iframe 이 자체 viewport 로 내부 스크롤해야 하므로 끄지 않는다.
      scrolling={isViewport ? undefined : 'no'}
      srcDoc={html}
      onLoad={applyMode}
      // content: 측정한 콘텐츠 전체 높이. viewport: 창 높이로 고정(내부 스크롤).
      style={isViewport ? { height: 'calc(100vh - 200px)', minHeight: 480 } : { height }}
      className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    />
  );

  if (!showFitToggle) {
    return iframe;
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-end">
        <button
          type="button"
          data-testid="html-viewer-fit-toggle"
          aria-pressed={isViewport}
          onClick={() => setMode((current) => (current === 'viewport' ? 'content' : 'viewport'))}
          className="inline-flex items-center gap-1.5 rounded-md border border-line-subtle bg-surface-raised px-2.5 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
          title={isViewport ? '문서 전체를 한 페이지로 펼쳐 봅니다' : '창 높이에 맞춰 문서 자체 스크롤(목차 고정)로 봅니다'}
        >
          {isViewport ? '전체 높이로 보기' : '창 높이로 보기 (목차 고정)'}
        </button>
      </div>
      {iframe}
    </div>
  );
}
