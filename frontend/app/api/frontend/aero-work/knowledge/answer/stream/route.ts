import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

export const dynamic = 'force-dynamic';

// Aero Work 지식 근거 합성(답변) SSE 스트리밍 — 요청 본문은 그대로 버퍼링해 전달하고,
// 백엔드 업스트림 응답 본문(text/event-stream)을 그대로 패스스루한다. 로그인 세션 쿠키와
// CSRF 헤더를 그대로 중계해 백엔드가 검증한다(실패는 event:error 프레임 또는 4xx로 표현).
// 근거 검색 + 생성이 이어지므로 비스트리밍 검색보다 긴 타임아웃을 둔다.
export async function POST(request: NextRequest) {
  const body = await request.text();
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  const cookie = request.headers.get('cookie');
  if (cookie) headers.cookie = cookie;
  const csrfToken = request.headers.get('x-csrf-token');
  if (csrfToken) headers['x-csrf-token'] = csrfToken;

  try {
    const upstreamResponse = await fetch(`${getServerApiBase()}/api/v1/aero-work/knowledge/answer/stream`, {
      method: 'POST',
      cache: 'no-store',
      headers,
      body,
      signal: AbortSignal.timeout(300000),
    });
    const response = new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: {
        'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json',
        'cache-control': 'no-store',
      },
    });
    // 다중 Set-Cookie 를 모두 보존한다(getSetCookie() 미지원 런타임은 단일 헤더로 폴백) —
    // 기존 AeroAI 스트림(proxyToAiBackend/relaySetCookie) 관례를 그대로 따른다.
    const setCookies =
      typeof upstreamResponse.headers.getSetCookie === 'function'
        ? upstreamResponse.headers.getSetCookie()
        : upstreamResponse.headers.get('set-cookie')
          ? [upstreamResponse.headers.get('set-cookie') as string]
          : [];
    for (const setCookie of setCookies) {
      response.headers.append('set-cookie', setCookie);
    }
    return response;
  } catch (error) {
    console.error('[FRONTEND][AERO-WORK] Failed POST /api/v1/aero-work/knowledge/answer/stream', error);
    return new NextResponse('Failed to reach backend', { status: 502 });
  }
}
