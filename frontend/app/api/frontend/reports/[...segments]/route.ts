import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';

export const dynamic = 'force-dynamic';

// The Civil Aircraft interactive dashboard bundle is served same-origin through this
// proxy so its own bundled scripts run. The backend applies a self-only CSP; we relay
// that CSP (and caching/validator headers) verbatim so the browser enforces it.
const FORWARDED_RESPONSE_HEADERS = [
  'content-type',
  'content-security-policy',
  'x-content-type-options',
  'content-disposition',
  'cache-control',
  'content-language',
  'etag',
  'last-modified',
  'accept-ranges',
  'content-range',
  'content-length',
] as const;

const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'range',
  'if-range',
  'if-none-match',
  'if-modified-since',
  'cookie',
] as const;

// Only the reports module's civil-aircraft subtree is reachable through this proxy.
const ALLOWED_FIRST_SEGMENTS = new Set(['civil-aircraft']);

function isUnsafeSegment(segment: string): boolean {
  return segment.length === 0 || segment.includes('..') || segment.includes('\\') || segment.includes('%');
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  const { segments } = await context.params;
  if (segments.length === 0 || !ALLOWED_FIRST_SEGMENTS.has(segments[0]) || segments.some(isUnsafeSegment)) {
    return new NextResponse('Not found', { status: 404 });
  }

  const upstreamPath = `/api/v1/reports/${segments.join('/')}`;
  const upstreamUrl = `${getServerApiBase()}${upstreamPath}${request.nextUrl.search}`;

  const upstreamRequestHeaders: Record<string, string> = {};
  for (const headerName of FORWARDED_REQUEST_HEADERS) {
    const headerValue = request.headers.get(headerName);
    if (headerValue) {
      upstreamRequestHeaders[headerName] = headerValue;
    }
  }

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      method: 'GET',
      cache: 'no-store',
      headers: upstreamRequestHeaders,
    });

    const response = new NextResponse(upstreamResponse.body, { status: upstreamResponse.status });
    for (const headerName of FORWARDED_RESPONSE_HEADERS) {
      const headerValue = upstreamResponse.headers.get(headerName);
      if (headerValue) {
        response.headers.set(headerName, headerValue);
      }
    }
    return response;
  } catch (error) {
    console.error(`[FRONTEND][API  ] Failed GET ${request.nextUrl.pathname} -> ${upstreamPath}`, error);
    return new NextResponse('Failed to load report asset', { status: 502 });
  }
}
