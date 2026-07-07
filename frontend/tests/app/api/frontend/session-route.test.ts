import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://session-backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET } from '@/app/api/frontend/session/route';

function createRouteRequest(cookie?: string) {
  return {
    headers: {
      get(name: string) {
        if (name.toLowerCase() === 'cookie') return cookie ?? null;
        return null;
      },
    } as Headers,
  } as NextRequest;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('GET returns permission and resource hints for authenticated sessions', async () => {
  const fetchMock = vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'analyst', role: 'user' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      permissions: ['collections.nsa.read'],
      resources: [
        { resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' },
      ],
    }), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    'http://127.0.0.1:18437/api/v1/auth/me',
    expect.objectContaining({ headers: { cookie: 'aeroone_session=token' }, cache: 'no-store' }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'http://127.0.0.1:18437/api/v1/auth/effective-permissions',
    expect.objectContaining({ headers: { cookie: 'aeroone_session=token' }, cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({
    authenticated: true,
    username: 'analyst',
    role: 'user',
    isAdmin: false,
    permissions: ['collections.nsa.read'],
    resources: [
      { resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' },
    ],
  });
});

test('GET returns empty hints for anonymous sessions', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('unauthorized', { status: 401 }));

  const response = await GET(createRouteRequest());

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({
    authenticated: false,
    username: null,
    role: null,
    isAdmin: false,
    permissions: [],
    resources: [],
  });
});

test('GET returns unknown identity and empty hints when all upstream bases fail', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED'));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({
    authenticated: null,
    username: null,
    role: null,
    isAdmin: false,
    permissions: [],
    resources: [],
  });
});
