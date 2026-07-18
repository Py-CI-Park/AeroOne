'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { fetchMyRecentReads } from '@/lib/api';
import { formatRelativeTime } from '@/lib/relative-time';
import type { RecentReadItem } from '@/lib/types';

// 대시보드 "최근 본 뉴스레터" 칩 스트립. read 비콘과 같은 (newsletter_id, client_ip) 스코프를
// 조회하므로 same-origin BFF 가 아니라 브라우저가 백엔드를 직접 호출해야 정확한 목록이 나온다
// (fetchMyRecentReads 참고). 항목이 없거나 조회가 실패하면 대시보드를 오염시키지 않도록
// 아무것도 렌더하지 않는다(에러 배너/스켈레톤 없음).
export function RecentReadsStrip() {
  const [items, setItems] = useState<RecentReadItem[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMyRecentReads(6)
      .then((response) => {
        if (!cancelled) setItems(response.items);
      })
      .catch((error) => {
        // 조용한 무렌더가 설정 오류(CORS/base URL)를 가리지 않게 진단 단서만 남긴다.
        if (process.env.NODE_ENV !== 'production') console.debug('[recent-reads] fetch failed', error);
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-line-subtle bg-surface-raised px-4 py-3">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-3">최근 본 뉴스레터</h2>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <Link
            key={item.slug}
            href={`/newsletters/${item.slug}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-elevated px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent"
          >
            <span className="font-medium text-ink-1">{item.title}</span>
            <span className="text-xs text-ink-4">{formatRelativeTime(item.last_seen_at)}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
