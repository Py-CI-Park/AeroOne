'use client';

import React from 'react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { ScrollToTop } from '@/components/ui/scroll-to-top';

// 민간 항공기 보고서 뷰 — 뉴스레터 리딩 뷰에서 "달력 없이" HTML 본문만 떼어낸 형태.
// HtmlViewer 는 hooks 를 쓰지만 'use client' 가 없어 서버 컴포넌트가 직접 렌더할 수 없으므로
// 이 클라이언트 경계에서 감싼다. sandbox iframe + 높이 동기화 + 기사 펼침 동작을 그대로 재사용.
export function CivilAircraftReport({ title, html }: { title: string; html: string }) {
  return (
    <section data-testid="civil-aircraft-report" className="min-w-0">
      <HtmlViewer title={title} html={html} />
      <ScrollToTop />
    </section>
  );
}
