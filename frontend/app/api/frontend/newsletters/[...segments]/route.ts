import { NextRequest, NextResponse } from 'next/server';

import { getServerApiBase } from '@/lib/api';
import { buildNewsletterUpstreamPath } from '@/lib/newsletter-observability';

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

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ segments: string[] }> },
) {
  const { segments } = await context.params;
  const upstreamPath = buildNewsletterUpstreamPath(segments, request.nextUrl.search);
  const upstreamUrl = `${getServerApiBase()}${upstreamPath}`;

  console.info(
    `[FRONTEND][API  ] GET ${request.nextUrl.pathname}${request.nextUrl.search} -> ${upstreamPath}`,
  );

  try {
    const upstreamResponse = await fetch(upstreamUrl, {
      method: 'GET',
      cache: 'no-store',
      headers: {
        accept: request.headers.get('accept') ?? '*/*',
      },
    });

    console.info(
      `[FRONTEND][API  ] ${upstreamResponse.status} ${upstreamPath}`,
    );

    const body = await upstreamResponse.arrayBuffer();
    const response = new NextResponse(body, {
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

    return new NextResponse('Failed to load newsletter asset', {
      status: 502,
    });
  }
}
