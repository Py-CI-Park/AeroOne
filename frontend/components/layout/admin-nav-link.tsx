'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { fetchClientSession, logout } from '@/lib/api';

type SessionState =
  | { status: 'unknown' | 'anon' }
  | { status: 'auth'; username: string; isAdmin: boolean };

// 헤더의 로그인/Admin/로그아웃 링크. 확인된 세션은 사용자 아이디만 표시하고,
// 관리자는 Admin 바로가기까지 노출한다. same-origin /api/frontend/session 을 써서
// CORS/LAN 에 흔들리지 않게 신원을 확인한다. AppShell 은 서버 컴포넌트로 두고 이 섬만 클라이언트다.
const navLinkClass =
  'rounded px-2.5 py-1.5 text-base transition-colors duration-[120ms]';

const inactiveNavClass = `${navLinkClass} font-regular text-ink-2 hover:bg-surface-sunken hover:text-ink-1`;
const activeNavClass = `${navLinkClass} bg-surface-sunken font-medium text-ink-1`;

export function AdminNavLink({ active = false }: { active?: boolean }) {
  const [session, setSession] = useState<SessionState>({ status: 'unknown' });
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetchClientSession()
      .then((data) => {
        if (cancelled) return;
        if (data?.authenticated === true) {
          setSession({
            status: 'auth',
            username: data.username || data.role || '사용자',
            isAdmin: data.isAdmin === true,
          });
        } else {
          setSession({ status: 'anon' });
        }
      })
      .catch(() => {
        if (!cancelled) setSession({ status: 'anon' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
      setSession({ status: 'anon' });
      window.location.assign('/login');
    } catch {
      setLogoutError('로그아웃 실패');
      setLoggingOut(false);
    }
  };

  if (session.status === 'auth') {
    return (
      <div className="flex items-center gap-2">
        {session.isAdmin ? (
          <Link
            href="/admin"
            aria-current={active ? 'page' : undefined}
            className={active ? activeNavClass : inactiveNavClass}
          >
            Admin
          </Link>
        ) : null}
        <span
          aria-label={`현재 로그인 사용자 ${session.username}`}
          className="rounded-full border border-line-subtle bg-surface-sunken px-3 py-1 text-sm text-ink-2"
        >
          <strong className="font-semibold text-ink-1">{session.username}</strong>
        </span>
        <button
          type="button"
          onClick={() => void handleLogout()}
          disabled={loggingOut}
          className="rounded px-2.5 py-1.5 text-sm font-semibold text-ink-2 transition-colors duration-[120ms] hover:bg-surface-sunken hover:text-ink-1 disabled:cursor-wait disabled:opacity-60"
        >
          {loggingOut ? '로그아웃 중' : '로그아웃'}
        </button>
        {logoutError ? <span role="alert" className="text-xs font-semibold text-red-600">{logoutError}</span> : null}
      </div>
    );
  }

  return (
    <Link
      href="/login"
      className="rounded px-2.5 py-1.5 text-base font-regular text-ink-2 transition-colors duration-[120ms] hover:bg-surface-sunken hover:text-ink-1"
    >
      로그인
    </Link>
  );
}
