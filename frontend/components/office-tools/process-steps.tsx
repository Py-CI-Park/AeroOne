'use client';

import React from 'react';

export type ProcessStep = {
  label: string;
  detail: string;
};

type ProcessStepsProps = {
  title?: string;
  steps: ProcessStep[];
  // 생성이 끝났으면 true — 단계를 완료 상태로 강조한다.
  done?: boolean;
  // 실제 사용된 처리 엔진 안내(예: 'AI 제안 사용' / '규칙 기반 폴백'). 결과가 있을 때만.
  engineNote?: string;
};

/**
 * 각 스튜디오의 '처리 과정'을 눈에 보이게 하는 파이프라인 스텝퍼.
 *
 * 생성 전에는 "이렇게 처리됩니다" 안내로, 생성 후에는 각 단계를 완료로 강조하고
 * 실제 사용된 엔진(AI/규칙)을 함께 보여준다. 서버가 무엇을 어떤 순서로 처리하는지
 * 사용자가 한눈에 이해하도록 돕는다.
 */
export function ProcessSteps({ title = '처리 과정', steps, done = false, engineNote }: ProcessStepsProps) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-ink-3/25 bg-ink-3/5 px-4 py-4" data-testid="process-steps">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink-1">{title}</h3>
        <span className={`text-xs ${done ? 'text-accent' : 'text-ink-3'}`}>
          {done ? '완료' : '이렇게 처리됩니다'}
        </span>
      </div>
      <ol className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-stretch">
        {steps.map((step, index) => (
          <li key={step.label} className="flex flex-1 items-start gap-2 sm:min-w-[9rem] sm:basis-0">
            <span
              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                done ? 'bg-accent text-accent-on' : 'border border-ink-3/40 text-ink-3'
              }`}
              aria-hidden
            >
              {index + 1}
            </span>
            <span className="flex flex-col">
              <span className="text-xs font-medium text-ink-1">{step.label}</span>
              <span className="text-[11px] leading-snug text-ink-3">{step.detail}</span>
            </span>
          </li>
        ))}
      </ol>
      {done && engineNote ? (
        <p className="text-xs text-ink-3">
          엔진: <span className="font-medium text-ink-1">{engineNote}</span>
        </p>
      ) : null}
    </section>
  );
}
