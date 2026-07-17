import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

// 외부 런처(Open Notebook/OpenWebUI) 동거 상태(/api/v1/launchers/*) 로의 same-origin 프록시.
// 쿠키/CSRF 를 중계해 로그인 세션 그대로 백엔드 health 를 조회한다(GET 전용).
const LAUNCHERS_ALLOWLIST = {
  frontendPrefix: '/api/frontend/launchers',
  backendPrefix: '/api/v1/launchers',
  backendPathPrefix: '/api/v1/launchers/',
  methods: ['GET'] as const,
  mode: { kind: 'prefix' as const },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, LAUNCHERS_ALLOWLIST);
}
