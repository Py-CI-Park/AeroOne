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

export function HtmlViewer({ title, html }: { title: string; html: string }) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1800);
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

  useEffect(() => {
    return () => {
      resizeObserverRef.current?.disconnect();
      mutationObserverRef.current?.disconnect();
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
      }
    };
  }, []);

  return (
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
      scrolling="no"
      srcDoc={html}
      onLoad={() => {
        refresh();
        startTracking();
      }}
      style={{ height }}
      className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    />
  );
}
