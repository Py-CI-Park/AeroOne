'use client';

import React, { useCallback, useRef, useState } from 'react';

export type ViewerDocType = 'markdown' | 'html';

// 확장자로 문서 종류를 추론한다(.md/.markdown → markdown, .html/.htm → html).
// 알 수 없으면 markdown 으로 둔다(사용자가 토글로 바꿀 수 있다).
export function inferDocType(fileName: string): ViewerDocType {
  const lower = fileName.toLowerCase();
  if (lower.endsWith('.html') || lower.endsWith('.htm')) {
    return 'html';
  }
  return 'markdown';
}

const ACCEPT = '.md,.markdown,.html,.htm';

// 로컬 .md/.html 파일을 열어 편집하고, 서버에서 sanitize 한 HTML 을
// 빈 sandbox(스크립트/동일출처 모두 차단) iframe 으로 미리보기한 뒤 Blob 으로 저장한다.
// 서버 쓰기는 없다(전부 클라이언트). 외부 URL/CDN 을 사용하지 않는다.
export function ViewerEditor() {
  const [text, setText] = useState('');
  const [type, setType] = useState<ViewerDocType>('markdown');
  const [fileName, setFileName] = useState('');
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const [rendering, setRendering] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadFile = useCallback((file: File) => {
    setError('');
    const reader = new FileReader();
    reader.onload = () => {
      setText(typeof reader.result === 'string' ? reader.result : '');
      setFileName(file.name);
      setType(inferDocType(file.name));
      setHtml('');
    };
    reader.onerror = () => setError('파일을 읽지 못했습니다.');
    reader.readAsText(file);
  }, []);

  const onInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        loadFile(file);
      }
    },
    [loadFile],
  );

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragActive(false);
      const file = event.dataTransfer.files?.[0];
      if (file) {
        loadFile(file);
      }
    },
    [loadFile],
  );

  const onRender = useCallback(async () => {
    setRendering(true);
    setError('');
    try {
      // same-origin 프록시(/api/frontend/render)만 호출 — 외부 절대 URL 금지.
      const response = await fetch('/api/frontend/render', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ type, text }),
      });
      if (!response.ok) {
        throw new Error(`렌더 실패 (${response.status})`);
      }
      const payload = (await response.json()) as { html?: string };
      setHtml(typeof payload.html === 'string' ? payload.html : '');
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : '렌더 중 오류가 발생했습니다.');
      setHtml('');
    } finally {
      setRendering(false);
    }
  }, [type, text]);

  const onSave = useCallback(() => {
    const mime = type === 'html' ? 'text/html' : 'text/markdown';
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName || (type === 'html' ? 'document.html' : 'document.md');
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, [text, type, fileName]);

  return (
    <div className="flex flex-col gap-4">
      <div
        data-testid="viewer-dropzone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center text-sm ${
          dragActive ? 'border-accent bg-accent-soft' : 'border-line bg-surface-raised text-ink-2'
        }`}
      >
        <p>로컬 Markdown·HTML 파일을 끌어다 놓거나 클릭해 선택하세요.</p>
        <p className="mt-1 text-xs text-ink-3">지원 형식: .md, .markdown, .html, .htm</p>
        {fileName ? <p className="mt-2 text-xs text-ink-2">불러온 파일: {fileName}</p> : null}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          onChange={onInputChange}
          data-testid="viewer-file-input"
          className="hidden"
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-2">
          형식
          <select
            data-testid="viewer-type-toggle"
            value={type}
            onChange={(event) => setType(event.target.value as ViewerDocType)}
            className="rounded border border-line bg-surface-elevated px-2 py-1 text-sm"
          >
            <option value="markdown">Markdown</option>
            <option value="html">HTML</option>
          </select>
        </label>
        <button
          type="button"
          onClick={onRender}
          disabled={rendering}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {rendering ? '렌더 중…' : '미리보기 렌더'}
        </button>
        <button
          type="button"
          onClick={onSave}
          className="rounded border border-line px-3 py-1.5 text-sm font-medium text-ink-1"
        >
          저장 (다운로드)
        </button>
      </div>

      {error ? (
        <p data-testid="viewer-error" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <textarea
          data-testid="viewer-editor"
          value={text}
          onChange={(event) => setText(event.target.value)}
          spellCheck={false}
          placeholder="파일을 불러오면 여기에 내용이 표시됩니다. 직접 편집할 수 있습니다."
          className="min-h-[420px] w-full rounded-lg border border-line bg-surface-elevated p-3 font-mono text-sm text-ink-1"
        />
        <iframe
          title="Viewer preview"
          data-testid="viewer-preview"
          sandbox=""
          srcDoc={html}
          className="min-h-[420px] w-full rounded-lg border border-line bg-white"
        />
      </div>
    </div>
  );
}
