import { NextResponse } from 'next/server';

import { NEWSLETTER_THEME_COOKIE, resolveNewsletterTheme } from '@/lib/theme';

function safeNextPath(raw: string | null) {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) {
    return '/newsletters';
  }

  return raw;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const theme = resolveNewsletterTheme(url.searchParams.get('theme') ?? undefined);
  const next = safeNextPath(url.searchParams.get('next'));
  const response = NextResponse.redirect(new URL(next, url.origin));

  response.cookies.set(NEWSLETTER_THEME_COOKIE, theme, {
    path: '/',
    sameSite: 'lax',
    maxAge: 31536000,
  });

  return response;
}
