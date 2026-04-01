import React, { useEffect, useRef, useState } from 'react';
export function HtmlViewer({ title, html }: { title: string; html: string }) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1400);
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
    setHeight(Math.max(bodyHeight, htmlHeight, 1400));
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
      sandbox="allow-same-origin"
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
