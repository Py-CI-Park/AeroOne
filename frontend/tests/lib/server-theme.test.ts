import { getAppTheme } from '@/lib/server-theme';

const { cookieThemeMock } = vi.hoisted(() => ({
  cookieThemeMock: vi.fn<() => string | undefined>(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(() => ({
    getAll: () => (cookieThemeMock() ? [{ name: 'aeroone_theme', value: cookieThemeMock() }] : []),
  })),
}));

afterEach(() => {
  vi.unstubAllEnvs();
  cookieThemeMock.mockReset();
});

test('uses query theme before cookie and environment', async () => {
  cookieThemeMock.mockReturnValue('dark');
  vi.stubEnv('NEWSLETTERS_THEME', 'dark');

  await expect(getAppTheme('light')).resolves.toBe('light');
});

test('uses cookie theme before environment when query is absent', async () => {
  cookieThemeMock.mockReturnValue('dark');
  vi.stubEnv('NEWSLETTERS_THEME', 'light');

  await expect(getAppTheme()).resolves.toBe('dark');
});
