import { resolveDashboardAuth } from '@/lib/server-auth';

const { cookiesMock, getServerApiBaseMock } = vi.hoisted(() => ({
  cookiesMock: vi.fn<() => { name: string; value: string }[]>(),
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({ getAll: cookiesMock })),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

beforeEach(() => {
  cookiesMock.mockReturnValue([]);
  getServerApiBaseMock.mockReturnValue('http://backend.test');
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  cookiesMock.mockReset();
  getServerApiBaseMock.mockReset();
  vi.unstubAllGlobals();
});

test('returns anonymous without contacting auth when no cookies exist', async () => {
  await expect(resolveDashboardAuth()).resolves.toEqual({ authenticated: false, isAdmin: false });
  expect(fetch).not.toHaveBeenCalled();
});

test('returns a signed-in user from one fail-closed auth request', async () => {
  cookiesMock.mockReturnValue([{ name: 'aeroone_session', value: 'session-token' }]);
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ username: '민지', role: 'user' }), { status: 200 }));

  await expect(resolveDashboardAuth()).resolves.toEqual({
    authenticated: true,
    isAdmin: false,
    username: '민지',
  });
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch).toHaveBeenCalledWith('http://backend.test/api/v1/auth/me', {
    cache: 'no-store',
    headers: { cookie: 'aeroone_session=session-token' },
  });
});

test('marks administrators explicitly', async () => {
  cookiesMock.mockReturnValue([{ name: 'aeroone_session', value: 'admin-token' }]);
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ username: '운영팀', role: 'admin' }), { status: 200 }));

  await expect(resolveDashboardAuth()).resolves.toEqual({
    authenticated: true,
    isAdmin: true,
    username: '운영팀',
  });
});

test.each([
  ['rejected session', () => Promise.resolve(new Response(null, { status: 401 }))],
  ['backend outage', () => Promise.reject(new Error('offline'))],
])('fails closed to anonymous for %s', async (_label, responseFactory) => {
  cookiesMock.mockReturnValue([{ name: 'aeroone_session', value: 'stale-token' }]);
  vi.mocked(fetch).mockImplementation(responseFactory);

  await expect(resolveDashboardAuth()).resolves.toEqual({ authenticated: false, isAdmin: false });
});
