'use client';

import { useEffect, useState } from 'react';

import {
  fetchAeroWorkActivity,
  fetchAeroWorkEvents,
  fetchAiStatus,
  fetchKnowledgeFolders,
  type AeroWorkActivity,
  type AeroWorkEvent,
  type KnowledgeFolder,
} from '@/lib/api';
import type { AiStatusResponse } from '@/lib/types';

// Aero Work F7 우측 컨텍스트 패널 — 업무 엔진 상태·가까운 일정·지식 색인 요약·최근 실행기록을
// 한눈에(gongmuwon §3.2 우측 패널). 기존 조회 API 만 조합하며, 항목 클릭 시 해당 탭으로 이동한다.

const AI_STATUS_META: Record<AiStatusResponse['status'], { label: string; dot: string }> = {
  ok: { label: '정상', dot: 'bg-emerald-500' },
  disabled: { label: '비활성', dot: 'bg-ink-3' },
  unavailable: { label: '연결 불가', dot: 'bg-rose-500' },
  model_missing: { label: '모델 없음', dot: 'bg-amber-500' },
};

function eventWhen(event: AeroWorkEvent): string {
  const date = event.starts_at.slice(5, 10).replace('-', '.');
  return event.all_day ? `${date} 종일` : `${date} ${event.starts_at.slice(11, 16)}`;
}

export function AeroWorkContextPanel({ onNavigate }: { onNavigate: (view: string) => void }) {
  const [events, setEvents] = useState<AeroWorkEvent[]>([]);
  const [activities, setActivities] = useState<AeroWorkActivity[]>([]);
  const [folders, setFolders] = useState<KnowledgeFolder[]>([]);
  const [ai, setAi] = useState<AiStatusResponse | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString().slice(0, 19);
      const end = new Date(now.getTime() + 7 * 86400000).toISOString().slice(0, 19);
      const [eventsResult, activityResult, foldersResult, statusResult] = await Promise.all([
        fetchAeroWorkEvents({ start, end }).catch(() => ({ events: [] as AeroWorkEvent[] })),
        fetchAeroWorkActivity(6).catch(() => ({ activities: [] as AeroWorkActivity[] })),
        fetchKnowledgeFolders().catch(() => ({ folders: [] as KnowledgeFolder[] })),
        fetchAiStatus().catch(() => null),
      ]);
      if (!alive) {
        return;
      }
      setEvents(eventsResult.events);
      setActivities(activityResult.activities);
      setFolders(foldersResult.folders);
      setAi(statusResult);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const aiMeta = ai ? AI_STATUS_META[ai.status] : null;
  const chunkTotal = folders.reduce((sum, folder) => sum + folder.chunk_count, 0);

  return (
    <aside className="space-y-3 text-sm">
      <div className="rounded-xl border border-line-subtle bg-surface-raised p-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">업무 엔진</p>
        <div className="mt-1 flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${aiMeta ? aiMeta.dot : 'bg-ink-3'}`} aria-hidden />
          <span className="text-xs text-ink-1">{aiMeta ? aiMeta.label : '확인 중…'}</span>
          {ai ? <span className="ml-auto truncate font-mono text-[10px] text-ink-3">{ai.model}</span> : null}
        </div>
      </div>

      <button
        type="button"
        onClick={() => onNavigate('schedule')}
        className="w-full rounded-xl border border-line-subtle bg-surface-raised p-3 text-left"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">가까운 일정</p>
        {events.length === 0 ? (
          <p className="mt-1 text-xs text-ink-3">이번 주 일정 없음</p>
        ) : (
          <ul className="mt-1 space-y-1">
            {events.slice(0, 4).map((event) => (
              <li key={event.id} className="flex gap-2 text-xs text-ink-2">
                <span className="shrink-0 font-medium text-ink-1">{eventWhen(event)}</span>
                <span className="truncate">{event.remind_before_minutes != null ? '🔔' : ''}{event.title}</span>
              </li>
            ))}
          </ul>
        )}
      </button>

      <button
        type="button"
        onClick={() => onNavigate('knowledge')}
        className="w-full rounded-xl border border-line-subtle bg-surface-raised p-3 text-left"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">지식 색인</p>
        <p className="mt-1 text-xs text-ink-2">{folders.length}개 폴더 · {chunkTotal.toLocaleString()}개 청크</p>
      </button>

      <button
        type="button"
        onClick={() => onNavigate('log')}
        className="w-full rounded-xl border border-line-subtle bg-surface-raised p-3 text-left"
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">최근 실행기록</p>
        {activities.length === 0 ? (
          <p className="mt-1 text-xs text-ink-3">아직 없음</p>
        ) : (
          <ul className="mt-1 space-y-1">
            {activities.slice(0, 5).map((activity) => (
              <li key={activity.id} className="truncate text-xs text-ink-2">{activity.summary}</li>
            ))}
          </ul>
        )}
      </button>
    </aside>
  );
}
