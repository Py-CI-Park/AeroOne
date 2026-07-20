'use client';

import { useMemo, useState } from 'react';

import type { AeroWorkEvent } from '@/lib/api';

// Aero Work 주/일 시간축 뷰 — 07~20시 시간축에 일정 블록을 배치한다(gongmuwon §7 주/일 보기).
// days=7 이면 주(일요일 시작), days=1 이면 일 보기. 종일 일정은 상단 스트립에 표시한다.

const HOURS = Array.from({ length: 14 }, (_, index) => 7 + index); // 07~20시
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

function ymd(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function ScheduleWeek({
  events,
  days,
  onSelectEvent,
}: {
  events: AeroWorkEvent[];
  days: 7 | 1;
  onSelectEvent: (event: AeroWorkEvent) => void;
}) {
  const [anchor, setAnchor] = useState(() => {
    const now = new Date();
    const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (days === 7) {
      base.setDate(base.getDate() - base.getDay()); // 주는 일요일 시작
    }
    return base;
  });

  const columns = useMemo(
    () =>
      Array.from({ length: days }, (_, index) => {
        const day = new Date(anchor);
        day.setDate(anchor.getDate() + index);
        return day;
      }),
    [anchor, days],
  );

  const byDay = useMemo(() => {
    const map = new Map<string, AeroWorkEvent[]>();
    for (const event of events) {
      const key = event.starts_at.slice(0, 10);
      (map.get(key) ?? map.set(key, []).get(key)!).push(event);
    }
    return map;
  }, [events]);

  const todayKey = ymd(new Date());
  const shift = (delta: number) =>
    setAnchor((prev) => {
      const next = new Date(prev);
      next.setDate(prev.getDate() + delta * days);
      return next;
    });
  const goToday = () =>
    setAnchor(() => {
      const now = new Date();
      const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (days === 7) {
        base.setDate(base.getDate() - base.getDay());
      }
      return base;
    });

  const rangeLabel =
    days === 7
      ? `${ymd(columns[0])} ~ ${ymd(columns[columns.length - 1])}`
      : `${ymd(columns[0])} (${WEEKDAYS[columns[0].getDay()]})`;

  return (
    <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink-1">{rangeLabel}</p>
        <div className="flex gap-1">
          <button type="button" onClick={() => shift(-1)} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">이전</button>
          <button type="button" onClick={goToday} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">오늘</button>
          <button type="button" onClick={() => shift(1)} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">다음</button>
        </div>
      </div>

      <div className="mt-2 overflow-x-auto">
        <div className="min-w-[560px]">
          {/* 요일 헤더 + 종일 스트립 */}
          <div className="grid" style={{ gridTemplateColumns: `48px repeat(${days}, 1fr)` }}>
            <div />
            {columns.map((day) => {
              const key = ymd(day);
              const allDay = (byDay.get(key) ?? []).filter((event) => event.all_day);
              return (
                <div key={key} className={`border-b border-line-subtle px-1 pb-1 text-center ${key === todayKey ? 'text-accent' : 'text-ink-2'}`}>
                  <p className="text-xs font-semibold">{`${day.getMonth() + 1}/${day.getDate()} (${WEEKDAYS[day.getDay()]})`}</p>
                  {allDay.map((event) => (
                    <button
                      key={event.id}
                      type="button"
                      onClick={() => onSelectEvent(event)}
                      className="mt-0.5 block w-full truncate rounded bg-accent-soft px-1 text-[10px] text-accent"
                      title={event.title}
                    >
                      종일 {event.remind_before_minutes != null ? '🔔' : ''}{event.title}
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
          {/* 시간축 */}
          {HOURS.map((hour) => (
            <div key={hour} className="grid border-b border-line-subtle/60" style={{ gridTemplateColumns: `48px repeat(${days}, 1fr)` }}>
              <div className="py-1 pr-2 text-right text-[10px] text-ink-3">{String(hour).padStart(2, '0')}:00</div>
              {columns.map((day) => {
                const key = ymd(day);
                const cellEvents = (byDay.get(key) ?? []).filter(
                  (event) => !event.all_day && Number(event.starts_at.slice(11, 13)) === hour,
                );
                return (
                  <div key={`${key}-${hour}`} className={`min-h-[26px] border-l border-line-subtle/60 p-0.5 ${key === todayKey ? 'bg-accent-soft/30' : ''}`}>
                    {cellEvents.map((event) => (
                      <button
                        key={event.id}
                        type="button"
                        onClick={() => onSelectEvent(event)}
                        className="block w-full truncate rounded bg-accent-soft px-1 py-0.5 text-left text-[10px] text-accent hover:bg-accent hover:text-accent-on"
                        title={event.title}
                      >
                        {event.starts_at.slice(11, 16)} {event.remind_before_minutes != null ? '🔔' : ''}{event.title}
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
