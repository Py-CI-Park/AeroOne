import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

export const dynamic = 'force-dynamic';

const LOCAL_BACKEND_BASE = 'http://127.0.0.1:18437';

// same-origin 세션 조회 프록시. 브라우저는 CORS 걱정 없이 /api/frontend/session 을 부르고,
// Next 서버가 쿠키를 백엔드 /auth/me 로 server-to-server 중계한다. LAN/loopback 모두에서
// 헤더 Admin/로그인 링크 판단이 흔들리지 않도록 한다.
export async function GET(request: NextRequest) {
  const cookie = request.headers.get('cookie') ?? '';
  const bases = [LOCAL_BACKEND_BASE, getServerApiBase().replace(/\/$/, '')].filter(
    (base, index, values) => values.indexOf(base) === index,
  );
  for (const base of bases) {
    try {
      const upstream = await fetch(`${base}/api/v1/auth/me`, {
        headers: cookie ? { cookie } : {},
        cache: 'no-store',
        signal: AbortSignal.timeout(5000),
      });
      if (upstream.ok) {
        const user = (await upstream.json()) as { role?: string };
        const isAdmin = user?.role === 'admin';
        return NextResponse.json({ authenticated: true, role: user?.role ?? null, isAdmin }, { status: 200 });
      }
      if (upstream.status === 401) {
        return NextResponse.json({ authenticated: false, role: null, isAdmin: false }, { status: 200 });
      }
    } catch {
      // try the next candidate base
    }
  }
  // 백엔드 미도달: 신원을 단정하지 않는다(헤더는 아무 링크도 표시하지 않음).
  return NextResponse.json({ authenticated: null, role: null, isAdmin: false }, { status: 200 });
}
