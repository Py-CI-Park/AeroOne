import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

// office-tools 백엔드(/api/v1/office-tools/*) 로의 same-origin catch-all 프록시.
// relayFrontendRequest 가 쿠키/x-csrf-token 을 중계하고, 비-GET 요청은 request.body 를
// duplex 스트림으로 그대로 전달하므로 multipart 업로드(보고서/차트)도 통과한다.
const OFFICE_TOOLS_ALLOWLIST = {
  frontendPrefix: '/api/frontend/office-tools',
  backendPrefix: '/api/v1/office-tools',
  backendPathPrefix: '/api/v1/office-tools/',
  mode: { kind: 'prefix' as const },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, OFFICE_TOOLS_ALLOWLIST);
}

export async function POST(request: NextRequest) {
  return relayFrontendRequest(request, OFFICE_TOOLS_ALLOWLIST);
}
export async function DELETE(request: NextRequest) {
  return relayFrontendRequest(request, OFFICE_TOOLS_ALLOWLIST);
}
