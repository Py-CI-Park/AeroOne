'use client';

import React from 'react';

type StepSectionProps = {
  n: number;
  title: string;
  hint?: string;
  done?: boolean;
  children: React.ReactNode;
};

/**
 * 번호가 붙은 입력 단계 묶음 — 폼을 "① 입력 → ② 옵션 → ③ 생성"처럼 시각적으로 구분한다.
 *
 * 각 단계에 번호 배지·제목·짧은 안내를 달아, 처음 쓰는 사람이 무엇을 어떤 순서로 채우면
 * 되는지 한눈에 알 수 있게 한다. 왼쪽 강조선과 큰 번호 배지로 단계 경계를 뚜렷이 하고,
 * ``done`` 이면 배지를 체크로 바꿔 완료를 표시한다.
 */
export function StepSection({ n, title, hint, done = false, children }: StepSectionProps) {
  return (
    <section className="relative flex flex-col gap-3 rounded-xl border border-ink-3/15 bg-surface-raised/40 pl-6 pr-5 py-4">
      <span
        aria-hidden
        className={`absolute left-0 top-4 bottom-4 w-1 rounded-full ${done ? 'bg-accent' : 'bg-accent/25'}`}
      />
      <div className="flex items-center gap-2.5">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
            done ? 'bg-accent text-accent-on' : 'bg-accent/15 text-accent'
          }`}
        >
          {done ? (
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.2" className="h-4 w-4" aria-hidden>
              <path d="M4 10l4 4 8-9" />
            </svg>
          ) : (
            n
          )}
        </span>
        <h3 className="text-sm font-semibold text-ink-1">{title}</h3>
        {hint ? <span className="text-xs text-ink-3">· {hint}</span> : null}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  );
}
