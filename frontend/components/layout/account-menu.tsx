'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import { fetchClientSession, logout } from '@/lib/api';
import type { ClientSession } from '@/lib/types';

type MenuState =
  | { status: 'unknown' }
  | { status: 'anon' }
  | { status: 'auth'; username: string; isAdmin: boolean };

// 헤더 우측의 계정 메뉴. ClientSession 계약(스네이크케이스 is_admin 등)만 소비하고
// 파생 플래그를 직접 재계산하지 않는다. 세 갈래 상태:
// - unknown(최초 로딩): 깜빡임 방지를 위해 아무것도 그리지 않는다.
// - anon: 로그인 링크만 노출.
// - auth: 사용자 칩 트리거 뒤에 드롭다운(내 활동/Admin/로그아웃)을 숨겨둔다.
// same-origin /api/frontend/session 을 써서 CORS/LAN 에 흔들리지 않게 신원을 확인한다.
// AppShell 은 서버 컴포넌트로 두고 이 섬만 클라이언트다.
export function AccountMenu({ active = false }: { active?: boolean }) {
  const [session, setSession] = useState<MenuState>({ status: 'unknown' });
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchClientSession()
      .then((data: ClientSession) => {
        if (cancelled) return;
        if (data?.authenticated === true) {
          if (data.requires_password_change && window.location.pathname !== '/change-password') {
            // 강제 변경 상태 계정이 어느 페이지로 진입하든 전용 변경 화면으로 유도한다.
            window.location.assign('/change-password');
            return;
          }
          setSession({
            status: 'auth',
            username: data.username || data.role || '사용자',
            isAdmin: data.is_admin === true,
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

  const closeMenu = useCallback((refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeMenu();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, closeMenu]);

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
      setSession({ status: 'anon' });
      setOpen(false);
      window.location.assign('/login');
    } catch {
      setLogoutError('로그아웃 실패');
      setLoggingOut(false);
    }
  };

  if (session.status === 'unknown' || session.status === 'anon') {
    // 세션 확인 전에도 로그인 진입점은 유지한다(과거 헤더 동작과 동일).
    // 인증 확정 전에는 Admin/내 활동 등 권한 표면을 절대 노출하지 않는다.
    return (
      <Link
        href="/login"
        className="rounded px-2.5 py-1.5 text-base font-regular text-ink-2 transition-colors duration-[120ms] hover:bg-surface-sunken hover:text-ink-1"
      >
        로그인
      </Link>
    );
  }

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`현재 로그인 사용자 ${session.username}`}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-full border border-line-subtle bg-surface-sunken px-3 py-1 text-sm text-ink-2 transition-colors duration-[120ms] hover:bg-surface-raised"
      >
        <strong className="font-semibold text-ink-1">{session.username}</strong>
      </button>
      {open ? (
        <div
          role="menu"
          aria-label={`${session.username} 계정 메뉴`}
          className="absolute right-0 z-[60] mt-2 min-w-[9rem] rounded-md border border-line-subtle bg-surface-raised py-1 shadow-lg"
        >
          <Link
            href="/activity"
            role="menuitem"
            onClick={() => closeMenu(false)}
            className="block px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-sunken hover:text-ink-1"
          >
            내 활동
          </Link>
          {session.isAdmin ? (
            <Link
              href="/admin"
              role="menuitem"
              aria-current={active ? 'page' : undefined}
              onClick={() => closeMenu(false)}
              className="block px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-sunken hover:text-ink-1"
            >
              Admin
            </Link>
          ) : null}
          <button
            type="button"
            role="menuitem"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
            className="block w-full px-3 py-1.5 text-left text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1 disabled:cursor-wait disabled:opacity-60"
          >
            {loggingOut ? '로그아웃 중' : '로그아웃'}
          </button>
          {logoutError ? (
            <span role="alert" className="block px-3 py-1 text-xs font-semibold text-red-600">
              {logoutError}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
