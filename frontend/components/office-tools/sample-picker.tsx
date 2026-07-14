'use client';

import React from 'react';

import { fetchOfficeSamples } from '@/lib/api';
import type { OfficeSample } from '@/lib/types';

type SamplePickerProps = {
  tool: OfficeSample['tool'];
  onPick: (sample: OfficeSample) => void;
  disabled?: boolean;
};

/**
 * 도구별 '예제' 칩 목록 — 마운트 시 전체 샘플을 한 번 받아 해당 도구만 칩으로 보여 준다.
 *
 * 사용자가 칩을 누르면 그 샘플의 내용·힌트를 그대로 상위 폼에 전달(onPick)해 즉시 채운다.
 * 백엔드가 도구별 여러 종(플로우/시퀀스/…, 막대/선/파이/…)을 제공하므로, 사용자는 여러
 * 데이터 형식·유형을 골라 바로 실행해 볼 수 있다. 조회 실패 시 칩을 숨긴다(폼은 정상 동작).
 */
export function SamplePicker({ tool, onPick, disabled }: SamplePickerProps) {
  const [samples, setSamples] = React.useState<OfficeSample[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    fetchOfficeSamples()
      .then((all) => {
        if (!cancelled) setSamples(all.filter((sample) => sample.tool === tool));
      })
      .catch(() => {
        if (!cancelled) setSamples([]);
      });
    return () => {
      cancelled = true;
    };
  }, [tool]);

  if (samples.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-accent/25 bg-accent-soft/30 px-3 py-3" data-testid="sample-picker">
      <span className="flex items-center gap-1.5 text-xs font-semibold text-accent">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden>
          <path d="M10 2l1.9 4.6L17 7l-3.6 3.2L14.4 15 10 12.6 5.6 15l1-4.8L3 7l5.1-.4z" />
        </svg>
        예제 — 클릭하면 바로 생성됩니다
      </span>
      <div className="flex flex-wrap gap-2">
        {samples.map((sample) => (
          <button
            key={sample.key}
            type="button"
            disabled={disabled}
            title={sample.description}
            onClick={() => onPick(sample)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-accent/40 bg-surface-raised px-3.5 py-2 text-sm font-medium text-ink-1 shadow-sm transition hover:-translate-y-0.5 hover:border-accent hover:bg-accent-soft hover:text-accent disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3 text-accent" aria-hidden>
              <path d="M6 4l10 6-10 6z" />
            </svg>
            {sample.title}
          </button>
        ))}
      </div>
    </div>
  );
}
