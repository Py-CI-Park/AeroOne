'use client';

import React, { useEffect, useState } from 'react';

import { Icon } from '@/components/ui/icons';

// 페이지를 일정 높이 이상 내리면 우하단에 떠오르는 "맨 위로" 버튼.
// 뉴스레터 본문 iframe 은 scrolling="no" + 콘텐츠 전체 높이로 늘어나므로 실제 스크롤은
// 창(window)에서 일어난다. 따라서 window.scrollY 를 보고 window.scrollTo 로 올린다.
export function ScrollToTop({ threshold = 300 }: { threshold?: number }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll(); // 마운트 시 현재 위치 반영
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  if (!visible) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      aria-label="맨 위로"
      title="맨 위로"
      data-testid="scroll-to-top"
      className="fixed bottom-6 right-6 z-40 inline-flex h-11 w-11 items-center justify-center rounded-full border border-line bg-surface-raised text-ink-1 shadow-lg transition-colors duration-[120ms] hover:bg-surface-sunken focus-visible:shadow-focus focus-visible:outline-none"
    >
      <Icon.chevD size={16} className="rotate-180" />
    </button>
  );
}
