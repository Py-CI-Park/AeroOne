import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { getServerApiBase } from '@/lib/api';
import type { AuthResponse } from '@/lib/types';

function buildCookieHeader() {
  return cookies()
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join('; ');
}

export async function requireAdminSession() {
  const cookieHeader = buildCookieHeader();
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

  return (await response.json()) as AuthResponse['user'];
}
