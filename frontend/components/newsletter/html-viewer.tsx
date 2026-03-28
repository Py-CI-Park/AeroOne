import React from 'react';
export function HtmlViewer({ title, html }: { title: string; html: string }) {
  return (
    <iframe
      title={title}
      sandbox=""
      srcDoc={html}
      className="min-h-[900px] w-full rounded-xl border border-slate-200 bg-white"
    />
  );
}
