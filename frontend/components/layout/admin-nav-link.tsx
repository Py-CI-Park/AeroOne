'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { getBrowserApiBase } from '@/lib/api';

// Admin(서버 실행자) 전용 헤더 링크. 로그인한 관리자에게만 보인다.
// AppShell 이 서버 컴포넌트라, 세션 확인이 필요한 이 부분만 클라이언트 섬으로 분리한다.
export function AdminNavLink({ active = false }: { active?: boolean }) {
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${getBrowserApiBase()}/api/v1/auth/me`, { credentials: 'include', cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((user) => {
        if (!cancelled) {
          setIsAdmin(Boolean(user && user.role === 'admin'));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIsAdmin(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!isAdmin) {
    return null;
  }

  return (
    <Link
      href="/admin"
      aria-current={active ? 'page' : undefined}
      className={`rounded px-2.5 py-1.5 text-base transition-colors duration-[120ms] ${
        active
          ? 'bg-surface-sunken font-medium text-ink-1'
          : 'font-regular text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
      }`}
    >
      Admin
    </Link>
  );
}
