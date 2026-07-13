import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET, POST } from '@/app/api/frontend/auth/[...segments]/route';

function createRouteRequest(
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: BodyInit },
) {
  return {
    url,
    method: init?.method ?? 'GET',
    headers: new Headers(init?.headers),
    body: init?.body,
  } as unknown as NextRequest;
}

function upstreamJsonWithCookies(payload: unknown) {
  const response = new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  (response.headers as Headers & { getSetCookie: () => string[] }).getSetCookie = () => [
    'aeroone_session=one; Expires=Wed, 15 Jul 2026 12:00:00 GMT; Path=/; HttpOnly',
    'csrf_token=two; Path=/; SameSite=Lax',
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
      authorization: 'Bearer must-not-forward',
      host: 'attacker.invalid',
      'x-forwarded-for': '203.0.113.8',
      connection: 'keep-alive',
      'x-unrelated': 'must-not-forward',
    },
    body: '{"username":"admin","password":"synthetic"}',
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://backend.test/api/v1/auth/login',
    expect.objectContaining({
      method: 'POST',
      cache: 'no-store',
      headers: expect.any(Headers),
    }),
  );
  const fetchInit = fetchMock.mock.calls[0]?.[1] as RequestInit & { duplex?: string };
  const relayedHeaders = fetchInit.headers as Headers;
  expect(Object.fromEntries(relayedHeaders.entries())).toEqual({
    accept: 'application/json',
    'content-type': 'application/json',
    cookie: 'aeroone_session=old',
    'x-csrf-token': 'csrf-token',
  });
  expect(fetchInit.body).toBe('{"username":"admin","password":"synthetic"}');
  expect(fetchInit.duplex).toBe('half');
  expect(response.status).toBe(200);
  const setCookies = (
    response.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie?.();
  expect(setCookies).toEqual([
    'aeroone_session=one; Expires=Wed, 15 Jul 2026 12:00:00 GMT; Path=/; HttpOnly',
    'csrf_token=two; Path=/; SameSite=Lax',
  ]);
  expect(response.headers.get('cache-control')).toBe('no-store');
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

test('unsupported method is rejected with no-store and no upstream fetch', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

  const response = await POST(createRouteRequest('http://localhost/api/frontend/auth/login', { method: 'PUT' }));

  expect(response.status).toBe(405);
  expect(response.headers.get('cache-control')).toBe('no-store');
  expect(fetchMock).not.toHaveBeenCalled();
});

test.each([401, 422, 500])('proxied %s response is no-store and hides backend body', async (status) => {
  vi.spyOn(global, 'fetch').mockResolvedValue(new Response('private backend detail', {
    status,
    headers: { 'content-type': 'application/json', 'content-length': '99' },
  }));

  const response = await POST(createRouteRequest('http://localhost/api/frontend/auth/login', { method: 'POST' }));

  expect(response.status).toBe(status);
  expect(response.headers.get('cache-control')).toBe('no-store');
  expect(response.headers.get('content-type')).toContain('text/plain');
  expect(response.headers.get('content-length')).toBeNull();
  const body = await response.text();
  expect(body).not.toContain('private backend detail');
  expect(body).toBe('요청을 처리할 수 없습니다.');
});
