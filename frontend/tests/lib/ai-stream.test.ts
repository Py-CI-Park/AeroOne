import { vi } from 'vitest';

import { parseSseBuffer, streamAiChat } from '@/lib/api';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// --- 순수 파서(parseSseBuffer) ---------------------------------------------------------

test('parseSseBuffer parses a complete frame and keeps a trailing partial frame as rest', () => {
  const { frames, rest } = parseSseBuffer('event: delta\ndata: {"content":"a"}\n\nevent: delta\ndata: {"content":"b"');
  expect(frames).toEqual([{ event: 'delta', data: '{"content":"a"}' }]);
  expect(rest).toBe('event: delta\ndata: {"content":"b"');
});

test('parseSseBuffer resumes parsing once the remaining chunk completes the frame', () => {
  const first = parseSseBuffer('event: done\ndata: {"model":"m');
  const second = parseSseBuffer(`${first.rest}"}\n\n`);
  expect(second.frames).toEqual([{ event: 'done', data: '{"model":"m"}' }]);
  expect(second.rest).toBe('');
});

test('parseSseBuffer normalizes CRLF frame separators', () => {
  const { frames } = parseSseBuffer('event: citations\r\ndata: {"citations":[]}\r\n\r\n');
  expect(frames).toEqual([{ event: 'citations', data: '{"citations":[]}' }]);
});

test('parseSseBuffer joins multi-line data fields and ignores dataless frames (keep-alive comments)', () => {
  const { frames } = parseSseBuffer(': keep-alive\n\nevent: delta\ndata: line1\ndata: line2\n\n');
  expect(frames).toEqual([{ event: 'delta', data: 'line1\nline2' }]);
});

test('parseSseBuffer defaults to a "message" event when no event: line is present', () => {
  const { frames } = parseSseBuffer('data: {"content":"x"}\n\n');
  expect(frames).toEqual([{ event: 'message', data: '{"content":"x"}' }]);
});

// --- streamAiChat 통합(fetch + ReadableStream) ------------------------------------------

function sseResponse(chunks: string[], init?: { status?: number; ok?: boolean }) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, {
    status: init?.status ?? 200,
    headers: { 'content-type': 'text/event-stream' },
  });
}

test('streamAiChat posts to the same-origin stream route without any CSRF header (cookie-only public path) and JSON body', async () => {
  const fetchMock = vi.fn().mockResolvedValue(sseResponse(['event: done\ndata: {"model":"m"}\n\n']));
  vi.stubGlobal('fetch', fetchMock);

  await streamAiChat({ messages: [{ role: 'user', content: 'hi' }] }, undefined, {});

  expect(fetchMock).toHaveBeenCalledWith(
    '/api/frontend/ai/chat/stream',
    expect.objectContaining({
      method: 'POST',
      cache: 'no-store',
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      body: '{"messages":[{"role":"user","content":"hi"}]}',
    }),
  );
  const [, requestInit] = fetchMock.mock.calls[0];
  expect(requestInit.headers).not.toHaveProperty('X-CSRF-Token');

});

test('streamAiChat dispatches citations once, delta chunks in order, then done', async () => {
  const chunks = [
    'event: citations\ndata: {"citations":[{"collection":"document","path":"a.html","name":"a","folder":"","navigation_url":"/documents?path=a.html","score":-1}]}\n\n',
    'event: delta\ndata: {"content":"안"}\n\nevent: delta\ndata: {"content":"녕"}\n\n',
    'event: done\ndata: {"model":"gemma4:12b","conversation_id":7,"persisted":true}\n\n',
  ];
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(chunks)));

  const onCitations = vi.fn();
  const onDelta = vi.fn();
  const onDone = vi.fn();
  const onError = vi.fn();

  await streamAiChat({ messages: [{ role: 'user', content: 'hi' }] }, undefined, {
    onCitations,
    onDelta,
    onDone,
    onError,
  });

  expect(onCitations).toHaveBeenCalledTimes(1);
  expect(onCitations).toHaveBeenCalledWith([expect.objectContaining({ path: 'a.html' })]);
  expect(onDelta).toHaveBeenNthCalledWith(1, '안');
  expect(onDelta).toHaveBeenNthCalledWith(2, '녕');
  expect(onDone).toHaveBeenCalledWith({ model: 'gemma4:12b', conversation_id: 7, persisted: true });
  expect(onError).not.toHaveBeenCalled();
});

test('streamAiChat reassembles a delta frame split across two stream reads', async () => {
  const chunks = ['event: delta\ndata: {"con', 'tent":"완성"}\n\n', 'event: done\ndata: {"model":"m"}\n\n'];
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse(chunks)));

  const onDelta = vi.fn();
  await streamAiChat({ messages: [] }, undefined, { onDelta });

  expect(onDelta).toHaveBeenCalledTimes(1);
  expect(onDelta).toHaveBeenCalledWith('완성');
});

test('streamAiChat dispatches the error frame via onError without throwing', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"detail":"모델을 사용할 수 없습니다","status":502}\n\n'])),
  );
  const onError = vi.fn();
  await expect(streamAiChat({ messages: [] }, undefined, { onError })).resolves.toBeUndefined();
  expect(onError).toHaveBeenCalledWith('모델을 사용할 수 없습니다', 502);
});

test('streamAiChat throws a safe error when the response is not ok', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: false, status: 502, body: null, text: async () => 'bad gateway' }),
  );
  await expect(streamAiChat({ messages: [] }, undefined, {})).rejects.toThrow('bad gateway');
});

test('streamAiChat forwards the AbortSignal to fetch so stop cancels the stream', async () => {
  const fetchMock = vi.fn().mockResolvedValue(sseResponse(['event: done\ndata: {"model":"m"}\n\n']));
  vi.stubGlobal('fetch', fetchMock);
  const controller = new AbortController();

  await streamAiChat({ messages: [] }, controller.signal, {});

  expect(fetchMock).toHaveBeenCalledWith('/api/frontend/ai/chat/stream', expect.objectContaining({ signal: controller.signal }));
});
