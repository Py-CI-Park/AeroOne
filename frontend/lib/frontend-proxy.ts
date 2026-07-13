import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

const DEFAULT_ALLOWED_METHODS = ['GET', 'POST', 'PATCH', 'DELETE'] as const;
const REQUEST_HEADERS_TO_RELAY = ['cookie', 'x-csrf-token', 'content-type', 'accept'] as const;
const RESPONSE_HEADERS_TO_RELAY = ['content-type', 'content-disposition', 'content-length'] as const;
const NO_STORE = 'no-store';

type RelayMode =
  | {
      kind: 'exact';
      segments: readonly string[];
      backendSegments?: Record<string, string>;
    }
  | {
      kind: 'prefix';
      excludedFirstSegments?: readonly string[];
    };

export type FrontendProxyAllowlist = {
  frontendPrefix: string;
  backendPrefix: string;
  backendPathPrefix: string;
  methods?: readonly string[];
  mode: RelayMode;
};

function getSetCookieHeaders(headers: Headers): string[] {
  const withGetSetCookie = headers as Headers & { getSetCookie?: () => string[] };
  const setCookies = typeof withGetSetCookie.getSetCookie === 'function'
    ? withGetSetCookie.getSetCookie()
    : [];
  if (setCookies.length > 0) {
    return setCookies;
  }
  const single = headers.get('set-cookie');
  return single ? [single] : [];
}

function hasUnsafeEncodedPathSegment(segment: string): boolean {
  // admin/auth path segments are plain ASCII identifiers. Any percent-encoding
  // (e.g. %73earch smuggling 'search' past the exclusion, %2e%2e, %2f, %5c) or
  // literal traversal is rejected outright, so the backend can never receive a
  // segment that decodes to something other than what the allowlist compared.
  return segment.includes('..') || segment.includes('\\') || segment.includes('%');
}

function resolveAllowedBackendPath(request: NextRequest, allowlist: FrontendProxyAllowlist): string | null {
  const requestUrl = new URL(request.url);
  const encodedPathname = requestUrl.pathname;
  const frontendPrefix = allowlist.frontendPrefix.replace(/\/$/, '');
  if (encodedPathname !== frontendPrefix && !encodedPathname.startsWith(`${frontendPrefix}/`)) {
    return null;
  }

  const encodedSuffix = encodedPathname.slice(frontendPrefix.length);
  if (!encodedSuffix.startsWith('/')) {
    return null;
  }

  const encodedSegments = encodedSuffix.split('/').filter(Boolean);
  if (encodedSegments.length === 0 || encodedSegments.some(hasUnsafeEncodedPathSegment)) {
    return null;
  }

  let backendSegments = encodedSegments;
  if (allowlist.mode.kind === 'exact') {
    if (encodedSegments.length !== 1 || !allowlist.mode.segments.includes(encodedSegments[0])) {
      return null;
    }
    backendSegments = [allowlist.mode.backendSegments?.[encodedSegments[0]] ?? encodedSegments[0]];
  } else {
    if (allowlist.mode.excludedFirstSegments?.includes(encodedSegments[0])) {
      return null;
    }
  }

  const backendPrefix = allowlist.backendPrefix.replace(/\/$/, '');
  const backendPath = `${backendPrefix}/${backendSegments.join('/')}`;
  const canonical = new URL(backendPath, 'http://proxy.local').pathname;
  if (!canonical.startsWith(allowlist.backendPathPrefix)) {
    return null;
  }
  return `${canonical}${requestUrl.search}`;
}

function buildRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  for (const headerName of REQUEST_HEADERS_TO_RELAY) {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }
  return headers;
}

export async function relayFrontendRequest(
  request: NextRequest,
  allowlist: FrontendProxyAllowlist,
): Promise<NextResponse> {
  const method = request.method.toUpperCase();
  const allowedMethods = allowlist.methods ?? DEFAULT_ALLOWED_METHODS;
  if (!allowedMethods.includes(method)) {
    return new NextResponse('Method not allowed', { status: 405, headers: { 'cache-control': NO_STORE } });
  }

  const upstreamPath = resolveAllowedBackendPath(request, allowlist);
  if (!upstreamPath) {
    return new NextResponse('Not found', { status: 404, headers: { 'cache-control': NO_STORE } });
  }

  const init: RequestInit & { duplex?: 'half' } = {
    method,
    cache: 'no-store',
    headers: buildRequestHeaders(request),
  };
  if (method !== 'GET' && method !== 'HEAD' && request.body) {
    init.body = request.body;
    init.duplex = 'half';
  }

  try {
    const upstreamResponse = await fetch(`${getServerApiBase()}${upstreamPath}`, init);
    const responseBody = upstreamResponse.status >= 400
      ? '요청을 처리할 수 없습니다.'
      : upstreamResponse.body;
    const response = new NextResponse(responseBody, { status: upstreamResponse.status });
    response.headers.set('cache-control', NO_STORE);
    if (upstreamResponse.status < 400) {
      for (const headerName of RESPONSE_HEADERS_TO_RELAY) {
        const value = upstreamResponse.headers.get(headerName);
        if (value) {
          response.headers.set(headerName, value);
        }
      }
    }
    for (const cookie of getSetCookieHeaders(upstreamResponse.headers)) {
      response.headers.append('set-cookie', cookie);
    }
    return response;
  } catch (error) {
    console.error(`[FRONTEND][PROXY] Failed ${method} ${upstreamPath}`, error);
    return new NextResponse('Failed to reach backend', { status: 502, headers: { 'cache-control': NO_STORE } });
  }
}
