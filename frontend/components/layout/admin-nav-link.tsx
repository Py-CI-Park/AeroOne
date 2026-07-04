'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { fetchClientSession } from '@/lib/api';

type SessionState = 'unknown' | 'anon' | 'admin' | 'user';

// 헤더의 로그인/Admin 링크. 서버 실행자(관리자)에게는 Admin, 로그인 안 한 사용자에게는 로그인 을,
// 관리자가 아닌 로그인 사용자에게는 아무 것도 보이지 않는다. same-origin /api/frontend/session 을 써서
// CORS/LAN 에 흔들리지 않게 신원을 확인한다. AppShell 은 서버 컴포넌트로 두고 이 섬만 클라이언트다.
export function AdminNavLink({ active = false }: { active?: boolean }) {
  const [session, setSession] = useState<SessionState>('unknown');

  useEffect(() => {
    let cancelled = false;
    fetchClientSession()
      .then((data) => {
        if (cancelled || !data) return;
        if (data.isAdmin) setSession('admin');
        else if (data.authenticated === true) setSession('user');
        else if (data.authenticated === false) setSession('anon');
        else setSession('unknown');
      })
      .catch(() => {
        // 미도달 시 신원 미확정 — 아무 링크도 표시하지 않는다.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (session === 'admin') {
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

  if (session === 'anon') {
    return (
      <Link
        href="/login"
        className="rounded px-2.5 py-1.5 text-base font-regular text-ink-2 transition-colors duration-[120ms] hover:bg-surface-sunken hover:text-ink-1"
      >
        로그인
      </Link>
    );
  }

  return null;
}
