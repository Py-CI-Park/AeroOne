import { NextRequest } from 'next/server';

import { relayFrontendRequest } from '@/lib/frontend-proxy';

export const dynamic = 'force-dynamic';

const ADMIN_ALLOWLIST = {
  frontendPrefix: '/api/frontend/admin',
  backendPrefix: '/api/v1/admin',
  backendPathPrefix: '/api/v1/admin/',
  mode: {
    kind: 'prefix' as const,
    excludedFirstSegments: ['search'] as const,
  },
};

export async function GET(request: NextRequest) {
  return relayFrontendRequest(request, ADMIN_ALLOWLIST);
}

export async function POST(request: NextRequest) {
  return relayFrontendRequest(request, ADMIN_ALLOWLIST);
}

export async function PATCH(request: NextRequest) {
  return relayFrontendRequest(request, ADMIN_ALLOWLIST);
}

export async function DELETE(request: NextRequest) {
  return relayFrontendRequest(request, ADMIN_ALLOWLIST);
}

export async function PUT(request: NextRequest) {
  return relayFrontendRequest(request, ADMIN_ALLOWLIST);
}
