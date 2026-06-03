'use client';

import React from 'react';
import { useCallback, useEffect, useState } from 'react';

import { fetchAdminReadEvents, purgeReadEvents } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { ReadEventsResponse } from '@/lib/types';

export function ReadEventsList() {
  const [data, setData] = useState<ReadEventsResponse | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    void fetchAdminReadEvents()
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handlePurge() {
    if (typeof window !== 'undefined' && !window.confirm('모든 읽음 기록을 삭제할까요? 되돌릴 수 없습니다.')) {
      return;
    }
    try {
      setError('');
      await purgeReadEvents(getCsrfCookie());
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'purge 실패');
    }
  }

  if (error) {
    return <div className="rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm text-danger">{error}</div>;
  }
  if (!data) {
    return <div className="rounded-lg border border-line bg-surface-raised p-6 text-sm text-ink-2">불러오는 중…</div>;
  }

  return (
    <div className="space-y-5">
      {data.loopback_only ? (
        <div
          data-testid="loopback-banner"
          className="rounded-lg border border-warn/40 bg-warn-soft p-3 text-sm text-ink-2"
        >
          loopback 모드 — 모든 접속이 127.0.0.1 로 기록됩니다. 실제 접속 IP 를 남기려면 LAN 모드로 실행하세요.
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-3">
          접속 IP 별 열람 횟수(30분 디바운스 세션 기준). 익명 IP 집계이며 관리자만 열람합니다.
        </p>
        <button
          type="button"
          onClick={handlePurge}
          className="shrink-0 rounded border border-line px-3 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken"
        >
          전체 기록 삭제
        </button>
      </div>

      {data.events.length === 0 ? (
        <div
          data-testid="read-events-empty"
          className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
        >
          아직 읽음 기록이 없습니다.
        </div>
      ) : (
        <>
          <section data-testid="read-summaries" className="overflow-hidden rounded-lg border border-line bg-surface-elevated">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-sunken text-left text-ink-3">
                <tr>
                  <th className="px-4 py-2">뉴스레터</th>
                  <th className="px-4 py-2">총 열람</th>
                  <th className="px-4 py-2">고유 IP</th>
                </tr>
              </thead>
              <tbody>
                {data.summaries.map((summary) => (
                  <tr key={summary.newsletter_id} className="border-t border-line-subtle">
                    <td className="px-4 py-2 text-ink-1">{summary.title}</td>
                    <td className="px-4 py-2 tabular-nums">{summary.total_reads}</td>
                    <td className="px-4 py-2 tabular-nums">{summary.unique_ips}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section data-testid="read-events" className="overflow-hidden rounded-lg border border-line bg-surface-elevated">
            <table className="min-w-full text-sm">
              <thead className="bg-surface-sunken text-left text-ink-3">
                <tr>
                  <th className="px-4 py-2">뉴스레터 ID</th>
                  <th className="px-4 py-2">접속 IP</th>
                  <th className="px-4 py-2">열람 횟수</th>
                  <th className="px-4 py-2">최근 열람</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <tr key={`${event.newsletter_id}-${event.client_ip}`} className="border-t border-line-subtle">
                    <td className="px-4 py-2 tabular-nums">{event.newsletter_id}</td>
                    <td className="px-4 py-2 font-mono text-ink-1">{event.client_ip}</td>
                    <td className="px-4 py-2 tabular-nums">{event.read_count}</td>
                    <td className="px-4 py-2 text-ink-3">{event.last_seen_at ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
