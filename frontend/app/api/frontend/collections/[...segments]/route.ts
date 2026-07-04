import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';
import { buildCollectionUpstreamPath, isAllowedCollection } from '@/lib/collection-proxy';

export const dynamic = 'force-dynamic';

const FORWARDED_UPSTREAM_RESPONSE_HEADERS = [
  'content-type',
  'content-disposition',
  'cache-control',
  'content-language',
  'etag',
  'last-modified',
  'accept-ranges',
  'content-range',
] as const;

const FORWARDED_UPSTREAM_REQUEST_HEADERS = [
  'accept',
  'range',
  'if-range',
  'if-none-match',
  'if-modified-since',
  // Forward the session cookie so backend collection authorization (e.g. NSA
  // access control) sees the real caller instead of treating them as anonymous.
  'cookie',
] as const;

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  const { segments } = await context.params;

  if (segments[0] !== 'search' && !isAllowedCollection(segments[0])) {
    return new NextResponse('Unknown collection', { status: 404 });
  }

  const upstreamPath = buildCollectionUpstreamPath(segments, request.nextUrl.search);
  const upstreamUrl = `${getServerApiBase()}${upstreamPath}`;

  console.info(
    `[FRONTEND][API  ] GET ${request.nextUrl.pathname}${request.nextUrl.search} -> ${upstreamPath}`,
  );

  try {
    const upstreamRequestHeaders: Record<string, string> = {};
    for (const headerName of FORWARDED_UPSTREAM_REQUEST_HEADERS) {
      const headerValue = request.headers.get(headerName);
      if (headerValue) {
        upstreamRequestHeaders[headerName] = headerValue;
      }
    }

    const upstreamResponse = await fetch(upstreamUrl, {
      method: 'GET',
      cache: 'no-store',
      headers: upstreamRequestHeaders,
    });

    console.info(
      `[FRONTEND][API  ] ${upstreamResponse.status} ${upstreamPath}`,
    );

    const response = new NextResponse(upstreamResponse.body, {
      status: upstreamResponse.status,
    });

    for (const headerName of FORWARDED_UPSTREAM_RESPONSE_HEADERS) {
      const headerValue = upstreamResponse.headers.get(headerName);
      if (headerValue) {
        response.headers.set(headerName, headerValue);
      }
    }

    return response;
  } catch (error) {
    console.error(
      `[FRONTEND][API  ] Failed GET ${request.nextUrl.pathname}${request.nextUrl.search} -> ${upstreamPath}`,
      error,
    );

    return new NextResponse('Failed to load collection asset', {
      status: 502,
    });
  }
}
