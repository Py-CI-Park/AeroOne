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
  // 상대 경로(root-relative)로 리다이렉트한다. NextResponse.redirect 는 절대 URL 을
  // 요구하는데, 서버가 0.0.0.0 으로 바인딩되면 request.url 의 origin 이 http://0.0.0.0:29501
  // 로 잡혀 브라우저가 접속 불가한 주소로 튕긴다(LAN 모드 연결 종료 증상). 상대 Location 은
  // 브라우저가 주소창의 실제 호스트 기준으로 해석하므로 localhost/LAN IP/호스트명 모두 안전하다.
  const response = new NextResponse(null, {
    status: 307,
    headers: { Location: next },
  });

  response.cookies.set(NEWSLETTER_THEME_COOKIE, theme, {
    path: '/',
    sameSite: 'lax',
    maxAge: 31536000,
  });

  return response;
}
