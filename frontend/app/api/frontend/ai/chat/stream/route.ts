import { NextRequest } from 'next/server';

import { proxyToAiBackend } from '@/app/api/frontend/ai/upstream';

export const dynamic = 'force-dynamic';

// AeroAI SSE 스트리밍 채팅 — 요청 본문(첨부 포함, ≤200,000자)은 그대로 버퍼링해 전달하고,
// proxyToAiBackend 가 업스트림 응답 본문(text/event-stream)을 그대로 패스스루한다.
// 생성이 오래 걸릴 수 있으므로 비스트리밍 chat 보다 긴 타임아웃을 둔다.
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyToAiBackend(request, '/api/v1/ai/chat/stream', {
    method: 'POST',
    body,
    timeoutMs: 300000,
  });
}
