import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://newsletter-backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET } from '@/app/api/frontend/newsletters/[...segments]/route';

function createRouteRequest(
  url: string,
  headers?: Record<string, string>,
) {
  const headerMap = new Map(
    Object.entries(headers ?? {}).map(([name, value]) => [name.toLowerCase(), value]),
  );

  return {
    headers: {
      get(name: string) {
        return headerMap.get(name.toLowerCase()) ?? null;
      },
    } as Headers,
    nextUrl: new URL(url),
  } as NextRequest;
}

beforeEach(() => {
  vi.spyOn(console, 'info').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('GET proxies newsletter asset responses with mirrored metadata', async () => {
  const upstreamResponse = new Response('rendered html', {
    status: 206,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'content-disposition': 'inline; filename=\"newsletter.html\"',
      'cache-control': 'public, max-age=60',
      etag: 'W/\"newsletter-38\"',
      'last-modified': 'Fri, 04 Apr 2026 12:00:00 GMT',
      'accept-ranges': 'bytes',
      'content-range': 'bytes 0-12/13',
      'x-upstream-internal': 'do-not-forward',
    },
  });
  const arrayBufferSpy = vi
    .spyOn(upstreamResponse, 'arrayBuffer')
    .mockRejectedValue(new Error('route should stream the upstream response'));
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  const request = createRouteRequest(
    'http://localhost/api/frontend/newsletters/38/content/html?preview=1',
    {
      accept: 'text/html',
      range: 'bytes=0-12',
      'if-range': 'W/\"newsletter-38\"',
      'if-none-match': 'W/\"newsletter-38\"',
      'if-modified-since': 'Fri, 04 Apr 2026 12:00:00 GMT',
    },
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['38', 'content', 'html'] }),
  });

  expect(fetchMock).toHaveBeenCalledWith(
    'http://newsletter-backend.test/api/v1/newsletters/38/content/html?preview=1',
    expect.objectContaining({
      method: 'GET',
      cache: 'no-store',
      headers: expect.any(Object),
    }),
  );
  const upstreamHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
  expect(upstreamHeaders.accept).toBe('text/html');
  expect(upstreamHeaders.range).toBe('bytes=0-12');
  expect(upstreamHeaders['if-range']).toBe('W/\"newsletter-38\"');
  expect(upstreamHeaders['if-none-match']).toBe('W/\"newsletter-38\"');
  expect(upstreamHeaders['if-modified-since']).toBe('Fri, 04 Apr 2026 12:00:00 GMT');
  expect(arrayBufferSpy).not.toHaveBeenCalled();
  expect(response.status).toBe(206);
  expect(response.headers.get('content-type')).toBe('text/html; charset=utf-8');
  expect(response.headers.get('content-disposition')).toBe(
    'inline; filename=\"newsletter.html\"',
  );
  expect(response.headers.get('cache-control')).toBe('public, max-age=60');
  expect(response.headers.get('etag')).toBe('W/\"newsletter-38\"');
  expect(response.headers.get('last-modified')).toBe('Fri, 04 Apr 2026 12:00:00 GMT');
  expect(response.headers.get('accept-ranges')).toBe('bytes');
  expect(response.headers.get('content-range')).toBe('bytes 0-12/13');
  expect(response.headers.get('x-upstream-internal')).toBeNull();
  await expect(response.text()).resolves.toBe('rendered html');
});

test('GET returns 502 and logs when upstream fetch fails', async () => {
  const fetchError = new Error('connect ECONNREFUSED');
  vi.spyOn(global, 'fetch').mockRejectedValue(fetchError);
  const errorLog = vi.spyOn(console, 'error').mockImplementation(() => {});

  const request = createRouteRequest(
    'http://localhost/api/frontend/newsletters/38/content/html',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['38', 'content', 'html'] }),
  });

  expect(response.status).toBe(502);
  await expect(response.text()).resolves.toBe('Failed to load newsletter asset');
  expect(errorLog).toHaveBeenCalledWith(
    '[FRONTEND][API  ] Failed GET /api/frontend/newsletters/38/content/html -> /api/v1/newsletters/38/content/html',
    fetchError,
  );
});

