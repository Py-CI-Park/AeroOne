'use client';

import React from 'react';

// AeroAI 인용/검색 결과가 가리키는 뷰어 경로만 열도록 화이트리스트로 제한한다.
// 백엔드가 절대/외부/알 수 없는 same-origin 경로를 내려주더라도 여기서 막는다.
const SAFE_VIEWER_NAVIGATION_PATHS = new Set(['/documents', '/reports/civil-aircraft', '/nsa']);

export function safeViewerNavigationUrl(rawUrl: string): string {
  const href = rawUrl.trim();
  if (!href || !href.startsWith('/') || href.startsWith('//')) return '';
  try {
    const url = new URL(href, 'http://aeroone.local');
    if (!SAFE_VIEWER_NAVIGATION_PATHS.has(url.pathname)) return '';
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return '';
  }
}

export function SafeViewerLink({
  navigationUrl,
  className,
  title,
  disabledElement = 'span',
  children,
}: {
  navigationUrl: string;
  className: string;
  title?: string;
  disabledElement?: 'span' | 'div';
  children: React.ReactNode;
}) {
  const href = safeViewerNavigationUrl(navigationUrl);
  const disabledClassName = `${className} cursor-not-allowed opacity-60`;
  const disabledTitle = title ? `${title} (열 수 없는 경로)` : '열 수 없는 경로';
  if (!href) {
    return disabledElement === 'div' ? (
      <div aria-disabled="true" className={disabledClassName} title={disabledTitle}>
        {children}
      </div>
    ) : (
      <span aria-disabled="true" className={disabledClassName} title={disabledTitle}>
        {children}
      </span>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className} title={title}>
      {children}
    </a>
  );
}
