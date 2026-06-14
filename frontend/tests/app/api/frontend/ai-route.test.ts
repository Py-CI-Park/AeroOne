import type { NextRequest } from 'next/server';
import { vi } from 'vitest';

const { getServerApiBaseMock } = vi.hoisted(() => ({
  getServerApiBaseMock: vi.fn(() => 'http://backend.test'),
}));

vi.mock('@/lib/api', () => ({
  getServerApiBase: getServerApiBaseMock,
}));

import { GET as GET_STATUS } from '@/app/api/frontend/ai/status/route';
import { POST as POST_CHAT } from '@/app/api/frontend/ai/chat/route';

function createPostRequest(body: unknown) {
  return {
    text: () => Promise.resolve(JSON.stringify(body)),
    headers: { get: () => null },
  } as unknown as NextRequest;
}

function createGetRequest() {
  return {
    headers: { get: () => null },
    nextUrl: { searchParams: new URLSearchParams() },
  } as unknown as NextRequest;
}

afterEach(() => {
  vi.restoreAllMocks();
  getServerApiBaseMock.mockClear();
});

test('status proxy calls backend AI status without exposing Ollama URL', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response('{"status":"ok"}', { status: 200, headers: { 'content-type': 'application/json' } }),
  );

  const response = await GET_STATUS(createGetRequest());

  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:18437/api/v1/ai/status',
    expect.objectContaining({ method: 'GET', cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
});

test('status proxy returns degraded JSON with 200 when backend is unreachable', async () => {
  vi.spyOn(global, 'fetch').mockRejectedValue(new Error('connect refused'));
  vi.spyOn(console, 'error').mockImplementation(() => {});

  const response = await GET_STATUS(createGetRequest());

  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toMatchObject({
    status: 'unavailable',
    detail: 'AI backend unavailable',
  });
});
test('status proxy falls back to configured backend when local backend is unreachable', async () => {
  const fetchMock = vi
    .spyOn(global, 'fetch')
    .mockRejectedValueOnce(new Error('local backend unavailable'))
    .mockResolvedValueOnce(
      new Response('{"status":"ok"}', { status: 200, headers: { 'content-type': 'application/json' } }),
    );
  vi.spyOn(console, 'error').mockImplementation(() => {});

  const response = await GET_STATUS(createGetRequest());

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    'http://127.0.0.1:18437/api/v1/ai/status',
    expect.objectContaining({ method: 'GET', cache: 'no-store' }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'http://backend.test/api/v1/ai/status',
    expect.objectContaining({ method: 'GET', cache: 'no-store' }),
  );
  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toMatchObject({ status: 'ok' });
});


test('chat proxy forwards POST body to backend AI chat', async () => {
  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response('{"message":{"role":"assistant","content":"ok"}}', {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
  );

  const response = await POST_CHAT(createPostRequest({ messages: [{ role: 'user', content: 'hi' }] }));

  expect(fetchMock).toHaveBeenCalledWith(
    'http://127.0.0.1:18437/api/v1/ai/chat',
    expect.objectContaining({
      method: 'POST',
      cache: 'no-store',
      body: '{"messages":[{"role":"user","content":"hi"}]}',
    }),
  );
  expect(response.status).toBe(200);
});
test('chat proxy falls back to configured backend with the same POST body', async () => {
  const fetchMock = vi
    .spyOn(global, 'fetch')
    .mockRejectedValueOnce(new Error('local backend unavailable'))
    .mockResolvedValueOnce(
      new Response('{"message":{"role":"assistant","content":"ok"}}', {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
  vi.spyOn(console, 'error').mockImplementation(() => {});

  const response = await POST_CHAT(createPostRequest({ messages: [{ role: 'user', content: 'hi' }] }));

  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    'http://backend.test/api/v1/ai/chat',
    expect.objectContaining({
      method: 'POST',
      cache: 'no-store',
      body: '{"messages":[{"role":"user","content":"hi"}]}',
    }),
  );
  expect(response.status).toBe(200);
});
