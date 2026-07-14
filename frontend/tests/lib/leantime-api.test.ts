import { ApiError, fetchLeantimeCalendar, fetchLeantimeProjects, fetchLeantimeTasks } from '@/lib/api';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const ENVELOPE_BASE = {
  degraded: false,
  reason: null,
  source: 'leantime',
  fetched_at: '2026-07-14T00:00:00Z',
};

test('fetchLeantimeProjects GETs the leantime proxy and returns the parsed envelope', async () => {
  const payload = {
    ...ENVELOPE_BASE,
    items: [{ id: '1', name: 'Alpha', state: 'active', client_name: 'Client A' }],
  };
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => payload });

  const result = await fetchLeantimeProjects();

  expect(result).toEqual(payload);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/leantime/projects');
  expect(init.method).toBe('GET');
  expect(init.credentials).toBe('include');
});

test('fetchLeantimeTasks GETs the leantime proxy and returns the parsed envelope', async () => {
  const payload = {
    ...ENVELOPE_BASE,
    items: [{ id: 't1', project_id: '1', headline: 'Do the thing', status: 'open', date_to_finish: '2026-08-01' }],
  };
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => payload });

  const result = await fetchLeantimeTasks();

  expect(result).toEqual(payload);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/leantime/tasks');
  expect(init.method).toBe('GET');
});

test('fetchLeantimeCalendar GETs the leantime proxy with encoded start/end query params', async () => {
  const payload = {
    ...ENVELOPE_BASE,
    items: [{ id: 'c1', name: 'Milestone', date_start: '2026-07-14', date_end: '2026-07-15' }],
  };
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => payload });

  const result = await fetchLeantimeCalendar('2026-07-14', '2026-08-13');

  expect(result).toEqual(payload);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/leantime/calendar?start=2026-07-14&end=2026-08-13');
  expect(init.method).toBe('GET');
});

test('fetchLeantimeCalendar encodes special characters in start/end', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...ENVELOPE_BASE, items: [] }) });

  await fetchLeantimeCalendar('2026-07-14T00:00:00+09:00', '2026-08-13T00:00:00+09:00');

  const [path] = fetchMock.mock.calls[0];
  expect(path).toBe(
    '/api/frontend/leantime/calendar?start=2026-07-14T00%3A00%3A00%2B09%3A00&end=2026-08-13T00%3A00%3A00%2B09%3A00',
  );
});

test('leantime fetchers throw ApiError with status on non-2xx responses', async () => {
  fetchMock.mockResolvedValue({ ok: false, status: 403, text: async () => 'Forbidden' });

  await expect(fetchLeantimeProjects()).rejects.toBeInstanceOf(ApiError);
  await expect(fetchLeantimeProjects()).rejects.toMatchObject({ status: 403 });
});
