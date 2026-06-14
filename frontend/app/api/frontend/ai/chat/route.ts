import { NextRequest } from 'next/server';

import { proxyToAiBackend } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyToAiBackend(request, '/api/v1/ai/chat', {
    method: 'POST',
    body,
    timeoutMs: 130000,
  });
}
