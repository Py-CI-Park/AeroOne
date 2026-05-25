import React, { useEffect, useRef, useState } from 'react';
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
    observerRef.current = new ResizeObserver(() => syncHeight());
    observerRef.current.observe(doc.body);
    observerRef.current.observe(doc.documentElement);

    let runs = 0;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
    }
    timerRef.current = window.setInterval(() => {
      syncHeight();
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
        bindResizeTracking();
      }}
      style={{ height }}
      className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    />
  );
}
