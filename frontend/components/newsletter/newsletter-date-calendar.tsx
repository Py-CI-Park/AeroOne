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
  const [isOpen, setIsOpen] = useState(false);
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
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">발행 캘린더</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">{monthLabel(currentMonthDate)}</h2>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setIsOpen((current) => !current)}
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            <span aria-hidden="true">📅</span>
            {isOpen ? '달력 닫기' : '달력 열기'}
          </button>
          <button
            type="button"
            onClick={() => setMonthIndex((current) => Math.min(current + 1, monthKeys.length - 1))}
            disabled={monthIndex >= monthKeys.length - 1}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            이전 달
          </button>
          <button
            type="button"
            onClick={() => setMonthIndex((current) => Math.max(current - 1, 0))}
            disabled={monthIndex <= 0}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            다음 달
          </button>
        </div>
      </div>

      {isOpen ? (
        <div className="mt-4">
          <div className="mb-2 grid grid-cols-7 gap-2 text-center text-xs font-medium text-slate-400">
            {['일', '월', '화', '수', '목', '금', '토'].map((label) => (
              <div key={label}>{label}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-2">
            {cells.map((cell, index) => {
              if (!cell.day) {
                return <div key={`empty-${index}`} className="h-14 rounded-lg bg-slate-50" />;
              }
              if (!cell.entry) {
                return (
                  <div key={`inactive-${cell.day}`} className="flex h-14 items-center justify-center rounded-lg border border-dashed border-slate-200 text-sm text-slate-300">
                    {cell.day}
                  </div>
                );
              }

              const isSelected = cell.entry.slug === selectedSlug;
              return (
                <Link
                  key={cell.entry.slug}
                  href={`/newsletters?slug=${cell.entry.slug}`}
                  className={`flex h-14 flex-col items-center justify-center rounded-lg border text-sm transition ${
                    isSelected
                      ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
                      : 'border-blue-200 bg-blue-50 text-blue-700 hover:border-blue-300 hover:bg-blue-100'
                  }`}
                  title={cell.entry.title}
                >
                  <span className="font-semibold">{cell.day}</span>
                  <span className={`text-[10px] uppercase ${isSelected ? 'text-slate-200' : 'text-blue-500'}`}>{cell.entry.source_type}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}
