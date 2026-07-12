import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

// Leantime 동거 상태(/api/v1/leantime/*) 로의 same-origin 프록시. 쿠키/CSRF 를 중계해
// 로그인 세션 그대로 백엔드 health 를 조회한다(GET 전용).
const LEANTIME_ALLOWLIST = {
  frontendPrefix: '/api/frontend/leantime',
  backendPrefix: '/api/v1/leantime',
  backendPathPrefix: '/api/v1/leantime/',
  methods: ['GET'] as const,
  mode: { kind: 'prefix' as const },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, LEANTIME_ALLOWLIST);
}
