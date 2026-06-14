import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({ getServerApiBase: getServerApiBaseMock }));

import { GET as GET_LIST } from '@/app/api/frontend/ai/conversations/route';
import { DELETE as DELETE_ONE } from '@/app/api/frontend/ai/conversations/[id]/route';

function createRequest(cookie: string | null, searchParams = new URLSearchParams()) {
  return {
    headers: { get: (key: string) => (key.toLowerCase() === 'cookie' ? cookie : null) },
    nextUrl: { searchParams },
  } as unknown as NextRequest;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('list proxy forwards the ai_session cookie to the backend', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response('{"conversations":[]}', { status: 200, headers: { 'content-type': 'application/json' } }),
  );

  await GET_LIST(createRequest('ai_session=abc123'));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:18437/api/v1/ai/conversations',
    expect.objectContaining({
      method: 'GET',
      headers: expect.objectContaining({ cookie: 'ai_session=abc123' }),
    }),
  );
});

test('list proxy relays backend Set-Cookie back to the browser', async () => {
  const upstream = new Response('{"conversations":[]}', {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  upstream.headers.append('set-cookie', 'ai_session=newsess; Path=/; HttpOnly; SameSite=Lax');
  vi.spyOn(global, 'fetch').mockResolvedValue(upstream);

  const response = await GET_LIST(createRequest(null));

  const setCookie = response.headers.get('set-cookie') ?? '';
  expect(setCookie).toContain('ai_session=newsess');
  expect(setCookie).toContain('Path=/');
  expect(setCookie).not.toContain('Domain=');
});

test('delete proxy targets the conversation id and forwards cookie', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response('{"deleted":true}', { status: 200, headers: { 'content-type': 'application/json' } }),
  );

  await DELETE_ONE(createRequest('ai_session=xyz'), { params: Promise.resolve({ id: '42' }) });

  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:18437/api/v1/ai/conversations/42',
    expect.objectContaining({
      method: 'DELETE',
      headers: expect.objectContaining({ cookie: 'ai_session=xyz' }),
    }),
  );
});
