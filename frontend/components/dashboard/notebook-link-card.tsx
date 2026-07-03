'use client';

import { useEffect, useState } from 'react';

import { ServiceCard } from '@/components/dashboard/service-card';

// Open Notebook 은 별도 폐쇄망 앱(co-deploy)으로 :8502 에서 기동된다.
// 같은 호스트의 다른 포트로 새 탭 이동 — 호스트는 클라이언트에서만 알 수 있어
// window.location.hostname 으로 동적 생성한다(SSR 은 localhost 폴백 후 hydrate).
const NOTEBOOK_PORT = 8502;

export function NotebookLinkCard({
  title,
  description,
  badge,
  href,
  active = true,
}: {
  title: string;
  description?: string;
  badge: string;
  href?: string;
  active?: boolean;
}) {
  const [host, setHost] = useState('localhost');

  useEffect(() => {
    setHost(window.location.hostname);
  }, []);

  const targetHref = href && href.trim() ? href : `http://${host}:${NOTEBOOK_PORT}`;

  return (
    <ServiceCard
      title={title}
      description={description}
      href={targetHref}
      badge={badge}
      active={active}
      external
    />
  );
}
