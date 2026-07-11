import { generateChart, generateDiagram, generateReport, inspectChartData } from '@/lib/api';
import type { DiagramGenerateRequest } from '@/lib/types';

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test('generateDiagram POSTs to the office-tools proxy with csrf + json body', async () => {
  const payload = { job_id: 'x', status: 'completed', mermaid: 'flowchart TD' };
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => payload,
  });

  const request: DiagramGenerateRequest = {
    description: 'A -> B',
    diagram_type: 'flowchart',
    title: '',
    ai_assist: true,
  };
  const result = await generateDiagram(request, 'token-123');

  expect(result).toEqual(payload);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/diagrams/generate');
  expect(init.method).toBe('POST');
  expect(init.credentials).toBe('include');
  expect(init.headers['X-CSRF-Token']).toBe('token-123');
  expect(init.headers['Content-Type']).toBe('application/json');
  expect(JSON.parse(init.body)).toEqual(request);
});

test('generateDiagram throws on non-ok response', async () => {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 422,
    text: async () => '금지된 지시어',
  });

  await expect(
    generateDiagram({ description: 'x', diagram_type: 'flowchart', ai_assist: true }, 'token'),
  ).rejects.toThrow('금지된 지시어');
});

test('generateReport POSTs multipart FormData to the office-tools proxy with csrf', async () => {
  const payload = { job_id: 'x', status: 'completed', title: '보고', html: '<!doctype html>' };
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => payload,
  });

  const file = new File(['# hi'], 'report.md', { type: 'text/markdown' });
  const result = await generateReport({ markdownFile: file, aiMode: 'polish', title: '보고' }, 'token-abc');

  expect(result).toEqual(payload);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/reports/generate');
  expect(init.method).toBe('POST');
  expect(init.credentials).toBe('include');
  expect(init.headers['X-CSRF-Token']).toBe('token-abc');
  // FormData 업로드는 Content-Type 을 브라우저가 boundary 와 함께 설정하도록 생략한다.
  expect(init.headers['Content-Type']).toBeUndefined();
  expect(init.body).toBeInstanceOf(FormData);
  const form = init.body as FormData;
  expect(form.get('markdown_file')).toBe(file);
  expect(form.get('ai_mode')).toBe('polish');
  expect(form.get('title')).toBe('보고');
});

test('inspectChartData POSTs multipart to the charts inspect proxy', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ row_count: 4 }) });

  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  const result = await inspectChartData(file, 'token-csv');

  expect(result).toEqual({ row_count: 4 });
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/charts/inspect');
  expect(init.method).toBe('POST');
  expect(init.headers['X-CSRF-Token']).toBe('token-csv');
  expect(init.headers['Content-Type']).toBeUndefined();
  expect((init.body as FormData).get('data_file')).toBe(file);
});

test('generateChart POSTs multipart with prompt/ai_assist/chart_type', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ job_id: 'x' }) });

  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  await generateChart({ dataFile: file, prompt: '비교', aiAssist: false, chartType: 'bar' }, 'token-gen');

  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/charts/generate');
  expect(init.headers['X-CSRF-Token']).toBe('token-gen');
  const form = init.body as FormData;
  expect(form.get('data_file')).toBe(file);
  expect(form.get('prompt')).toBe('비교');
  expect(form.get('ai_assist')).toBe('false');
  expect(form.get('chart_type')).toBe('bar');
});

test('generateChart omits chart_type when auto (empty string)', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ job_id: 'x' }) });

  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  await generateChart({ dataFile: file, chartType: '' }, 'token');

  const form = fetchMock.mock.calls[0][1].body as FormData;
  expect(form.has('chart_type')).toBe(false);
  // 기본 aiAssist 는 true 로 직렬화된다.
  expect(form.get('ai_assist')).toBe('true');
});
