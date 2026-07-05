import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET, POST, PUT } from '@/app/api/frontend/auth/[...segments]/route';

function createRouteRequest(url: string, init?: { method?: string; headers?: Record<string, string> }) {
  return {
    url,
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
    body: undefined,
  } as unknown as NextRequest;
}

function upstreamJsonWithCookies(payload: unknown) {
  const response = new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  (response.headers as Headers & { getSetCookie: () => string[] }).getSetCookie = () => [
    'aeroone_session=one; Path=/; HttpOnly',
    'csrf_token=two; Path=/',
  ];
  return response;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('POST relays auth login method, cookie, csrf, content headers and multi Set-Cookie', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamJsonWithCookies({ ok: true }));

  const response = await POST(createRouteRequest('http://localhost/api/frontend/auth/login', {
    method: 'POST',
    headers: {
      cookie: 'aeroone_session=old',
      'x-csrf-token': 'csrf-token',
      'content-type': 'application/json',
      accept: 'application/json',
    },
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/auth/login',
    expect.objectContaining({
      method: 'POST',
      cache: 'no-store',
      headers: expect.any(Headers),
    }),
  );
  const relayedHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
  expect(relayedHeaders.get('cookie')).toBe('aeroone_session=old');
  expect(relayedHeaders.get('x-csrf-token')).toBe('csrf-token');
  expect(relayedHeaders.get('content-type')).toBe('application/json');
  expect(relayedHeaders.get('accept')).toBe('application/json');
  expect(response.status).toBe(200);
  expect(response.headers.get('set-cookie')).toContain('aeroone_session=one');
  expect(response.headers.get('set-cookie')).toContain('csrf_token=two');
});

test.each([
  ['literal dotdot', 'http://localhost/api/frontend/auth/..'],
  ['encoded dotdot', 'http://localhost/api/frontend/auth/%2e%2e'],
  ['encoded slash', 'http://localhost/api/frontend/auth/login%2fextra'],
  ['encoded backslash', 'http://localhost/api/frontend/auth/login%5cextra'],
  ['unknown segment', 'http://localhost/api/frontend/auth/profile'],
])('GET rejects %s with 404 and no upstream fetch', async (_name, url) => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await GET(createRouteRequest(url));

  expect(response.status).toBe(404);
  expect(fetchMock).not.toHaveBeenCalled();
});

test('PUT rejects disallowed method with 405 and no upstream fetch', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await PUT(createRouteRequest('http://localhost/api/frontend/auth/login', { method: 'PUT' }));

  expect(response.status).toBe(405);
  expect(fetchMock).not.toHaveBeenCalled();
});
