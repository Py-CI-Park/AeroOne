import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

export const dynamic = 'force-dynamic';

const LOCAL_BACKEND_BASE = 'http://127.0.0.1:18437';
const RENDER_PATH = '/api/v1/render';
const TIMEOUT_MS = 15_000;

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/$/, '');
}

// 백엔드 /api/v1/render(stateless sanitize)로 보낼 후보 URL을 만든다.
// local-first(127.0.0.1) → 설정된 server base 순. 쿠키/세션 중계가 필요 없다.
function getRenderBackendUrls() {
  const candidates = [LOCAL_BACKEND_BASE, getServerApiBase()]
    .map(normalizeBaseUrl)
    .filter((baseUrl, index, values) => values.indexOf(baseUrl) === index);
  return candidates.map((baseUrl) => `${baseUrl}${RENDER_PATH}`);
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  for (const upstreamUrl of getRenderBackendUrls()) {
    try {
      const upstreamResponse = await fetch(upstreamUrl, {
        method: 'POST',
        cache: 'no-store',
        signal: AbortSignal.timeout(TIMEOUT_MS),
        headers: { 'content-type': 'application/json' },
        body,
      });
      return new NextResponse(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers: {
          'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json',
        },
      });
    } catch (error) {
      console.error('[FRONTEND][RENDER] Failed POST /api/v1/render', error);
    }
  }
  return new NextResponse('Failed to reach render backend', { status: 502 });
}
