import { NextResponse } from 'next/server';

import { getAiBackendUrls } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

export async function GET() {
  const upstreamUrls = getAiBackendUrls('/api/v1/ai/status');
  for (const upstreamUrl of upstreamUrls) {
    try {
      const upstreamResponse = await fetch(upstreamUrl, {
        method: 'GET',
        cache: 'no-store',
        signal: AbortSignal.timeout(5000),
      });
      return new NextResponse(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers: { 'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json' },
      });
    } catch (error) {
      console.error('[FRONTEND][AI   ] Failed GET /api/frontend/ai/status', error);
    }
  }
  return NextResponse.json(
    {
      enabled: true,
      base_url: '',
      model: 'gemma4:12b',
      reachable: false,
      model_available: false,
      status: 'unavailable',
      detail: 'AI backend unavailable',
    },
    { status: 200 },
  );
}
