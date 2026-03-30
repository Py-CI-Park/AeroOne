import React, { useRef, useState } from 'react';
export function HtmlViewer({ title, html }: { title: string; html: string }) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(1400);

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

  return (
    <iframe
      ref={iframeRef}
      title={title}
      sandbox="allow-same-origin"
      scrolling="no"
      srcDoc={html}
      onLoad={syncHeight}
      style={{ height }}
      className="w-full rounded-2xl border border-slate-200 bg-white shadow-sm"
    />
  );
}
