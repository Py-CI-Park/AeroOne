'use client';

import React from 'react';

export type UsageWay = {
  badge: string;
  title: string;
  detail: string;
};

type UsageGuideProps = {
  intro: string;
  ways: UsageWay[];
  output: string;
};

/**
 * 각 스튜디오 상단에 '기본으로' 펼쳐져 있는 사용법 안내 패널.
 *
 * 처음 쓰는 사람이 무엇을 어떻게 넣고 무엇을 얻는지 한눈에 알도록, 입력하는 3가지 방법
 * (예제 선택 / 정형 텍스트 / 서술형)과 산출물을 카드로 상시 노출한다. 접어 둘 수 있지만
 * 기본값은 열림이라, 별도 도움말을 찾지 않아도 화면에 바로 안내가 보인다.
 */
export function UsageGuide({ intro, ways, output }: UsageGuideProps) {
  const [open, setOpen] = React.useState(true);

  return (
    <section className="rounded-xl border border-accent/20 bg-accent-soft/40 px-5 py-4" data-testid="usage-guide">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-2">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4 text-accent" aria-hidden>
            <circle cx="10" cy="10" r="7.5" />
            <path d="M10 9v4M10 6.5h.01" />
          </svg>
          <span className="text-sm font-semibold text-ink-1">사용 방법</span>
        </span>
        <svg
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          className={`h-4 w-4 text-ink-3 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        >
          <path d="M5 8l5 5 5-5" />
        </svg>
      </button>

      {open ? (
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm leading-relaxed text-ink-2">{intro}</p>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {ways.map((way) => (
              <div key={way.title} className="flex flex-col gap-1 rounded-lg border border-ink-3/15 bg-surface-raised/70 px-3 py-2.5">
                <span className="inline-flex w-fit items-center rounded-full bg-accent/10 px-2 py-0.5 text-[11px] font-semibold text-accent">
                  {way.badge}
                </span>
                <span className="text-sm font-medium text-ink-1">{way.title}</span>
                <span className="text-xs leading-snug text-ink-3">{way.detail}</span>
              </div>
            ))}
          </div>
          <p className="flex items-start gap-1.5 text-xs text-ink-3">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden>
              <path d="M4 10l4 4 8-9" />
            </svg>
            <span>{output}</span>
          </p>
        </div>
      ) : null}
    </section>
  );
}
