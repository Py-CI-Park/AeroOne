import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

export const dynamic = 'force-dynamic';

// Aero Work 문서 AI 내용 생성 SSE 스트리밍 — 요청 본문은 그대로 버퍼링해 전달하고,
// 백엔드 업스트림 응답 본문(text/event-stream)을 그대로 패스스루한다. 로그인 세션 쿠키와
// CSRF 헤더를 그대로 중계해 백엔드가 검증한다(실패는 event:error 프레임 또는 4xx로 표현).
export async function POST(request: NextRequest) {
  const body = await request.text();
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  const cookie = request.headers.get('cookie');
  if (cookie) headers.cookie = cookie;
  const csrfToken = request.headers.get('x-csrf-token');
  if (csrfToken) headers['x-csrf-token'] = csrfToken;

  try {
    const upstreamResponse = await fetch(`${getServerApiBase()}/api/v1/aero-work/document/compose/stream`, {
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
      },
    });
    const setCookie = upstreamResponse.headers.get('set-cookie');
    if (setCookie) response.headers.append('set-cookie', setCookie);
    return response;
  } catch (error) {
    console.error('[FRONTEND][AERO-WORK] Failed POST /api/v1/aero-work/document/compose/stream', error);
    return new NextResponse('Failed to reach backend', { status: 502 });
  }
}
