'use client';

import React from 'react';

type StepSectionProps = {
  n: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
};

/**
 * 번호가 붙은 입력 단계 묶음 — 폼을 "① 입력 → ② 옵션 → ③ 생성"처럼 시각적으로 구분한다.
 *
 * 각 단계에 번호 배지·제목·짧은 안내를 달아, 처음 쓰는 사람이 무엇을 어떤 순서로 채우면
 * 되는지 한눈에 알 수 있게 한다.
 */
export function StepSection({ n, title, hint, children }: StepSectionProps) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-ink-3/15 bg-surface-raised/40 px-5 py-4">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-on">
          {n}
        </span>
        <h3 className="text-sm font-semibold text-ink-1">{title}</h3>
        {hint ? <span className="text-xs text-ink-3">· {hint}</span> : null}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}
