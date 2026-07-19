'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import {
  createAeroWorkEvent,
  deleteAeroWorkEvent,
  fetchAeroWorkEvents,
  updateAeroWorkEvent,
  type AeroWorkEvent,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work P4 일정 — 사용자별 개인 캘린더(아젠다 뷰 + 생성/수정/삭제). 향후 홈 브리핑이
// 이 데이터를 소비한다. 시각은 datetime-local(로컬 naive)로 주고받으며 백엔드가 정규화한다.

type EventForm = {
  title: string;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  location: string;
  notes: string;
};

const EMPTY_FORM: EventForm = { title: '', starts_at: '', ends_at: '', all_day: false, location: '', notes: '' };

function toInputValue(iso: string | null): string {
  return iso ? iso.slice(0, 16) : '';
}

function formatDateHeading(dateKey: string): string {
  const date = new Date(`${dateKey}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return dateKey;
  }
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][date.getDay()];
  return `${dateKey.slice(0, 4)}. ${dateKey.slice(5, 7)}. ${dateKey.slice(8, 10)} (${weekday})`;
}

export function SchedulePanel() {
  const [events, setEvents] = useState<AeroWorkEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<EventForm>(EMPTY_FORM);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const now = new Date();
      const start = new Date(now.getTime() - 7 * 86400000).toISOString().slice(0, 19);
      const end = new Date(now.getTime() + 120 * 86400000).toISOString().slice(0, 19);
      const data = await fetchAeroWorkEvents({ start, end });
      setEvents(data.events);
      setError(null);
    } catch {
      setError('일정을 불러오지 못했음. 로그인 상태를 확인할 것.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
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
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [events]);

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
  };

  const startEdit = (event: AeroWorkEvent) => {
    setEditingId(event.id);
    setForm({
      title: event.title,
      starts_at: toInputValue(event.starts_at),
      ends_at: toInputValue(event.ends_at),
      all_day: event.all_day,
      location: event.location,
      notes: event.notes,
    });
  };

  const handleSubmit = async (submitEvent: FormEvent) => {
    submitEvent.preventDefault();
    if (!form.title.trim() || !form.starts_at) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        title: form.title.trim(),
        starts_at: form.starts_at,
        ends_at: form.ends_at ? form.ends_at : null,
        all_day: form.all_day,
        location: form.location.trim(),
        notes: form.notes.trim(),
      };
      if (editingId !== null) {
        await updateAeroWorkEvent(editingId, payload, getCsrfCookie());
      } else {
        await createAeroWorkEvent(payload, getCsrfCookie());
      }
      resetForm();
      await load();
    } catch {
      setError('저장 실패. 종료 시각이 시작보다 앞서지 않는지 확인할 것.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (event: AeroWorkEvent) => {
    setError(null);
    try {
      await deleteAeroWorkEvent(event.id, getCsrfCookie());
      if (editingId === event.id) {
        resetForm();
      }
      await load();
    } catch {
      setError('삭제 실패.');
    }
  };

  return (
    <div className="mt-4 space-y-6">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}

      <form onSubmit={handleSubmit} className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">{editingId !== null ? '일정 수정' : '새 일정'}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <input
            value={form.title}
            onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
            placeholder="제목"
            className="sm:col-span-2 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <label className="flex flex-col gap-1 text-xs text-ink-3">
            시작
            <input
              type="datetime-local"
              value={form.starts_at}
              onChange={(event) => setForm((prev) => ({ ...prev, starts_at: event.target.value }))}
              className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-ink-3">
            종료(선택)
            <input
              type="datetime-local"
              value={form.ends_at}
              onChange={(event) => setForm((prev) => ({ ...prev, ends_at: event.target.value }))}
              className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
            />
          </label>
          <input
            value={form.location}
            onChange={(event) => setForm((prev) => ({ ...prev, location: event.target.value }))}
            placeholder="장소(선택)"
            className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              checked={form.all_day}
              onChange={(event) => setForm((prev) => ({ ...prev, all_day: event.target.checked }))}
            />
            종일
          </label>
          <textarea
            value={form.notes}
            onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
            placeholder="메모(선택)"
            rows={2}
            className="sm:col-span-2 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="submit"
            disabled={saving || !form.title.trim() || !form.starts_at}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {saving ? '저장 중…' : editingId !== null ? '수정 저장' : '일정 추가'}
          </button>
          {editingId !== null ? (
            <button type="button" onClick={resetForm} className="rounded-lg border border-line-subtle bg-surface-raised px-4 py-2 text-sm text-ink-2 hover:bg-surface-sunken">
              취소
            </button>
          ) : null}
        </div>
      </form>

      <div>
        <p className="text-sm font-semibold text-ink-1">다가오는 일정</p>
        {loading ? (
          <p className="mt-2 text-sm text-ink-3">불러오는 중…</p>
        ) : grouped.length === 0 ? (
          <p className="mt-2 rounded-lg border border-dashed border-line-subtle bg-surface-base px-3 py-4 text-sm text-ink-3">
            예정된 일정이 없음. 위에서 새 일정을 추가할 것.
          </p>
        ) : (
          <div className="mt-2 space-y-4">
            {grouped.map(([dateKey, dayEvents]) => (
              <div key={dateKey}>
                <p className="text-xs font-semibold uppercase tracking-wide text-accent">{formatDateHeading(dateKey)}</p>
                <ul className="mt-1 space-y-1">
                  {dayEvents.map((event) => (
                    <li key={event.id} className="flex items-start gap-3 rounded-lg border border-line-subtle bg-surface-base px-3 py-2">
                      <span className="w-14 shrink-0 pt-0.5 text-xs font-medium text-ink-2">
                        {event.all_day ? '종일' : event.starts_at.slice(11, 16)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-ink-1">{event.title}</p>
                        {event.location ? <p className="text-xs text-ink-3">📍 {event.location}</p> : null}
                        {event.notes ? <p className="mt-0.5 whitespace-pre-wrap text-xs text-ink-2">{event.notes}</p> : null}
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <button type="button" onClick={() => startEdit(event)} className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken">수정</button>
                        <button type="button" onClick={() => void handleDelete(event)} className="rounded px-2 py-1 text-xs text-rose-600 hover:bg-rose-500/10">삭제</button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
