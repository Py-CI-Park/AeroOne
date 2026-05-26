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

export function HtmlViewer({ title, html }: { title: string; html: string }) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1800);
  const observerRef = useRef<ResizeObserver | null>(null);
  const timerRef = useRef<number | null>(null);

  function syncHeight() {
    const iframe = iframeRef.current;
    if (!iframe?.contentWindow?.document) {
      return;
    }
    const doc = iframe.contentWindow.document;
    const bodyHeight = doc.body?.scrollHeight ?? 0;
    const htmlHeight = doc.documentElement?.scrollHeight ?? 0;
    setHeight(Math.max(bodyHeight, htmlHeight, 1800));
  }

  // 기사 본문이 JS 로 비동기 주입되므로, 같은 iframe 문서(allow-same-origin)에서
  // 기사를 펼친다. :not([data-aeroone-defopen]) 로 이미 처리한 기사는 건너뛰어,
  // 폴링/Observer 가 반복 호출돼도 사용자가 접은 기사를 다시 펼치지 않는다.
  function expandArticles() {
    const doc = iframeRef.current?.contentWindow?.document;
    if (!doc) {
      return;
    }
    expandNewsletterArticles(doc);
  }

  function bindResizeTracking() {
    const iframe = iframeRef.current;
    const doc = iframe?.contentWindow?.document;
    if (!doc?.body || !doc.documentElement) {
      return;
    }
    if (typeof ResizeObserver === 'undefined') {
      return;
    }

    observerRef.current?.disconnect();
    observerRef.current = new ResizeObserver(() => {
      syncHeight();
      expandArticles();
    });
    observerRef.current.observe(doc.body);
    observerRef.current.observe(doc.documentElement);

    let runs = 0;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
    }
    timerRef.current = window.setInterval(() => {
      syncHeight();
      expandArticles();
      runs += 1;
      if (runs >= 20 && timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 300);
  }

  useEffect(() => {
    return () => {
      observerRef.current?.disconnect();
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
        syncHeight();
        expandArticles();
        bindResizeTracking();
      }}
      style={{ height }}
      className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    />
  );
}
