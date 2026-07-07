'use client';

import { useEffect, useState } from 'react';

export function formatKoreanDateTime(date: Date) {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function KoreanClock() {
  const [current, setCurrent] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setCurrent(new Date());
    update();
    const intervalId = window.setInterval(update, 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  return (
    <time
      dateTime={current?.toISOString()}
      aria-label="한국 시간"
      className="hidden rounded-full border border-line-subtle bg-surface-sunken px-3 py-1 font-mono text-xs text-ink-2 md:inline-flex"
    >
      한국 시간 {current ? `${formatKoreanDateTime(current)} KST` : '동기화 중'}
    </time>
  );
}
