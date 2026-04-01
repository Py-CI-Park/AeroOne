import React from 'react';
export function MarkdownViewer({ html }: { html: string }) {
  return <div className="prose max-w-none rounded-xl border border-slate-200 bg-white p-8" dangerouslySetInnerHTML={{ __html: html }} />;
}
