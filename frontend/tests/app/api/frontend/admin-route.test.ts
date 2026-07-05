import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET, POST, PUT } from '@/app/api/frontend/admin/[...segments]/route';

function createRouteRequest(url: string, init?: { method?: string; headers?: Record<string, string> }) {
  return {
    url,
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
    body: undefined,
  } as unknown as NextRequest;
}

function upstreamWithCookies() {
  const response = new Response('{"ok":true}', {
    status: 201,
    headers: { 'content-type': 'application/json' },
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

test('POST relays admin path, query, method, cookie, csrf and multi Set-Cookie', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamWithCookies());

  const response = await POST(createRouteRequest('http://localhost/api/frontend/admin/users?active=true', {
    method: 'POST',
    headers: {
      cookie: 'aeroone_session=old',
      'x-csrf-token': 'csrf-token',
      'content-type': 'multipart/form-data; boundary=----test',
      accept: 'application/json',
    },
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/admin/users?active=true',
    expect.objectContaining({ method: 'POST', cache: 'no-store', headers: expect.any(Headers) }),
  );
  const relayedHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
  expect(relayedHeaders.get('cookie')).toBe('aeroone_session=old');
  expect(relayedHeaders.get('x-csrf-token')).toBe('csrf-token');
  expect(relayedHeaders.get('content-type')).toBe('multipart/form-data; boundary=----test');
  expect(relayedHeaders.get('accept')).toBe('application/json');
  expect(response.status).toBe(201);
  expect(response.headers.get('set-cookie')).toContain('aeroone_session=admin');
  expect(response.headers.get('set-cookie')).toContain('csrf_token=admin-csrf');
});

test.each([
  ['literal dotdot', 'http://localhost/api/frontend/admin/..'],
  ['encoded dotdot', 'http://localhost/api/frontend/admin/%2e%2e/users'],
  ['encoded slash', 'http://localhost/api/frontend/admin/users%2f1'],
  ['encoded backslash', 'http://localhost/api/frontend/admin/users%5c1'],
  ['non-admin encoded path escape', 'http://localhost/api/frontend/admin/%2fapi%2fv1%2fauth%2fme'],
  ['search excluded from admin proxy', 'http://localhost/api/frontend/admin/search?q=test'],
])('GET rejects %s with 404 and no upstream fetch', async (_name, url) => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await GET(createRouteRequest(url));

  expect(response.status).toBe(404);
  expect(fetchMock).not.toHaveBeenCalled();
});

test('PUT rejects disallowed method with 405 and no upstream fetch', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await PUT(createRouteRequest('http://localhost/api/frontend/admin/users', { method: 'PUT' }));

  expect(response.status).toBe(405);
  expect(fetchMock).not.toHaveBeenCalled();
});
