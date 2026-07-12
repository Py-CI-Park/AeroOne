'use client';

import React from 'react';
import type { EChartsType } from 'echarts';

import { beautifyEChartsOption } from '@/lib/echarts-beautify';

/**
 * 서버가 만든 ECharts option(JSON)을 브라우저에서 렌더하는 미리보기.
 *
 * echarts 는 무겁고 SSR 비호환이라 모듈 최상단에서 import 하지 않고 effect 안에서 지연
 * import 한다(페이지는 이 컴포넌트를 `next/dynamic({ ssr: false })` 로 로드). 서버는 pandas
 * 집계 결과만 option 으로 넘기고, 렌더/PNG 추출은 여기서 한다. option 은 신뢰된 서버 산출물
 * 이므로 그대로 setOption 한다.
 */
type ChartPreviewProps = {
  option: Record<string, unknown>;
  title: string;
};

export function ChartPreview({ option, title }: ChartPreviewProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<EChartsType | null>(null);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let cancelled = false;
    let disposed = false;

    async function render() {
      setError('');
      try {
        const echarts = await import('echarts');
        if (cancelled || !containerRef.current) return;
        const instance = echarts.init(containerRef.current, undefined, { renderer: 'canvas' });
        chartRef.current = instance;
        // 서버 option 에 검증 팔레트·라운드 막대·툴팁·레전드 등 표현 스타일을 입혀 렌더한다.
        instance.setOption(beautifyEChartsOption(option), { notMerge: true });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : '차트 렌더에 실패했습니다.');
      }
    }

    render();
    const handleResize = () => chartRef.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      cancelled = true;
      disposed = true;
      window.removeEventListener('resize', handleResize);
      if (disposed) chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, [option]);

  function downloadPng() {
    try {
      const url = chartRef.current?.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
      if (!url) return;
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${safeFileBase(title)}.png`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
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

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={containerRef}
        data-testid="chart-preview-canvas"
        className="h-[460px] w-full rounded-xl border border-ink-3/20 bg-white p-3 shadow-sm"
      />
      <div className="flex gap-2">
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
  return cleaned.slice(0, 60) || 'chart';
}
