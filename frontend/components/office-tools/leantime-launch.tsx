'use client';

import React from 'react';

/**
 * Leantime 실행 버튼 — 동거(co-deploy) 앱이라 별도 포트(기본 8081)에서 돈다.
 *
 * LAN 접속에서도 맞도록 현재 접속 호스트를 기준으로 URL 을 만든다(localhost 고정 금지).
 * 상위(LeantimeStatus)가 헬스 결과로 enabled 를 넘겨, ready 가 아니면 링크 대신 비활성
 * 안내로 렌더해 '눌러도 빈 화면'을 원천 차단한다. `launchUrl` 은 백엔드가 알려준 정식 대상을
 * 참고 표시용으로만 쓰고, 실제 이동 링크는 항상 브라우저 접속 호스트 기준으로 만든다.
 */
export function LeantimeLaunch({
  port = 8081,
  enabled = true,
  launchUrl,
}: {
  port?: number;
  enabled?: boolean;
  launchUrl?: string;
}) {
  const [url, setUrl] = React.useState(`http://localhost:${port}`);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      setUrl(`${window.location.protocol}//${window.location.hostname}:${port}`);
    }
  }, [port]);

  const icon = (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-4 w-4" aria-hidden>
      <path d="M11 3h6v6M17 3l-8 8M8 4H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4" />
    </svg>
  );

  if (!enabled) {
    return (
      <span
        aria-disabled
        title="Leantime 이 아직 준비되지 않았습니다."
        className="inline-flex cursor-not-allowed items-center gap-2 self-start rounded-md border border-ink-3/30 bg-surface-sunken px-4 py-2 text-sm font-semibold text-ink-3"
      >
        {icon}
        Leantime 열기 (미구동)
        <span className="text-xs font-normal opacity-80">({launchUrl ?? url})</span>
      </span>
    );
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 self-start rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-on transition hover:bg-accent-hover"
    >
      {icon}
      Leantime 새 탭으로 열기
      <span className="text-xs font-normal opacity-80">({launchUrl ?? url})</span>
    </a>
  );
}
