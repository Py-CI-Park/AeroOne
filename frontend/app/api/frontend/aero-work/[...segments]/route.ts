import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

// Aero Work 백엔드(/api/v1/aero-work/*) 로의 same-origin catch-all 프록시.
// relayFrontendRequest 가 쿠키/x-csrf-token 을 중계한다(지식폴더 등록/색인/삭제는 CSRF 필수).
const AERO_WORK_ALLOWLIST = {
  frontendPrefix: '/api/frontend/aero-work',
  backendPrefix: '/api/v1/aero-work',
  backendPathPrefix: '/api/v1/aero-work/',
  mode: { kind: 'prefix' as const },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, AERO_WORK_ALLOWLIST);
}

export async function POST(request: NextRequest) {
  return relayFrontendRequest(request, AERO_WORK_ALLOWLIST);
}

export async function DELETE(request: NextRequest) {
  return relayFrontendRequest(request, AERO_WORK_ALLOWLIST);
}
