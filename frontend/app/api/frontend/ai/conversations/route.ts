import { NextRequest } from 'next/server';

import { proxyToAiBackend } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const includeArchived = request.nextUrl.searchParams.get('include_archived');
  const query = includeArchived ? `?include_archived=${encodeURIComponent(includeArchived)}` : '';
  return proxyToAiBackend(request, `/api/v1/ai/conversations${query}`, {
    method: 'GET',
    timeoutMs: 10000,
  });
}
