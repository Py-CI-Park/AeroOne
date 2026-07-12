'use client';

import React from 'react';

/**
 * Mermaid 소스를 브라우저에서 strict 모드로 렌더하는 미리보기.
 *
 * mermaid 는 무겁고 SSR 비호환이라 모듈 최상단에서 import 하지 않고 effect 안에서
 * 지연 import 한다(페이지는 이 컴포넌트를 `next/dynamic({ ssr: false })` 로 로드).
 * 서버가 이미 `validate_mermaid` 로 실행 지시어를 차단했고, 여기서도 `securityLevel:
 * 'strict'` 로 이중 방어한다. 렌더 결과 SVG/PNG 는 브라우저에서 내려받는다.
 */
type DiagramPreviewProps = {
  source: string;
  title: string;
};

let _renderSeq = 0;

export function DiagramPreview({ source, title }: DiagramPreviewProps) {
  const [svg, setSvg] = React.useState<string>('');
  const [error, setError] = React.useState<string>('');

  React.useEffect(() => {
    let cancelled = false;
    async function render() {
      setError('');
      try {
        const mermaid = (await import('mermaid')).default;
        // 실서비스급 표현: 밋밋한 neutral 대신 브랜드 색을 입힌 base 테마 + 곡선 엣지·넉넉한 간격.
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'base',
          fontFamily: 'inherit',
          themeVariables: {
            primaryColor: '#eaf1fb',
            primaryBorderColor: '#2a78d6',
            primaryTextColor: '#0b0b0b',
            secondaryColor: '#e7f7f0',
            secondaryBorderColor: '#1baf7a',
            tertiaryColor: '#fbf3e0',
            tertiaryBorderColor: '#eda100',
            lineColor: '#6b7280',
            fontSize: '15px',
            clusterBkg: '#f7f7f5',
            clusterBorder: '#d8d8d3',
            nodeBorder: '#2a78d6',
            edgeLabelBackground: '#ffffff',
          },
          flowchart: { curve: 'basis', htmlLabels: true, padding: 16, nodeSpacing: 46, rankSpacing: 58, useMaxWidth: true },
          sequence: { useMaxWidth: true, actorMargin: 60, boxMargin: 12 },
          gantt: { useMaxWidth: true },
        });
        const id = `aeroone-diagram-${(_renderSeq += 1)}`;
        const result = await mermaid.render(id, source);
        if (!cancelled) setSvg(result.svg);
      } catch (err) {
        if (!cancelled) {
          setSvg('');
          setError(err instanceof Error ? err.message : '다이어그램 렌더에 실패했습니다.');
        }
      }
    }
    if (source.trim()) {
      render();
    } else {
      setSvg('');
    }
    return () => {
      cancelled = true;
    };
  }, [source]);

  function downloadSvg() {
    triggerDownload(new Blob([svg], { type: 'image/svg+xml' }), `${safeFileBase(title)}.svg`);
  }

  async function downloadPng() {
    try {
      const blob = await svgToPngBlob(svg);
      triggerDownload(blob, `${safeFileBase(title)}.png`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PNG 변환에 실패했습니다.');
    }
  }

  if (error) {
    return (
      <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
        {error}
      </p>
    );
  }

  if (!svg) {
    return <p className="text-sm text-ink-3">미리보기를 준비하는 중입니다…</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className="flex justify-center overflow-x-auto rounded-xl border border-ink-3/20 bg-white p-6 shadow-sm [&_svg]:h-auto [&_svg]:max-w-full"
        data-testid="diagram-preview-svg"
        // 소스는 서버 validate_mermaid + strict 렌더로 검증된 결과물이다.
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={downloadSvg}
          className="rounded-md border border-ink-3/40 px-3 py-1.5 text-sm text-ink-1 hover:bg-ink-3/10"
        >
          SVG 다운로드
        </button>
        <button
          type="button"
          onClick={downloadPng}
          className="rounded-md border border-ink-3/40 px-3 py-1.5 text-sm text-ink-1 hover:bg-ink-3/10"
        >
          PNG 다운로드
        </button>
      </div>
    </div>
  );
}

function safeFileBase(title: string): string {
  const cleaned = title.trim().replace(/[^\w가-힣.-]+/g, '_').replace(/^[._]+|[._]+$/g, '');
  return cleaned.slice(0, 60) || 'diagram';
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function svgToPngBlob(svgText: string): Promise<Blob> {
  const svgBlob = new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  try {
    const image = await loadImage(url);
    const scale = 2;
    const canvas = document.createElement('canvas');
    canvas.width = (image.width || 1200) * scale;
    canvas.height = (image.height || 800) * scale;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('캔버스 컨텍스트를 만들 수 없습니다.');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await canvasToBlob(canvas);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('SVG 이미지를 불러오지 못했습니다.'));
    image.src = url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('PNG 인코딩에 실패했습니다.'));
    }, 'image/png');
  });
}
