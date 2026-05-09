import React from 'react';
export function PdfViewer({ src }: { src: string }) {
  return <iframe title="PDF viewer" src={src} className="min-h-[1200px] w-full rounded-xl border border-slate-200 bg-white" />;
}
