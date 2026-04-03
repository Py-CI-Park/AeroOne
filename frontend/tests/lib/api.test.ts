import { vi } from 'vitest';

import {
  fetchLatestNewsletter,
  fetchNewsletterCalendar,
  fetchNewsletterDetail,
  fetchNewsletters,
  getNewsletterProxyPath,
  getPublicNewsletters,
} from '@/lib/api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
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
    'http://localhost:18437/api/v1/newsletters',
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
    'http://localhost:18437/api/v1/newsletters/latest',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(infoMock).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.latest -> /api/v1/newsletters/latest',
  );
});

test('builds frontend newsletter proxy paths from backend asset urls', () => {
  expect(getNewsletterProxyPath('/api/v1/newsletters/9/content/html')).toBe(
    '/api/frontend/newsletters/9/content/html',
  );
});
