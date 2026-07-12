'use client';

import React from 'react';

import { ChartForm } from '@/components/office-tools/chart-form';
import { DiagramForm } from '@/components/office-tools/diagram-form';
import { ReportForm } from '@/components/office-tools/report-form';

export type OfficeToolKey = 'diagram' | 'chart' | 'report';

function DiagramIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4" aria-hidden>
      <rect x="7.5" y="2.5" width="5" height="4" rx="1" />
      <rect x="2.5" y="13.5" width="5" height="4" rx="1" />
      <rect x="12.5" y="13.5" width="5" height="4" rx="1" />
      <path d="M10 6.5v3M10 9.5H5v4M10 9.5h5v4" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4" aria-hidden>
      <path d="M3 17h14" />
      <rect x="4.5" y="9" width="3" height="6" rx="0.6" />
      <rect x="8.5" y="5.5" width="3" height="9.5" rx="0.6" />
      <rect x="12.5" y="11" width="3" height="4" rx="0.6" />
    </svg>
  );
}

function ReportIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4" aria-hidden>
      <path d="M5 2.5h6l4 4V17a.5.5 0 0 1-.5.5h-9A.5.5 0 0 1 5 17z" />
      <path d="M11 2.5V6a.5.5 0 0 0 .5.5H15M7.5 10h5M7.5 13h5" />
    </svg>
  );
}

const TABS: { key: OfficeToolKey; label: string; description: string; icon: React.ReactNode }[] = [
  { key: 'diagram', label: '다이어그램', description: '설명을 입력하면 Mermaid 다이어그램(플로우/시퀀스/상태/간트)으로 그려 줍니다.', icon: <DiagramIcon /> },
  { key: 'chart', label: '차트', description: 'CSV·엑셀 데이터를 올리면 목적에 맞는 ECharts 차트로 시각화합니다.', icon: <ChartIcon /> },
  { key: 'report', label: '보고서', description: 'Markdown 을 이미지까지 내장한 단일 HTML 보고서로 변환합니다.', icon: <ReportIcon /> },
];

/**
 * 오피스 도구 허브 — 보고서·차트·다이어그램을 한 화면에서 세그먼트 탭으로 전환한다.
 *
 * 대시보드의 'Office Studio' 카드 한 장이 이 허브로 들어오고, 사용자는 아이콘이 붙은
 * 탭만 눌러 세 스튜디오를 오간다(선택 탭은 표면을 띄우고 강조 링으로 구분해 가독성을
 * 높였다). 각 탭은 기존 폼 컴포넌트를 그대로 렌더한다(예제 불러오기·처리 과정 포함).
 * 딥링크(/office-tools?tab=chart)로 특정 탭을 바로 열 수 있다.
 */
export function OfficeToolsHub({ initialTab = 'diagram' }: { initialTab?: OfficeToolKey }) {
  const [tab, setTab] = React.useState<OfficeToolKey>(initialTab);
  const active = TABS.find((item) => item.key === tab) ?? TABS[0];

  return (
    <div className="flex flex-col gap-5" data-testid="office-tools-hub">
      <div
        role="tablist"
        aria-label="Office Studio 도구"
        className="inline-flex flex-wrap gap-1.5 self-start rounded-xl bg-surface-sunken p-1.5"
      >
        {TABS.map((item) => {
          const isActive = item.key === tab;
          return (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setTab(item.key)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm transition ${
                isActive
                  ? 'bg-surface-raised font-semibold text-ink-1 shadow-sm ring-1 ring-accent/30'
                  : 'font-medium text-ink-3 hover:bg-surface-raised/60 hover:text-ink-1'
              }`}
            >
              <span className={isActive ? 'text-accent' : 'text-ink-3'}>{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-ink-3/15 bg-surface-sunken/50 px-4 py-3">
        <span className="mt-0.5 text-accent">{active.icon}</span>
        <p className="text-sm text-ink-2">{active.description}</p>
      </div>

      {tab === 'diagram' ? <DiagramForm /> : null}
      {tab === 'chart' ? <ChartForm /> : null}
      {tab === 'report' ? <ReportForm /> : null}
    </div>
  );
}
