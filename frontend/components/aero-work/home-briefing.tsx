'use client';

import { useEffect, useState } from 'react';

import {
  fetchAeroWorkChatSessions,
  fetchAeroWorkEvents,
  fetchKnowledgeFolders,
  type AeroWorkChatSession,
  type AeroWorkEvent,
  type KnowledgeFolder,
} from '@/lib/api';

// Aero Work P4 홈 '오늘의 브리핑' — 일정(다가오는 7일)과 지식폴더 색인 상태를 실데이터로
// 요약해 홈에서 한눈에 보여주고, 클릭하면 해당 탭으로 이동한다. AI 팩 없이 기존 자산만 조합.

function todayLabel(): string {
  const now = new Date();
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][now.getDay()];
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}. ${month}. ${day} (${weekday})`;
}

function eventWhen(event: AeroWorkEvent): string {
  if (event.all_day) {
    return `${event.starts_at.slice(5, 10).replace('-', '.')} 종일`;
  }
  return `${event.starts_at.slice(5, 10).replace('-', '.')} ${event.starts_at.slice(11, 16)}`;
}

export function HomeBriefing({
  onOpenSchedule,
  onOpenKnowledge,
  onOpenChat,
}: {
  onOpenSchedule: () => void;
  onOpenKnowledge: () => void;
  onOpenChat: () => void;
}) {
  const [events, setEvents] = useState<AeroWorkEvent[]>([]);
  const [folders, setFolders] = useState<KnowledgeFolder[]>([]);
  const [lastSession, setLastSession] = useState<AeroWorkChatSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString().slice(0, 19);
        const end = new Date(now.getTime() + 7 * 86400000).toISOString().slice(0, 19);
        const [eventsResult, foldersResult, sessionsResult] = await Promise.all([
          fetchAeroWorkEvents({ start, end }).catch(() => ({ events: [] as AeroWorkEvent[] })),
          fetchKnowledgeFolders().catch(() => ({ folders: [] as KnowledgeFolder[] })),
          fetchAeroWorkChatSessions().catch(() => ({ sessions: [] as AeroWorkChatSession[] })),
        ]);
        if (!alive) {
          return;
        }
        setEvents(eventsResult.events);
        setFolders(foldersResult.folders);
        setLastSession(sessionsResult.sessions[0] ?? null);
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const chunkTotal = folders.reduce((sum, folder) => sum + folder.chunk_count, 0);

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line-subtle bg-gradient-to-br from-accent-soft to-surface-base p-5">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-accent">오늘의 브리핑</p>
        <p className="mt-1 text-lg font-semibold text-ink-1">{todayLabel()}</p>
        <p className="mt-1 text-sm text-ink-2">일정과 지식폴더를 한눈에 보고 바로 이어서 일하세요.</p>
        {lastSession ? (
          <button
            type="button"
            onClick={onOpenChat}
            className="mt-2 inline-flex items-center gap-1 rounded-full bg-surface-raised px-3 py-1 text-xs font-medium text-accent hover:bg-accent hover:text-accent-on"
          >
            ▶ 이어서 하기: <span className="max-w-[220px] truncate">{lastSession.title}</span>
          </button>
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={onOpenSchedule}
          className="flex flex-col gap-2 rounded-xl border border-line-subtle bg-surface-base p-4 text-left transition-shadow hover:shadow-md"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-ink-1">
            <span aria-hidden>📅</span>다가오는 일정
          </span>
          {loading ? (
            <span className="text-xs text-ink-3">불러오는 중…</span>
          ) : events.length === 0 ? (
            <span className="text-xs text-ink-2">이번 주 예정된 일정이 없음. 눌러서 추가.</span>
          ) : (
            <ul className="space-y-1">
              {events.slice(0, 4).map((event) => (
                <li key={event.id} className="flex gap-2 text-xs text-ink-2">
                  <span className="shrink-0 font-medium text-ink-1">{eventWhen(event)}</span>
                  <span className="truncate">{event.title}</span>
                </li>
              ))}
              {events.length > 4 ? <li className="text-[11px] text-ink-3">외 {events.length - 4}건</li> : null}
            </ul>
          )}
        </button>

        <button
          type="button"
          onClick={onOpenKnowledge}
          className="flex flex-col gap-2 rounded-xl border border-line-subtle bg-surface-base p-4 text-left transition-shadow hover:shadow-md"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-ink-1">
            <span aria-hidden>📚</span>내 지식폴더
          </span>
          {loading ? (
            <span className="text-xs text-ink-3">불러오는 중…</span>
          ) : (
            <span className="text-xs text-ink-2">
              {folders.length}개 폴더 · {chunkTotal.toLocaleString()}개 청크 색인됨
            </span>
          )}
          <span className="text-[11px] text-ink-3">질문으로 근거를 벡터 검색 →</span>
        </button>
      </div>
    </div>
  );
}
