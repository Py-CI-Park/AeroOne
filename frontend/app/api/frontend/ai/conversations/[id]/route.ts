import { NextRequest } from 'next/server';

import { proxyToAiBackend } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

function path(id: string) {
  return `/api/v1/ai/conversations/${encodeURIComponent(id)}`;
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToAiBackend(request, path(id), { method: 'GET', timeoutMs: 10000 });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  return proxyToAiBackend(request, path(id), { method: 'PATCH', body, timeoutMs: 10000 });
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToAiBackend(request, path(id), { method: 'DELETE', timeoutMs: 10000 });
}
