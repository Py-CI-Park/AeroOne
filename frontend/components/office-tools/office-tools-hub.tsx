'use client';

import React from 'react';

import { ChartForm } from '@/components/office-tools/chart-form';
import { DiagramForm } from '@/components/office-tools/diagram-form';
import { ReportForm } from '@/components/office-tools/report-form';

export type OfficeToolKey = 'diagram' | 'chart' | 'report';

const TABS: { key: OfficeToolKey; label: string; description: string }[] = [
  { key: 'diagram', label: '다이어그램', description: '설명을 Mermaid 다이어그램으로 생성합니다.' },
  { key: 'chart', label: '차트', description: 'CSV·표 데이터를 ECharts 차트로 시각화합니다.' },
  { key: 'report', label: '보고서', description: 'Markdown 을 사내 표준 HTML 보고서로 변환합니다.' },
];

/**
 * 오피스 도구 허브 — 보고서·차트·다이어그램을 한 화면에서 탭으로 전환한다.
 *
 * 대시보드의 '오피스 도구' 카드 한 장이 이 허브로 들어오고, 사용자는 탭만 눌러
 * 세 스튜디오를 오간다. 각 탭은 기존 폼 컴포넌트를 그대로 렌더한다(예제 불러오기·
 * 처리 과정 포함). 딥링크(/office-tools?tab=chart)로 특정 탭을 바로 열 수 있다.
 */
export function OfficeToolsHub({ initialTab = 'diagram' }: { initialTab?: OfficeToolKey }) {
  const [tab, setTab] = React.useState<OfficeToolKey>(initialTab);
  const active = TABS.find((item) => item.key === tab) ?? TABS[0];

  return (
    <div className="flex flex-col gap-4" data-testid="office-tools-hub">
      <div role="tablist" aria-label="오피스 도구" className="flex flex-wrap gap-1 border-b border-ink-3/20">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={item.key === tab}
            onClick={() => setTab(item.key)}
            className={`rounded-t-md px-4 py-2 text-sm font-medium transition-colors ${
              item.key === tab ? 'border-b-2 border-accent text-ink-1' : 'text-ink-3 hover:text-ink-1'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <p className="text-sm text-ink-3">{active.description}</p>

      {tab === 'diagram' ? <DiagramForm /> : null}
      {tab === 'chart' ? <ChartForm /> : null}
      {tab === 'report' ? <ReportForm /> : null}
    </div>
  );
}
