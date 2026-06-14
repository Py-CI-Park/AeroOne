import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

const LOCAL_BACKEND_BASE = 'http://127.0.0.1:18437';

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/$/, '');
}

export function getAiBackendUrls(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const candidates = [LOCAL_BACKEND_BASE, getServerApiBase()]
    .map(normalizeBaseUrl)
    .filter((baseUrl, index, values) => values.indexOf(baseUrl) === index);

  return candidates.map((baseUrl) => `${baseUrl}${normalizedPath}`);
}

function buildHeaders(request: NextRequest, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra ?? {}) };
  // 익명 세션 쿠키(ai_session)를 백엔드로 투명 중계한다. 이게 없으면 같은 브라우저의
  // 대화가 매 요청마다 새 세션으로 흩어진다(신원=세션쿠키 단독 권위).
  const cookie = request.headers.get('cookie');
  if (cookie) {
    headers.cookie = cookie;
  }
  return headers;
}

function relaySetCookie(upstream: Response, response: NextResponse): void {
  // 백엔드가 발급한 Set-Cookie(host-only+Path=/)를 브라우저로 그대로 전달한다.
  // 계약: 이 왕복은 백엔드가 ai_session 을 Path=/ (Domain 미설정)로 발급해야 성립한다.
  // 백엔드가 쿠키를 /api/v1/ai 로 좁히면 브라우저가 프록시 경로(/api/frontend/ai/*)에
  // 다시 보내지 않아 세션이 흩어진다(backend public.py _owner_session 가 Path=/ 유지).
  // Next 의 Headers 는 getSetCookie() 로 다중 Set-Cookie 를 보존한다.
  const setCookies =
    typeof upstream.headers.getSetCookie === 'function'
      ? upstream.headers.getSetCookie()
      : ([] as string[]);
  if (setCookies.length === 0) {
    const single = upstream.headers.get('set-cookie');
    if (single) {
      setCookies.push(single);
    }
  }
  for (const cookie of setCookies) {
    response.headers.append('set-cookie', cookie);
  }
}

/**
 * AI 백엔드로 same-origin 프록시 요청을 보내고, Cookie/Set-Cookie 를 양방향 중계한다.
 * local-first(127.0.0.1) 후 설정된 server base 순으로 시도한다.
 */
export async function proxyToAiBackend(
  request: NextRequest,
  path: string,
  init: { method: string; body?: string; timeoutMs: number },
): Promise<NextResponse> {
  const upstreamUrls = getAiBackendUrls(path);
  for (const upstreamUrl of upstreamUrls) {
    try {
      const headers = buildHeaders(
        request,
        init.body !== undefined ? { 'content-type': 'application/json' } : undefined,
      );
      const upstreamResponse = await fetch(upstreamUrl, {
        method: init.method,
        cache: 'no-store',
        signal: AbortSignal.timeout(init.timeoutMs),
        headers,
        body: init.body,
      });
      const response = new NextResponse(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers: {
          'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json',
        },
      });
      relaySetCookie(upstreamResponse, response);
      return response;
    } catch (error) {
      console.error(`[FRONTEND][AI   ] Failed ${init.method} ${path}`, error);
    }
  }
  return new NextResponse('Failed to reach AI backend', { status: 502 });
}
