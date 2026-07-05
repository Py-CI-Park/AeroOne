import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET as adminGET, POST as adminPOST, PUT as adminPUT } from '@/app/api/frontend/admin/[...segments]/route';
import { GET as authGET } from '@/app/api/frontend/auth/[...segments]/route';
import { GET as searchGET } from '@/app/api/frontend/search/unified/route';

function createRouteRequest(url: string, init?: { method?: string; headers?: Record<string, string>; body?: ReadableStream<Uint8Array> }) {
  return {
    url,
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
    body: init?.body,
  } as unknown as NextRequest;
}

function upstreamResponse(body = '{"ok":true}', headers: Record<string, string> = {}) {
  const response = new Response(body, {
    status: 200,
    headers: { 'content-type': 'application/json', ...headers },
  });
  (response.headers as Headers & { getSetCookie: () => string[] }).getSetCookie = () => [
    'aeroone_session=admin; Path=/; HttpOnly',
    'csrf_token=admin-csrf; Path=/',
  ];
  return response;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test.each([
  ['admin search excluded', 'http://localhost/api/frontend/admin/search?q=jet', adminGET, 404],
  ['literal traversal into auth', 'http://localhost/api/frontend/admin/../auth/login', adminGET, 404],
  ['encoded dotdot', 'http://localhost/api/frontend/admin/%2e%2e/x', adminGET, 404],
  ['encoded slash segment', 'http://localhost/api/frontend/admin/%2f', adminGET, 404],
  ['encoded backslash segment', 'http://localhost/api/frontend/admin/foo%5cbar', adminGET, 404],
  ['encoded search bypass', 'http://localhost/api/frontend/admin/%73earch?q=jet', adminGET, 404],
  ['unknown auth segment', 'http://localhost/api/frontend/auth/register', authGET, 404],
  ['disallowed admin method', 'http://localhost/api/frontend/admin/users', adminPUT, 405],
])('%s returns %i without upstream fetch', async (_name, url, handler, expectedStatus) => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await handler(createRouteRequest(url, { method: expectedStatus === 405 ? 'PUT' : 'GET' }));

  expect(response.status).toBe(expectedStatus);
  expect(fetchMock).not.toHaveBeenCalled();
});

test.each([
  ['GET', adminGET],
  ['POST', adminPOST],
])('allowed admin %s relays cookie, csrf and multiple Set-Cookie headers', async (method, handler) => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse());

  const response = await handler(createRouteRequest('http://localhost/api/frontend/admin/users?active=true', {
    method,
    headers: {
      cookie: 'aeroone_session=old',
      'x-csrf-token': 'csrf-token',
      accept: 'application/json',
      'content-type': 'application/json',
    },
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/admin/users?active=true',
    expect.objectContaining({ method, cache: 'no-store', headers: expect.any(Headers) }),
  );
  const relayedHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
  expect(relayedHeaders.get('cookie')).toBe('aeroone_session=old');
  expect(relayedHeaders.get('x-csrf-token')).toBe('csrf-token');
  expect(response.headers.get('set-cookie')).toContain('aeroone_session=admin');
  expect(response.headers.get('set-cookie')).toContain('csrf_token=admin-csrf');
});

test('search unified relays only to backend admin search', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse('{"results":[]}'));

  const response = await searchGET(createRouteRequest('http://localhost/api/frontend/search/unified?q=jet&include_nsa=true', {
    headers: { cookie: 'aeroone_session=token', 'x-csrf-token': 'csrf-token' },
  }));

  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/admin/search?q=jet&include_nsa=true',
    expect.objectContaining({ method: 'GET', cache: 'no-store', headers: expect.any(Headers) }),
  );
});

test.each([
  ['backup download', 'http://localhost/api/frontend/admin/backups/1/download', 'application/zip', 'attachment; filename="aeroone-backup-test.zip"', '1234'],
  ['read-events csv', 'http://localhost/api/frontend/admin/read-events.csv', 'text/csv; charset=utf-8', 'attachment; filename="read-events.csv"', '42'],
])('%s now preserves Content-Disposition and Content-Length through frontend proxy', async (_name, url, contentType, disposition, length) => {
  vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse('payload', {
    'content-type': contentType,
    'content-disposition': disposition,
    'content-length': length,
  }));

  const response = await adminGET(createRouteRequest(url));

  expect(response.status).toBe(200);
  expect(response.headers.get('content-type')).toBe(contentType);
  expect(response.headers.get('content-disposition')).toBe(disposition);
  expect(response.headers.get('content-length')).toBe(length);
});
