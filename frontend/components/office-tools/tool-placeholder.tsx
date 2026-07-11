'use client';

import React from 'react';

type ToolPlaceholderProps = {
  title: string;
  description: string;
};

/**
 * office-tools 각 도구의 클라이언트 폼 자리(뼈대).
 *
 * 다음 단계 HOOK: 이 컴포넌트를 도구별 폼(report-form / chart-form / diagram-form)과
 * 미리보기(chart-preview: echarts, diagram-preview: mermaid — 모두 dynamic import,
 * ssr:false)로 교체한다. 제출은 `/api/frontend/office-tools/*` 프록시로 보낸다.
 */
export function ToolPlaceholder({ title, description }: ToolPlaceholderProps) {
  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-dashed border-ink-3/40 px-6 py-10 text-center"
      data-testid="office-tool-placeholder"
    >
      <h2 className="text-lg font-semibold text-ink-1">{title}</h2>
      <p className="text-sm text-ink-3">{description}</p>
      <p className="text-sm font-medium text-ink-3">준비 중입니다. 도구 구현이 곧 채워집니다.</p>
    </section>
  );
}
