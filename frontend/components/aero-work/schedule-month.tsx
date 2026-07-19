'use client';

import { useMemo, useState } from 'react';

import type { AeroWorkEvent } from '@/lib/api';

// Aero Work F6 월 캘린더 — 6주 그리드에 일정 블록을 얹는다(gongmuwon §7 월 보기). 이전·오늘·다음
// 으로 달을 이동한다. 이벤트는 상위(SchedulePanel)가 로드한 범위(−7~+120일)에서 필터링한다.

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

function ymd(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function ScheduleMonth({
  events,
  onSelectEvent,
}: {
  events: AeroWorkEvent[];
  onSelectEvent: (event: AeroWorkEvent) => void;
}) {
  const [monthDate, setMonthDate] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const byDay = useMemo(() => {
    const map = new Map<string, AeroWorkEvent[]>();
    for (const event of events) {
      const key = event.starts_at.slice(0, 10);
      const bucket = map.get(key);
      if (bucket) {
        bucket.push(event);
      } else {
        map.set(key, [event]);
      }
    }
    return map;
  }, [events]);

  const grid = useMemo(() => {
    const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const start = new Date(first);
    start.setDate(1 - first.getDay()); // 그리드는 그 주 일요일부터
    return Array.from({ length: 42 }, (_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      return day;
    });
  }, [monthDate]);

  const todayKey = ymd(new Date());
  const monthLabel = `${monthDate.getFullYear()}년 ${monthDate.getMonth() + 1}월`;

  const shift = (delta: number) =>
    setMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));

  return (
    <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink-1">{monthLabel}</p>
        <div className="flex gap-1">
          <button type="button" onClick={() => shift(-1)} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">이전</button>
          <button type="button" onClick={() => setMonthDate(new Date(new Date().getFullYear(), new Date().getMonth(), 1))} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">오늘</button>
          <button type="button" onClick={() => shift(1)} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">다음</button>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-7 gap-px text-center text-[11px] text-ink-3">
        {WEEKDAYS.map((day) => (
          <div key={day} className="py-1">{day}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg bg-line-subtle">
        {grid.map((day) => {
          const key = ymd(day);
          const inMonth = day.getMonth() === monthDate.getMonth();
          const dayEvents = byDay.get(key) ?? [];
          return (
            <div
              key={key}
              className={`min-h-[76px] bg-surface-base p-1 ${inMonth ? '' : 'opacity-40'} ${key === todayKey ? 'ring-1 ring-inset ring-accent' : ''}`}
            >
              <div className="text-right text-[11px] text-ink-3">{day.getDate()}</div>
              <div className="mt-0.5 space-y-0.5">
                {dayEvents.slice(0, 3).map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    onClick={() => onSelectEvent(event)}
                    className="block w-full truncate rounded bg-accent-soft px-1 py-0.5 text-left text-[10px] text-accent hover:bg-accent hover:text-accent-on"
                    title={event.title}
                  >
                    {event.all_day ? '' : `${event.starts_at.slice(11, 16)} `}
                    {event.remind_before_minutes != null ? '🔔' : ''}{event.title}
                  </button>
                ))}
                {dayEvents.length > 3 ? <div className="text-[10px] text-ink-3">외 {dayEvents.length - 3}</div> : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
