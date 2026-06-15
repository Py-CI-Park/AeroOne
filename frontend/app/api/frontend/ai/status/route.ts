import { NextRequest, NextResponse } from 'next/server';

import { proxyToAiBackend } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const response = await proxyToAiBackend(request, '/api/v1/ai/status', {
    method: 'GET',
    timeoutMs: 5000,
  });
  if (response.status === 502) {
    // 백엔드 미도달 시에도 화면이 동작하도록 graceful degraded 상태를 돌려준다.
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
  return response;
}
