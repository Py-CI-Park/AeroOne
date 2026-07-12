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
    <div className="flex flex-wrap items-center gap-2" data-testid="sample-picker">
      <span className="text-xs font-medium text-ink-3">예제</span>
      {samples.map((sample) => (
        <button
          key={sample.key}
          type="button"
          disabled={disabled}
          title={sample.description}
          onClick={() => onPick(sample)}
          className="rounded-full border border-ink-3/30 px-3 py-1 text-xs text-ink-1 transition hover:border-accent/50 hover:bg-accent-soft disabled:opacity-50"
        >
          {sample.title}
        </button>
      ))}
    </div>
  );
}
