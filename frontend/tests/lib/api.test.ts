import { vi } from 'vitest';

import { getPublicNewsletters } from '@/lib/api';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('requests newsletters list from backend api', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => [],
  });
  vi.stubGlobal('fetch', fetchMock);
  await getPublicNewsletters();
  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:18437/api/v1/newsletters',
    expect.objectContaining({ cache: 'no-store' }),
  );
});
