import { vi } from 'vitest';

import {
  fetchAiStatus,
  fetchCollectionContent,
  fetchCollectionList,
  fetchDocumentContent,
  fetchClientSession,
  getServerApiBase,
  fetchLatestNewsletter,
  getNewsletterProxyPath,
  getPublicNewsletters,
  login,
  changeOwnPassword,
  fetchAdminSummary,
  fetchConnectedUsers,
  purgeSessions,
  fetchUnifiedSearch,
} from '@/lib/api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

test('trims whitespace from configured backend api bases', async () => {
  vi.resetModules();
  vi.stubEnv('SERVER_API_BASE_URL', ' http://127.0.0.1:18437 \r\n');
  vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', ' http://127.0.0.1:18437/ \n');

  const api = await import('@/lib/api');

  expect(api.getServerApiBase()).toBe('http://127.0.0.1:18437');
  expect(api.getBrowserApiBase()).toBe('http://127.0.0.1:18437');
});

test('requests newsletters list from backend api', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
  const infoMock = vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.stubGlobal('fetch', fetchMock);

  await getPublicNewsletters();

  expect(fetchMock).toHaveBeenCalledWith(
    `${getServerApiBase()}/api/v1/newsletters`,
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(infoMock).toHaveBeenCalledWith(
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
});

test('requests latest newsletter from backend api with logging', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ id: 1 }),
  });
  const infoMock = vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.stubGlobal('fetch', fetchMock);

  await fetchLatestNewsletter();

  expect(fetchMock).toHaveBeenCalledWith(
    `${getServerApiBase()}/api/v1/newsletters/latest`,
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(infoMock).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.latest -> /api/v1/newsletters/latest',
  );
});

test('fetchAiStatus accepts degraded JSON payloads from same-origin proxy', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: false,
    status: 502,
    text: async () => '{"status":"unavailable","enabled":true,"base_url":"","model":"gemma4:12b","reachable":false,"model_available":false,"detail":"AI backend unavailable"}',
  });
  vi.stubGlobal('fetch', fetchMock);

  const status = await fetchAiStatus();

  expect(fetchMock).toHaveBeenCalledWith('/api/frontend/ai/status', { cache: 'no-store' });
  expect(status.status).toBe('unavailable');
  expect(status.detail).toBe('AI backend unavailable');
});

test('builds frontend newsletter proxy paths from backend asset urls', () => {
  expect(getNewsletterProxyPath('/api/v1/newsletters/9/content/html')).toBe(
    '/api/frontend/newsletters/9/content/html',
  );
});

// C1 회귀 가드 — 원버그(외부 PC에서 localhost 직접호출로 Failed to fetch)를 잡는 단언.
// fetchCollectionContent 가 same-origin 상대경로를 쓰고 localhost:18437 를 붙이지 않는지 확인.
test('fetchCollectionContent calls same-origin relative url, never localhost', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ asset_type: 'html', content_html: '<p>ok</p>' }),
  });
  vi.stubGlobal('fetch', fetchMock);

  await fetchCollectionContent('document', 'sub/doc.html');

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const calledUrl: string = fetchMock.mock.calls[0][0] as string;
  expect(calledUrl).toMatch(/^\/api\/frontend\/collections\/document\/content\/html\?path=/);
  expect(calledUrl).not.toContain('localhost:18437');
  expect(calledUrl).not.toContain('http://');
});

test('fetchCollectionList calls same-origin relative url for nsa, never localhost', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ documents: [] }),
  });
  vi.stubGlobal('fetch', fetchMock);

  await fetchCollectionList('nsa');

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const calledUrl: string = fetchMock.mock.calls[0][0] as string;
  expect(calledUrl).toBe('/api/frontend/collections/nsa/list');
  expect(calledUrl).not.toContain('localhost');
  expect(calledUrl).not.toContain('http://');
});

test('fetchDocumentContent delegates to collection content proxy path', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ asset_type: 'html', content_html: '<p>doc</p>' }),
  });
  vi.stubGlobal('fetch', fetchMock);

  await fetchDocumentContent('x.html');

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const calledUrl: string = fetchMock.mock.calls[0][0] as string;
  expect(calledUrl).toMatch(/^\/api\/frontend\/collections\/document\/content\/html\?path=x\.html/);
});

test('fetchClientSession calls same-origin session route with credentials', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      authenticated: true,
      role: 'user',
      isAdmin: false,
      permissions: ['collections.nsa.read'],
      resources: [{ resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }],
    }),
  });
  vi.stubGlobal('fetch', fetchMock);

  const session = await fetchClientSession();

  expect(fetchMock).toHaveBeenCalledWith('/api/frontend/session', {
    credentials: 'include',
    cache: 'no-store',
  });
  expect(session.permissions).toEqual(['collections.nsa.read']);
  expect(session.resources).toEqual([
    { resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' },
  ]);
});


test('auth and admin helpers call same-origin frontend proxy paths, never backend origins', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
  } as Response);

  await login('admin', 'secret');
  await changeOwnPassword('old', 'new', 'csrf-token');
  await fetchAdminSummary();
  await fetchConnectedUsers();
  await fetchUnifiedSearch('jet', true);

  const calledUrls = fetchMock.mock.calls.map((call) => call[0] as string);
  expect(calledUrls).toEqual([
    '/api/frontend/auth/login',
    '/api/frontend/auth/change-password',
    '/api/frontend/admin/dashboard',
    '/api/frontend/admin/sessions',
    '/api/frontend/search/unified?q=jet&include_nsa=true',
  ]);
  for (const calledUrl of calledUrls) {
    expect(calledUrl).toMatch(/^\/api\/frontend\//);
    expect(calledUrl).not.toContain('localhost');
    expect(calledUrl).not.toContain('http://');
    expect(calledUrl).not.toContain('/api/v1/admin');
    expect(calledUrl).not.toContain('/api/v1/auth');
  }
  fetchMock.mockRestore();
});

test('purgeSessions sends csrf header to same-origin admin proxy', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({ ok: true, status: 200, json: async () => ({ login_events_deleted: 1, session_activity_deleted: 2 }) } as Response);
  await purgeSessions('csrf-token');
  expect(fetchMock).toHaveBeenCalledWith('/api/frontend/admin/sessions/purge', expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'X-CSRF-Token': 'csrf-token' }) }));
  fetchMock.mockRestore();
});
