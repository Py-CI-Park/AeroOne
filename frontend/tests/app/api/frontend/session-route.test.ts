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

const MODULES = [
  { key: 'document', is_enabled: true },
  { key: 'nsa', is_enabled: true },
  { key: 'ai', is_enabled: true },
];

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('GET returns full derived flags and hints for an authenticated non-admin user with a resource grant', async () => {
  const fetchMock = vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'analyst', role: 'user' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      permissions: [],
      resources: [
        { resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' },
      ],
    }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(MODULES), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    'http://session-backend.test/api/v1/auth/me',
    expect.objectContaining({ headers: { cookie: 'aeroone_session=token' }, cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toBe('no-store');
  await expect(response.json()).resolves.toEqual({
    authenticated: true,
    username: 'analyst',
    role: 'user',
    is_admin: false,
    can_view_document: true,
    can_view_nsa: true,
    can_use_ai: true,
    permissions: [],
    resources: [
      { resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' },
    ],
    requires_password_change: false,
  });
});

test('GET grants NSA visibility for admins even without an explicit permission or resource grant', async () => {
  vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'root', role: 'admin' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ permissions: [], resources: [] }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(MODULES), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  await expect(response.json()).resolves.toEqual({
    authenticated: true,
    username: 'root',
    role: 'admin',
    is_admin: true,
    can_view_document: true,
    can_view_nsa: true,
    can_use_ai: true,
    permissions: [],
    resources: [],
    requires_password_change: false,
  });
});

test('GET grants NSA visibility via a global permission string without a resource grant', async () => {
  vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'analyst', role: 'user' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ permissions: ['collections.nsa.read'], resources: [] }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(MODULES), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  await expect(response.json()).resolves.toMatchObject({ can_view_nsa: true });
});

test('GET accepts the legacy search.nsa.read permission key', async () => {
  vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'analyst', role: 'user' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ permissions: ['search.nsa.read'], resources: [] }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify(MODULES), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  await expect(response.json()).resolves.toMatchObject({ can_view_nsa: true });
});

test('GET withholds NSA and AI visibility when the corresponding module is disabled', async () => {
  vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'root', role: 'admin' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ permissions: [], resources: [] }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify([
      { key: 'document', is_enabled: true },
      { key: 'nsa', is_enabled: false },
      { key: 'ai', is_enabled: false },
    ]), { status: 200 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  await expect(response.json()).resolves.toMatchObject({
    is_admin: true,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
  });
});

test('GET returns empty hints and default flags for anonymous sessions, keeping Document public', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('unauthorized', { status: 401 }));

  const response = await GET(createRouteRequest());

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(response.status).toBe(200);
  expect(response.headers.get('cache-control')).toBe('no-store');
  await expect(response.json()).resolves.toEqual({
    authenticated: false,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
    requires_password_change: false,
  });
});

test('GET returns unknown identity, protected flags false, and public Document when the backend is unreachable', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockRejectedValue(new Error('connect ECONNREFUSED'));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(response.status).toBe(200);
  const body = await response.json();
  expect(body).toEqual({
    authenticated: null,
    username: null,
    role: null,
    is_admin: false,
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
    permissions: [],
    resources: [],
    requires_password_change: false,
  });
  expect(JSON.stringify(body)).not.toContain('ECONNREFUSED');
});

test('GET falls back to public Document access when the service-modules fetch fails, without granting NSA or AI', async () => {
  vi.spyOn(global, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: 'analyst', role: 'user' }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ permissions: [], resources: [] }), { status: 200 }))
    .mockResolvedValueOnce(new Response('backend error', { status: 500 }));

  const response = await GET(createRouteRequest('aeroone_session=token'));

  const body = await response.json();
  expect(body).toMatchObject({
    can_view_document: true,
    can_view_nsa: false,
    can_use_ai: false,
  });
  expect(JSON.stringify(body)).not.toContain('backend error');
});
