import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

const AUTH_ALLOWLIST = {
  frontendPrefix: '/api/frontend/auth',
  backendPrefix: '/api/v1/auth',
  backendPathPrefix: '/api/v1/auth/',
  methods: ['GET', 'POST'] as const,
  mode: {
    kind: 'exact' as const,
    segments: ['login', 'logout', 'change-password', 'me', 'effective-permissions', 'activity'] as const,
  },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, AUTH_ALLOWLIST);
}

export async function POST(request: NextRequest) {
  return relayFrontendRequest(request, AUTH_ALLOWLIST);
}
