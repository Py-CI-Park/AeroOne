import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';
import type { ClientSession, ClientSessionResourceGrant } from '@/lib/types';

export const dynamic = 'force-dynamic';

const EMPTY_HINTS = { permissions: [] as string[], resources: [] as ClientSessionResourceGrant[] };

type ServiceModuleHint = { key: string; is_enabled?: boolean };

const NSA_PERMISSION_KEYS = ['collections.nsa.read', 'search.nsa.read'];

function fetchInit(cookie: string): RequestInit {
  return {
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store' as const,
    signal: AbortSignal.timeout(5000),
  };
}

async function fetchAuthMe(base: string, cookie: string): Promise<{ username?: string | null; role?: string | null; requires_password_change?: boolean } | 'unauthorized' | null> {
  try {
    const upstream = await fetch(`${base}/api/v1/auth/me`, fetchInit(cookie));
    if (upstream.ok) {
      return (await upstream.json()) as { username?: string | null; role?: string | null; requires_password_change?: boolean };
    }
    if (upstream.status === 401) {
      return 'unauthorized';
    }
    return null;
  } catch {
    return null;
  }
}

async function fetchEffectivePermissionHints(base: string, cookie: string): Promise<typeof EMPTY_HINTS> {
  try {
    const upstream = await fetch(`${base}/api/v1/auth/effective-permissions`, fetchInit(cookie));
    if (!upstream.ok) {
      return EMPTY_HINTS;
    }
    const payload = (await upstream.json()) as Partial<typeof EMPTY_HINTS>;
    return {
      permissions: Array.isArray(payload.permissions) ? payload.permissions : [],
      resources: Array.isArray(payload.resources) ? payload.resources : [],
    };
  } catch {
    return EMPTY_HINTS;
  }
}

async function fetchPublicModules(base: string, cookie: string): Promise<ServiceModuleHint[] | null> {
  try {
    const upstream = await fetch(`${base}/api/v1/admin/service-modules/public`, fetchInit(cookie));
    if (!upstream.ok) {
      return null;
    }
    const payload = (await upstream.json()) as unknown;
    return Array.isArray(payload) ? (payload as ServiceModuleHint[]) : null;
  } catch {
    return null;
  }
}

function moduleAvailable(modules: ServiceModuleHint[] | null, key: string): boolean {
  if (!modules) {
    return false;
  }
  const found = modules.find((module) => module.key === key);
  return Boolean(found) && found?.is_enabled !== false;
}

function unauthenticatedResponse(): NextResponse {
  const body: ClientSession = {
    authenticated: false,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    ...EMPTY_HINTS,
    requires_password_change: false,
  };
  return NextResponse.json(body, { status: 200, headers: { 'Cache-Control': 'no-store' } });
}

function unreachedResponse(): NextResponse {
  const body: ClientSession = {
    authenticated: null,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    ...EMPTY_HINTS,
    requires_password_change: false,
  };
  return NextResponse.json(body, { status: 200, headers: { 'Cache-Control': 'no-store' } });
}

// same-origin 세션 조회 프록시. 브라우저는 CORS 걱정 없이 /api/frontend/session 을 부르고,
// Next 서버가 쿠키를 백엔드 /auth/me, /auth/effective-permissions, /admin/service-modules/public 으로
// server-to-server 중계한다. 파생 플래그(is_admin/can_view_*)는 이 라우트에서만 계산하며,
// 백엔드에 닿지 못하면 authenticated=null 로 신원을 단정하지 않되 Document 는 공개 상태를 유지한다.
export async function GET(request: NextRequest) {
  const cookie = request.headers.get('cookie') ?? '';
  const base = getServerApiBase();

  const authMe = await fetchAuthMe(base, cookie);

  if (authMe === null) {
    return unreachedResponse();
  }
  if (authMe === 'unauthorized') {
    return unauthenticatedResponse();
  }

  const [hints, modules] = await Promise.all([
    fetchEffectivePermissionHints(base, cookie),
    fetchPublicModules(base, cookie),
  ]);

  const role = authMe.role ?? null;
  const isAdmin = role === 'admin';
  const canViewDocument = modules === null ? true : moduleAvailable(modules, 'document');
  const hasNsaPermission =
    isAdmin ||
    hints.permissions.some((permission) => NSA_PERMISSION_KEYS.includes(permission)) ||
    hints.resources.some((grant) => grant.resource_type === 'collection' && grant.resource_id === 'nsa');
  const canViewNsa = moduleAvailable(modules, 'nsa') && hasNsaPermission;
  const canUseAi = moduleAvailable(modules, 'ai');

  const body: ClientSession = {
    authenticated: true,
    username: authMe.username ?? null,
    role,
    is_admin: isAdmin,
    can_view_document: canViewDocument,
    can_view_nsa: canViewNsa,
    can_use_ai: canUseAi,
    permissions: hints.permissions,
    resources: hints.resources,
    requires_password_change: authMe.requires_password_change === true,
  };

  return NextResponse.json(body, { status: 200, headers: { 'Cache-Control': 'no-store' } });
}
