'use client';

import { useEffect, useState } from 'react';

import type { AeroWorkEvent } from '@/lib/api';

// Aero Work F6 사전 알림 — 알림이 설정된 일정이 리드타임 안에 들면 상단 배너로 안내한다
// (gongmuwon §7.3, 폐쇄망이라 인앱 전용). 30초마다 재확인하고, '확인'하면 그 일정은 숨긴다.

export function ReminderBanner({ events }: { events: AeroWorkEvent[] }) {
  const [, forceTick] = useState(0);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());

  useEffect(() => {
    const id = setInterval(() => forceTick((value) => value + 1), 30000);
    return () => clearInterval(id);
  }, []);

  const now = Date.now();
  const due = events
    .filter((event) => event.remind_before_minutes != null && !dismissed.has(event.id))
    .map((event) => {
      const start = new Date(event.starts_at).getTime();
      return { event, start, remindAt: start - (event.remind_before_minutes as number) * 60000 };
    })
    .filter((item) => now >= item.remindAt && now < item.start)
    .sort((a, b) => a.start - b.start);

  if (due.length === 0) {
    return null;
  }

  const { event, start } = due[0];
  const minutesLeft = Math.max(0, Math.round((start - now) / 60000));

  return (
    <div className="flex items-center gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-700">
      <span>
        🔔 곧 시작: <span className="font-semibold">{event.title}</span> ({minutesLeft}분 후)
        {due.length > 1 ? <span className="ml-1 text-xs">외 {due.length - 1}건</span> : null}
      </span>
      <button
        type="button"
        onClick={() => setDismissed((prev) => new Set(prev).add(event.id))}
        className="ml-auto rounded px-2 py-0.5 text-xs font-medium hover:bg-amber-500/20"
      >
        확인
      </button>
    </div>
  );
}
