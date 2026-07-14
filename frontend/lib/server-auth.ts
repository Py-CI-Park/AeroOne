import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { getServerApiBase } from '@/lib/api';
import type { AuthResponse } from '@/lib/types';

async function buildCookieHeader() {
  // Next 15: cookies() 는 async — 동기 접근 경고를 피하려 await 로 읽는다.
  return (await cookies())
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join('; ');
}

export async function requireAdminSession() {
  const cookieHeader = await buildCookieHeader();
  if (!cookieHeader) {
    redirect('/login');
  }

  const response = await fetch(`${getServerApiBase()}/api/v1/auth/me`, {
    cache: 'no-store',
    headers: {
      cookie: cookieHeader,
    },
  });

  if (!response.ok) {
    redirect('/login');
  }

  const user = (await response.json()) as AuthResponse['user'];
  if (user.role !== 'admin') {
    redirect('/login');
  }
  return user;
}

export async function resolveIsAdmin(): Promise<boolean> {
  const cookieHeader = await buildCookieHeader();
  if (!cookieHeader) {
    return false;
  }
  try {
    const response = await fetch(`${getServerApiBase()}/api/v1/auth/me`, {
      cache: 'no-store',
      headers: { cookie: cookieHeader },
    });
    if (!response.ok) {
      return false;
    }
    const user = (await response.json()) as AuthResponse['user'];
    return user.role === 'admin';
  } catch {
    return false;
  }
}
