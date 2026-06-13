import { NextRequest, NextResponse } from 'next/server';

import { getAiBackendUrls } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const upstreamUrls = getAiBackendUrls('/api/v1/ai/chat');
  const body = await request.text();

  for (const upstreamUrl of upstreamUrls) {
    try {
      const upstreamResponse = await fetch(upstreamUrl, {
        method: 'POST',
        cache: 'no-store',
        signal: AbortSignal.timeout(130000),
        headers: { 'content-type': 'application/json' },
        body,
      });
      return new NextResponse(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers: { 'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json' },
      });
    } catch (error) {
      console.error('[FRONTEND][AI   ] Failed POST /api/frontend/ai/chat', error);
    }
  }
  return new NextResponse('Failed to reach AI backend', { status: 502 });
}
