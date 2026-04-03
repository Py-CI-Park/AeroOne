import { vi } from 'vitest';

import {
  buildNewsletterProxyPath,
  buildNewsletterUpstreamPath,
  loggedServerFetchJson,
} from '@/lib/newsletter-observability';

afterEach(() => {
  vi.restoreAllMocks();
});

test('maps newsletter backend paths to same-origin proxy paths', () => {
  expect(buildNewsletterProxyPath('/api/v1/newsletters/13/content/html')).toBe(
    '/api/frontend/newsletters/13/content/html',
  );
  expect(buildNewsletterProxyPath('/api/v1/newsletters/13/download/pdf')).toBe(
    '/api/frontend/newsletters/13/download/pdf',
  );
});

test('rejects non-newsletter backend paths', () => {
  expect(() => buildNewsletterProxyPath('/api/v1/admin/newsletters')).toThrow(
    'Only newsletter read paths can be proxied',
  );
});

test('builds backend upstream path from catch-all route segments', () => {
  expect(buildNewsletterUpstreamPath(['latest'])).toBe('/api/v1/newsletters/latest');
  expect(buildNewsletterUpstreamPath(['13', 'content', 'html'], '?preview=1')).toBe(
    '/api/v1/newsletters/13/content/html?preview=1',
  );
});

test('buildNewsletterUpstreamPath preserves nested newsletter asset paths', () => {
  expect(buildNewsletterUpstreamPath(['38', 'content', 'html'])).toBe(
    '/api/v1/newsletters/38/content/html',
  );
  expect(buildNewsletterUpstreamPath(['38', 'download', 'pdf'])).toBe(
    '/api/v1/newsletters/38/download/pdf',
  );
});

test('loggedServerFetchJson logs request and response around backend fetch', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [{ id: 1 }],
  });
  const logger = vi.fn();

  const result = await loggedServerFetchJson<{ id: number }[]>({
    label: 'newsletters.list',
    baseUrl: 'http://localhost:18437',
    path: '/api/v1/newsletters',
    fetchImpl: fetchMock,
    log: logger,
  });

  expect(result).toEqual([{ id: 1 }]);
  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters',
    expect.objectContaining({ cache: 'no-store' }),
  );
  expect(logger).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
  expect(logger).toHaveBeenNthCalledWith(
    2,
    '[FRONTEND][FETCH] newsletters.list <- 200 /api/v1/newsletters',
  );
});

test('loggedServerFetchJson forces no-store even when init specifies a different cache mode', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ ok: true }),
  });

  await loggedServerFetchJson<{ ok: boolean }>({
    label: 'newsletters.cache',
    baseUrl: 'http://localhost:18437',
    path: '/api/v1/newsletters/latest',
    fetchImpl: fetchMock,
    init: {
      cache: 'force-cache',
      headers: {
        'x-test': '1',
      },
    },
    log: vi.fn(),
  });

  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters/latest',
    expect.objectContaining({
      cache: 'no-store',
      headers: {
        'x-test': '1',
      },
    }),
  );
});

test('loggedServerFetchJson logs and rethrows when fetch rejects', async () => {
  const fetchError = new Error('connect ECONNREFUSED');
  const fetchMock = vi.fn().mockRejectedValue(fetchError);
  const logger = vi.fn();

  await expect(
    loggedServerFetchJson({
      label: 'newsletters.list',
      baseUrl: 'http://localhost:18437',
      path: '/api/v1/newsletters',
      fetchImpl: fetchMock,
      log: logger,
    }),
  ).rejects.toThrow(fetchError);

  expect(logger).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
  expect(logger).toHaveBeenNthCalledWith(
    2,
    '[FRONTEND][FETCH] newsletters.list !! /api/v1/newsletters connect ECONNREFUSED',
  );
});

test('loggedServerFetchJson logs and rethrows when json parsing fails', async () => {
  const parseError = new Error('Unexpected token < in JSON');
  const logger = vi.fn();

  await expect(
    loggedServerFetchJson({
      label: 'newsletters.list',
      baseUrl: 'http://localhost:18437',
      path: '/api/v1/newsletters',
      fetchImpl: vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: vi.fn().mockRejectedValue(parseError),
      }),
      log: logger,
    }),
  ).rejects.toThrow(parseError);

  expect(logger).toHaveBeenNthCalledWith(
    1,
    '[FRONTEND][FETCH] newsletters.list -> /api/v1/newsletters',
  );
  expect(logger).toHaveBeenNthCalledWith(
    2,
    '[FRONTEND][FETCH] newsletters.list <- 200 /api/v1/newsletters',
  );
  expect(logger).toHaveBeenNthCalledWith(
    3,
    '[FRONTEND][FETCH] newsletters.list !! /api/v1/newsletters Unexpected token < in JSON',
  );
});
