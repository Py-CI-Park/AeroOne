import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

const SEARCH_ALLOWLIST = {
  frontendPrefix: '/api/frontend/search',
  backendPrefix: '/api/v1/admin',
  backendPathPrefix: '/api/v1/admin/search',
  methods: ['GET'] as const,
  mode: {
    kind: 'exact' as const,
    segments: ['unified'] as const,
    backendSegments: { unified: 'search' },
  },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, SEARCH_ALLOWLIST);
}

export async function POST(request: NextRequest) {
  return relayFrontendRequest(request, SEARCH_ALLOWLIST);
}
