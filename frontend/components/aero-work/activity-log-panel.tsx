'use client';

import { useCallback, useEffect, useState } from 'react';

import { fetchAeroWorkActivity, type AeroWorkActivity } from '@/lib/api';

// Aero Work P4 실행기록 — 사용자가 워크스페이스에서 한 행위를 최신순 타임라인으로 투명하게
// 보여준다(지식 색인/검색, 일정 변경, 문서 생성 등). created_at 은 서버 UTC naive 라 표시 시
// 'Z' 를 붙여 로컬 시각으로 환산한다.

const KIND_META: Record<string, { icon: string; label: string }> = {
  'knowledge.register': { icon: '📚', label: '지식폴더 등록' },
  'knowledge.reindex': { icon: '🔄', label: '지식 색인' },
  'knowledge.delete': { icon: '🗑️', label: '지식폴더 삭제' },
  'knowledge.search': { icon: '🔍', label: '지식 검색' },
  'schedule.create': { icon: '📅', label: '일정 추가' },
  'schedule.update': { icon: '✏️', label: '일정 수정' },
  'schedule.delete': { icon: '🗑️', label: '일정 삭제' },
  'document.generate': { icon: '📝', label: '문서 생성' },
};

function kindMeta(kind: string) {
  return KIND_META[kind] ?? { icon: '•', label: kind };
}

function formatWhen(iso: string): string {
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const diffMin = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diffMin < 1) {
    return '방금 전';
  }
  if (diffMin < 60) {
    return `${diffMin}분 전`;
  }
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) {
    return `${diffHr}시간 전`;
  }
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) {
    return `${diffDay}일 전`;
  }
  return date.toLocaleString('ko-KR');
}

export function ActivityLogPanel() {
  const [items, setItems] = useState<AeroWorkActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAeroWorkActivity(100);
      setItems(data.activities);
      setError(null);
    } catch {
      setError('실행기록을 불러오지 못했음. 로그인 상태를 확인할 것.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="mt-4 space-y-4">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}

      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-2">워크스페이스에서 실행한 작업을 최신순으로 남깁니다.</p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken"
        >
          새로고침
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-ink-3">불러오는 중…</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-subtle bg-surface-base px-3 py-4 text-sm text-ink-3">
          아직 실행기록이 없음. 지식 색인·검색이나 일정 추가 등을 하면 여기에 남음.
        </p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => {
            const meta = kindMeta(item.kind);
            return (
              <li key={item.id} className="flex items-start gap-3 rounded-lg border border-line-subtle bg-surface-base px-3 py-2">
                <span aria-hidden className="pt-0.5 text-base">{meta.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink-1">
                    <span className="font-medium text-ink-2">{meta.label}</span> · {item.summary}
                  </p>
                  {item.detail ? <p className="mt-0.5 truncate text-xs text-ink-3">{item.detail}</p> : null}
                </div>
                <span className="shrink-0 pt-0.5 text-xs text-ink-3">{formatWhen(item.created_at)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
