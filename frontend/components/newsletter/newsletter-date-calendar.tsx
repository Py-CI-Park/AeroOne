'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';

import type { NewsletterCalendarEntry } from '@/lib/types';

type CalendarEntry = NewsletterCalendarEntry & {
  parsedDate: Date;
};

function monthLabel(date: Date) {
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월`;
}

export function NewsletterDateCalendar({
  entries,
  selectedSlug,
}: {
  entries: NewsletterCalendarEntry[];
  selectedSlug?: string;
}) {
  const parsedEntries = useMemo<CalendarEntry[]>(
    () =>
      entries.map((entry) => ({
        ...entry,
        parsedDate: new Date(`${entry.date}T00:00:00`),
      })),
    [entries],
  );

  const monthKeys = useMemo(
    () =>
      [...new Set(parsedEntries.map((entry) => `${entry.parsedDate.getFullYear()}-${entry.parsedDate.getMonth()}`))].sort(
        (left, right) => (left < right ? 1 : -1),
      ),
    [parsedEntries],
  );

  const selectedEntry = parsedEntries.find((entry) => entry.slug === selectedSlug) ?? parsedEntries[0];
  const initialMonthKey =
    selectedEntry != null ? `${selectedEntry.parsedDate.getFullYear()}-${selectedEntry.parsedDate.getMonth()}` : monthKeys[0];
  const initialMonthIndex = Math.max(
    0,
    monthKeys.findIndex((key) => key === initialMonthKey),
  );

  const [monthIndex, setMonthIndex] = useState(initialMonthIndex);
  const [open, setOpen] = useState(true);
  const [year, month] = (monthKeys[monthIndex] ?? monthKeys[0] ?? `${new Date().getFullYear()}-${new Date().getMonth()}`)
    .split('-')
    .map(Number);
  const currentMonthDate = new Date(year, month, 1);

  const entryMap = new Map(
    parsedEntries
      .filter((entry) => entry.parsedDate.getFullYear() === year && entry.parsedDate.getMonth() === month)
      .map((entry) => [entry.parsedDate.getDate(), entry]),
  );

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: Array<{ day?: number; entry?: CalendarEntry }> = [];

  for (let index = 0; index < firstDay; index += 1) {
    cells.push({});
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push({ day, entry: entryMap.get(day) });
  }

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/95 p-3 text-slate-100 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Calendar</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">{monthLabel(currentMonthDate)}</h2>
          <p className="mt-1 text-xs text-slate-400">발행일을 선택하면 해당 뉴스레터 미리보기로 이동합니다.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setMonthIndex((current) => Math.min(current + 1, monthKeys.length - 1))}
            disabled={monthIndex >= monthKeys.length - 1}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-600 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            이전 달
          </button>
          <button
            type="button"
            onClick={() => setMonthIndex((current) => Math.max(current - 1, 0))}
            disabled={monthIndex <= 0}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-600 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-40"
          >
            다음 달
          </button>
          <button
            type="button"
            aria-expanded={open}
            aria-controls="newsletter-calendar-grid"
            onClick={() => setOpen((current) => !current)}
            className="rounded-lg border border-blue-500/40 bg-blue-950/40 px-3 py-2 text-sm text-blue-100 transition hover:border-blue-400/60 hover:bg-blue-950"
          >
            {open ? '달력 접기' : '달력 펼치기'}
          </button>
        </div>
      </div>

      <div id="newsletter-calendar-grid" data-testid="newsletter-calendar-grid" hidden={!open} className="mt-4">
        <div className="mb-2 grid grid-cols-7 gap-2 text-center text-xs font-medium text-slate-500">
          {['일', '월', '화', '수', '목', '금', '토'].map((label) => (
            <div key={label}>{label}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-2">
          {cells.map((cell, index) => {
            if (!cell.day) {
              return <div key={`empty-${index}`} className="h-14 rounded-xl bg-slate-950/30" />;
            }
            if (!cell.entry) {
              return (
                <div
                  key={`inactive-${cell.day}`}
                  className="flex h-14 items-center justify-center rounded-xl border border-slate-800/70 bg-slate-950/60 text-sm text-slate-600"
                >
                  {cell.day}
                </div>
              );
            }

            const isSelected = cell.entry.slug === selectedSlug;
            return (
              <Link
                key={cell.entry.slug}
                href={`/newsletters?slug=${cell.entry.slug}`}
                className={`flex h-14 flex-col items-center justify-center rounded-xl border text-sm transition ${
                  isSelected
                    ? 'border-blue-500/50 bg-blue-950/40 text-slate-50 shadow-[0_0_0_1px_rgba(59,130,246,0.25)]'
                    : 'border-emerald-500/30 bg-slate-950 text-slate-100 hover:border-emerald-400/50 hover:bg-slate-900'
                }`}
                title={cell.entry.title}
              >
                <span className="font-semibold">{cell.day}</span>
                <span className={`text-[10px] uppercase ${isSelected ? 'text-blue-100' : 'text-emerald-300'}`}>
                  {cell.entry.source_type}
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
