'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';

import type { NewsletterTheme } from '@/lib/theme';
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
  theme = 'light',
  defaultOpen = false,
}: {
  entries: NewsletterCalendarEntry[];
  selectedSlug?: string;
  theme?: NewsletterTheme;
  defaultOpen?: boolean;
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
  const [open, setOpen] = useState(defaultOpen);
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

  const navButtonClass =
    'rounded border border-line-subtle bg-surface-elevated px-2.5 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1 disabled:cursor-not-allowed disabled:opacity-40';

  return (
    <section className="h-full rounded-lg border border-line-subtle bg-surface-raised p-4 text-ink-1">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-ink-3">Calendar</p>
          <h2 className="mt-1 text-lg font-semibold text-ink-1">{monthLabel(currentMonthDate)}</h2>
          <p className="mt-1 text-xs text-ink-3">발행일을 선택하면 해당 뉴스레터 미리보기로 이동합니다.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {open ? (
            <>
              <button
                type="button"
                onClick={() => setMonthIndex((current) => Math.min(current + 1, monthKeys.length - 1))}
                disabled={monthIndex >= monthKeys.length - 1}
                className={navButtonClass}
              >
                이전 달
              </button>
              <button
                type="button"
                onClick={() => setMonthIndex((current) => Math.max(current - 1, 0))}
                disabled={monthIndex <= 0}
                className={navButtonClass}
              >
                다음 달
              </button>
            </>
          ) : null}
          <button
            type="button"
            aria-expanded={open}
            aria-controls="newsletter-calendar-grid"
            onClick={() => setOpen((current) => !current)}
            className="rounded border border-accent-soft bg-accent-soft px-2.5 py-1.5 text-sm text-accent transition-colors hover:bg-surface-sunken"
          >
            {open ? '달력 접기' : '달력 펼치기'}
          </button>
        </div>
      </div>

      <div id="newsletter-calendar-grid" data-testid="newsletter-calendar-grid" hidden={!open} className="mt-4">
        <div className="mb-2 grid grid-cols-7 gap-1 text-center font-mono text-xs text-ink-3">
          {['일', '월', '화', '수', '목', '금', '토'].map((label) => (
            <div key={label}>{label}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {cells.map((cell, index) => {
            if (!cell.day) {
              return <div key={`empty-${index}`} className="h-9 rounded-sm" />;
            }
            if (!cell.entry) {
              return (
                <div
                  key={`inactive-${cell.day}`}
                  className="flex h-9 items-center justify-center rounded-sm font-mono text-sm text-ink-4"
                >
                  {cell.day}
                </div>
              );
            }

            const isSelected = cell.entry.slug === selectedSlug;

            return (
              <Link
                key={cell.entry.slug}
                href={`/newsletters?slug=${cell.entry.slug}&theme=${theme}`}
                className={`flex h-9 items-center justify-center rounded-sm font-mono text-sm font-medium transition-colors ${
                  isSelected
                    ? 'bg-accent text-accent-on'
                    : 'bg-accent-soft text-accent hover:bg-surface-sunken'
                }`}
                title={`${cell.entry.title} (${cell.entry.source_type.toUpperCase()})`}
              >
                {cell.day}
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
