import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET as adminGET } from '@/app/api/frontend/admin/[...segments]/route';
import { GET, POST } from '@/app/api/frontend/search/unified/route';

function createRouteRequest(url: string, init?: { method?: string; headers?: Record<string, string> }) {
  return {
    url,
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
    body: undefined,
  } as unknown as NextRequest;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('GET relays unified search to backend admin search with query params', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('{"results":[]}', {
    status: 200,
    headers: { 'content-type': 'application/json' },
  }));

  const response = await GET(createRouteRequest('http://localhost/api/frontend/search/unified?q=jet&include_nsa=true', {
    headers: { cookie: 'aeroone_session=token', accept: 'application/json' },
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/admin/search?q=jet&include_nsa=true',
    expect.objectContaining({ method: 'GET', cache: 'no-store', headers: expect.any(Headers) }),
  );
  const relayedHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
  expect(relayedHeaders.get('cookie')).toBe('aeroone_session=token');
  expect(relayedHeaders.get('accept')).toBe('application/json');
  expect(response.status).toBe(200);
});

test('POST rejects unified search with 405 and no upstream fetch', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await POST(createRouteRequest('http://localhost/api/frontend/search/unified?q=jet', { method: 'POST' }));

  expect(response.status).toBe(405);
  expect(fetchMock).not.toHaveBeenCalled();
});

test('admin proxy does not expose search endpoint', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await adminGET(createRouteRequest('http://localhost/api/frontend/admin/search?q=jet'));

  expect(response.status).toBe(404);
  expect(fetchMock).not.toHaveBeenCalled();
});
