import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://collection-backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET } from '@/app/api/frontend/collections/[...segments]/route';

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

test('GET proxies collection content with search forwarded verbatim (pre-encoded query)', async () => {
  const upstreamResponse = new Response('{"content_html":"<p>항공</p>"}', {
    status: 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
    },
  });
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  // ?path=%ED%95%AD%EA%B3%B5%2F%EC%83%81%EC%9A%A9%EA%B8%B0.html is already-encoded 항공/상용기.html
  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/document/content/html?path=%ED%95%AD%EA%B3%B5%2F%EC%83%81%EC%9A%A9%EA%B8%B0.html',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['document', 'content', 'html'] }),
  });

  // Path segments are per-segment encoded; query is forwarded verbatim (no double-encoding)
  expect(fetchMock).toHaveBeenCalledWith(
    'http://collection-backend.test/api/v1/collections/document/content/html?path=%ED%95%AD%EA%B3%B5%2F%EC%83%81%EC%9A%A9%EA%B8%B0.html',
    expect.objectContaining({ method: 'GET', cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
  expect(response.headers.get('content-type')).toBe('application/json; charset=utf-8');
});

test('GET proxies collection search route without requiring a collection segment', async () => {
  const upstreamResponse = new Response('{"results":[],"degraded":false,"collections":["document","civil"]}', {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/search?q=UNIQUE&collections=document%2Ccivil',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['search'] }),
  });

  expect(fetchMock).toHaveBeenCalledWith(
    'http://collection-backend.test/api/v1/collections/search?q=UNIQUE&collections=document%2Ccivil',
    expect.objectContaining({ method: 'GET', cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
  expect(response.headers.get('content-type')).toBe('application/json');
});

test('GET traversal segment: slash inside a segment is encoded (%2F), keeping segments isolated', async () => {
  // The real traversal/SSRF injection vector is a slash embedded inside a single segment,
  // e.g. segment = "document/../../etc/passwd". encodeURIComponent encodes '/' as '%2F',
  // so the slash can never escape the segment boundary and create a new path component.
  // A plain '..' passed as a discrete segment is forwarded as '..' (encodeURIComponent does
  // not encode '.'); the backend's ensure_within_root rejects it there. Here we verify the
  // slash-injection guard: a segment containing '/' is forwarded with '%2F', not as '/'.
  const upstreamResponse = new Response('ok', { status: 200 });
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/document/content/html',
  );

  // Simulate a segment that embeds a slash — the slash must be encoded, not treated as a separator
  const response = await GET(request, {
    params: Promise.resolve({ segments: ['document', '../x'] }),
  });

  expect(response.status).toBe(200);
  const calledUrl: string = (fetchMock.mock.calls[0]?.[0] as string) ?? '';
  // The embedded slash in '../x' is encoded as %2F — no literal '/../' appears in the upstream URL
  expect(calledUrl).toContain('..%2Fx');
  expect(calledUrl).not.toMatch(/\/\.\.\//);
});

test('GET returns 404 and does not call fetch for unknown collection', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach', { status: 200 }));

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/evil/list',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['evil', 'list'] }),
  });

  expect(response.status).toBe(404);
  await expect(response.text()).resolves.toBe('Unknown collection');
  expect(fetchMock).not.toHaveBeenCalled();
});

test('GET returns 502 and logs when upstream fetch throws', async () => {
  const fetchError = new Error('connect ECONNREFUSED');
  vi.spyOn(global, 'fetch').mockRejectedValue(fetchError);
  const errorLog = vi.spyOn(console, 'error').mockImplementation(() => {});

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/document/content/html',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['document', 'content', 'html'] }),
  });

  expect(response.status).toBe(502);
  await expect(response.text()).resolves.toBe('Failed to load collection asset');
  expect(errorLog).toHaveBeenCalledWith(
    '[FRONTEND][API  ] Failed GET /api/frontend/collections/document/content/html -> /api/v1/collections/document/content/html',
    fetchError,
  );
});

test('GET forwards content-type header from upstream to client response', async () => {
  const upstreamResponse = new Response('{"content_html":"<p>test</p>"}', {
    status: 200,
    headers: {
      'content-type': 'application/json',
      'x-internal-only': 'should-not-forward',
    },
  });
  vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/nsa/content/html?path=test.html',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['nsa', 'content', 'html'] }),
  });

  expect(response.headers.get('content-type')).toBe('application/json');
  expect(response.headers.get('x-internal-only')).toBeNull();
});

test('GET forwards download headers from upstream to client response', async () => {
  const upstreamResponse = new Response('<html>download</html>', {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'content-disposition': "attachment; filename*=utf-8''doc.html",
    },
  });
  vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse);

  const request = createRouteRequest(
    'http://localhost/api/frontend/collections/document/download/html?path=doc.html',
  );

  const response = await GET(request, {
    params: Promise.resolve({ segments: ['document', 'download', 'html'] }),
  });

  expect(response.status).toBe(200);
  expect(response.headers.get('content-type')).toBe('text/html; charset=utf-8');
  expect(response.headers.get('content-disposition')).toBe("attachment; filename*=utf-8''doc.html");
});
