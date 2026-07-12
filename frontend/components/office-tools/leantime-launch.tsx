'use client';

import React from 'react';

/**
 * Leantime 실행 버튼 — 동거(co-deploy) 앱이라 별도 포트(기본 8081)에서 돈다.
 *
 * LAN 접속에서도 맞도록 현재 접속 호스트를 기준으로 URL 을 만든다(localhost 고정 금지).
 * 설치·기동되지 않았다면 새 탭에서 연결 오류가 나므로, 이 버튼 주변 안내가 그 맥락을 준다.
 */
export function LeantimeLaunch({ port = 8081 }: { port?: number }) {
  const [url, setUrl] = React.useState(`http://localhost:${port}`);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      setUrl(`${window.location.protocol}//${window.location.hostname}:${port}`);
    }
  }, [port]);

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 self-start rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-on transition hover:bg-accent-hover"
    >
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4" aria-hidden>
        <path d="M11 3h6v6M17 3l-8 8M8 4H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4" />
      </svg>
      Leantime 새 탭으로 열기
      <span className="text-xs font-normal opacity-80">({url})</span>
    </a>
  );
}
