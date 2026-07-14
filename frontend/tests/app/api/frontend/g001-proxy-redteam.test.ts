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
import { DELETE as officeToolsDELETE, GET as officeToolsGET, POST as officeToolsPOST } from '@/app/api/frontend/office-tools/[...segments]/route';
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
])('%s rejects without upstream fetch', async (_name, url, handler, expectedStatus) => {
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
test.each([
  ['encoded dotdot', 'http://localhost/api/frontend/office-tools/%2e%2e/admin/users'],
  ['encoded slash segment', 'http://localhost/api/frontend/office-tools/%2f'],
  ['encoded backslash segment', 'http://localhost/api/frontend/office-tools/jobs%5cadmin%5cpurge'],
])('office-tools %s returns 404 without upstream fetch for every supported verb', async (_name, url) => {
  for (const [method, handler] of [
    ['GET', officeToolsGET],
    ['POST', officeToolsPOST],
    ['DELETE', officeToolsDELETE],
  ] as const) {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('should not reach'));

    const response = await handler(createRouteRequest(url, { method }));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockRestore();
  }
});


test('office-tools GET and streaming POST preserve the same-origin relay contract', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(upstreamResponse());
  const getResponse = await officeToolsGET(createRouteRequest(
    'http://localhost/api/frontend/office-tools/jobs?limit=10',
    { headers: { cookie: 'aeroone_session=owner-session' } },
  ));

  expect(getResponse.status).toBe(200);
  expect(fetchMock).toHaveBeenLastCalledWith(
    'http://backend.test/api/v1/office-tools/jobs?limit=10',
    expect.objectContaining({ method: 'GET', cache: 'no-store', headers: expect.any(Headers) }),
  );

  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('multipart-body'));
      controller.close();
    },
  });
  await officeToolsPOST(createRouteRequest(
    'http://localhost/api/frontend/office-tools/reports/generate',
    {
      method: 'POST',
      body,
      headers: {
        cookie: 'aeroone_session=owner-session',
        'x-csrf-token': 'owner-csrf-token',
        'content-type': 'multipart/form-data; boundary=office-boundary',
      },
    },
  ));

  expect(fetchMock).toHaveBeenLastCalledWith(
    'http://backend.test/api/v1/office-tools/reports/generate',
    expect.objectContaining({
      method: 'POST',
      body,
      duplex: 'half',
      cache: 'no-store',
      headers: expect.any(Headers),
    }),
  );
});
test.each([
  [
    'owner job',
    'http://localhost/api/frontend/office-tools/jobs/job-123',
    'http://backend.test/api/v1/office-tools/jobs/job-123',
    200,
    JSON.stringify({
      outcome: {
        operation: 'owner_delete',
        job_id: 'job-123',
        owner_id: 7,
        logical_bytes: 128,
        physical_bytes: 256,
        partial_bytes_removed: 256,
        removed: true,
        durably_synced: false,
        durability: 'platform_best_effort',
        owner_identity_removed: true,
        owner_identity_durably_synced: false,
        owner_identity_durability: 'platform_best_effort',
        retry_required: false,
      },
    }),
  ],
  [
    'management evidence',
    'http://localhost/api/frontend/office-tools/jobs/evidence/0123456789abcdef0123456789abcdef',
    'http://backend.test/api/v1/office-tools/jobs/evidence/0123456789abcdef0123456789abcdef',
    200,
    '{"item":"corrupt-evidence","outcome":{"removed":true}}',
  ],
])('office-tools %s DELETE relays cookie and CSRF while passing through the backend response', async (
  _name,
  url,
  backendUrl,
  status,
  body,
) => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(new Response(body, {
    status,
    headers: body ? { 'content-type': 'application/json' } : undefined,
  }));

  const response = await officeToolsDELETE(createRouteRequest(url, {
    method: 'DELETE',
    headers: {
      cookie: 'aeroone_session=owner-session',
      'x-csrf-token': 'owner-csrf-token',
      accept: 'application/json',
    },
  }));

  expect(fetchMock).toHaveBeenCalledWith(
    backendUrl,
    expect.objectContaining({ method: 'DELETE', cache: 'no-store', headers: expect.any(Headers) }),
  );
  const relayedHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
  expect(relayedHeaders.get('cookie')).toBe('aeroone_session=owner-session');
  expect(relayedHeaders.get('x-csrf-token')).toBe('owner-csrf-token');
  expect(response.status).toBe(status);
  expect(response.headers.get('content-type')).toBe(body ? 'application/json' : null);
  expect(await response.text()).toBe(body ?? '');
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
