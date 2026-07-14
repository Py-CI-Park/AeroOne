import {
  fetchOfficeJob,
  fetchOfficeJobs,
  fetchOfficeSamples,
  generateChart,
  generateDiagram,
  generateReport,
  getOfficeArtifactProxyPath,
  inspectChartData,
} from '@/lib/api';
import type { ChartManualSpecInput, DiagramGenerateRequest } from '@/lib/types';

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
  const controller = new AbortController();
  const result = await generateDiagram(request, 'token-123', controller.signal);

  expect(result).toEqual(payload);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/diagrams/generate');
  expect(init.method).toBe('POST');
  expect(init.credentials).toBe('include');
  expect(init.headers['X-CSRF-Token']).toBe('token-123');
  expect(init.headers['Content-Type']).toBe('application/json');
  expect(JSON.parse(init.body)).toEqual(request);
  expect(init.signal).toBe(controller.signal);
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
  const controller = new AbortController();
  const result = await generateReport({ markdownFile: file, aiMode: 'polish', title: '보고' }, 'token-abc', controller.signal);

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
  expect(init.signal).toBe(controller.signal);
});

test('inspectChartData POSTs multipart to the charts inspect proxy', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ row_count: 4 }) });

  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  const controller = new AbortController();
  const result = await inspectChartData(file, 'token-csv', controller.signal);

  expect(result).toEqual({ row_count: 4 });
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/charts/inspect');
  expect(init.method).toBe('POST');
  expect(init.headers['X-CSRF-Token']).toBe('token-csv');
  expect(init.headers['Content-Type']).toBeUndefined();
  expect((init.body as FormData).get('data_file')).toBe(file);
  expect(init.signal).toBe(controller.signal);
});

test('generateChart POSTs multipart with prompt/ai_assist/chart_type', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ job_id: 'x' }) });

  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  const controller = new AbortController();
  await generateChart(
    { dataFile: file, prompt: '비교', aiAssist: false, chartType: 'bar' },
    'token-gen',
    controller.signal,
  );

  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/charts/generate');
  expect(init.headers['X-CSRF-Token']).toBe('token-gen');
  const form = init.body as FormData;
  expect(form.get('data_file')).toBe(file);
  expect(form.get('prompt')).toBe('비교');
  expect(form.get('ai_assist')).toBe('false');
  expect(form.get('chart_type')).toBe('bar');
  expect(init.signal).toBe(controller.signal);
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
test('generateChart serializes a typed manual spec once', async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ job_id: 'x' }) });
  const file = new File(['region,revenue\nSeoul,120\n'], 'data.csv', { type: 'text/csv' });
  const manualSpec: ChartManualSpecInput = {
    x: 'region',
    y: ['revenue'],
    group: null,
    stacked: true,
    aggregation: 'sum',
    sort: 'value_desc',
    limit: 10,
    orientation: 'horizontal',
  };

  await generateChart({ dataFile: file, manualSpec }, 'token');

  const form = fetchMock.mock.calls[0][1].body as FormData;
  expect(form.get('manual_spec_json')).toBe(JSON.stringify(manualSpec));
});

test('generateChart rejects conflicting manual spec inputs before fetching', async () => {
  const file = new File(['region,revenue\nSeoul,120\n'], 'data.csv', { type: 'text/csv' });

  await expect(
    generateChart({
      dataFile: file,
      manualSpec: { x: 'region', y: ['revenue'] },
      manualSpecJson: '{"x":"region","y":["revenue"]}',
    }, 'token'),
  ).rejects.toThrow('Provide either manualSpec or manualSpecJson, not both');
  expect(fetchMock).not.toHaveBeenCalled();
});

test('fetchOfficeSamples GETs the samples list from the office-tools proxy', async () => {
  const samples = [
    { key: 'diagram-flow', tool: 'diagram', filename: 'f.txt', media_type: 'text/plain', title: '흐름', description: '', content: 'A -> B', hints: {} },
  ];
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => samples });

  const result = await fetchOfficeSamples();

  expect(result).toEqual(samples);
  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/samples');
  expect(init.method).toBe('GET');
});
test('fetchOfficeJobs GETs the owner-scoped job list from the office-tools proxy', async () => {
  const payload = {
    jobs: [{
      job_id: 'a'.repeat(32),
      service: 'chart',
      status: 'completed',
      created_at: '2026-07-14T00:00:00Z',
      updated_at: '2026-07-14T00:00:01Z',
      warnings: [],
      artifacts: [],
      title: 'Revenue',
      llm_used: true,
    }],
    usage: { job_count: 1, total_bytes: 20, max_jobs_per_owner: 10, max_bytes_per_owner: 1000 },
  };
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => payload });

  await expect(fetchOfficeJobs()).resolves.toEqual(payload);

  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/frontend/office-tools/jobs');
  expect(init.method).toBe('GET');
});

test('fetchOfficeJob validates and GETs an encoded owner-scoped job detail path', async () => {
  const jobId = 'a'.repeat(32);
  const payload = {
    job_id: jobId,
    service: 'chart',
    owner_id: 7,
    status: 'completed',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:00:01Z',
    request_summary: {},
    warnings: [],
    artifacts: [],
    error: null,
  };
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => payload });

  await expect(fetchOfficeJob(jobId)).resolves.toEqual(payload);

  const [path, init] = fetchMock.mock.calls[0];
  expect(path).toBe(`/api/frontend/office-tools/jobs/${encodeURIComponent(jobId)}`);
  expect(init.method).toBe('GET');
});

test('fetchOfficeJob rejects malformed job IDs before fetching', async () => {
  await expect(fetchOfficeJob('../other-owner-job')).rejects.toThrow('Invalid office job ID');
  expect(fetchMock).not.toHaveBeenCalled();
});

test('getOfficeArtifactProxyPath maps only office-tools backend artifact and bundle paths', () => {
  expect(getOfficeArtifactProxyPath('/api/v1/office-tools/jobs/abc/artifacts/report.html')).toBe(
    '/api/frontend/office-tools/jobs/abc/artifacts/report.html',
  );
  expect(getOfficeArtifactProxyPath('/api/v1/office-tools/jobs/abc/bundle')).toBe(
    '/api/frontend/office-tools/jobs/abc/bundle',
  );
  expect(() => getOfficeArtifactProxyPath('https://example.com/api/v1/office-tools/jobs/abc/bundle')).toThrow(
    'Only office-tools artifact paths can be proxied',
  );
  expect(() => getOfficeArtifactProxyPath('/api/v1/office-tools-private/jobs/abc/bundle')).toThrow(
    'Only office-tools artifact paths can be proxied',
  );
  expect(() => getOfficeArtifactProxyPath('/api/v1/office-tools/jobs/abc/artifacts/../job.json')).toThrow(
    'Only office-tools artifact paths can be proxied',
  );
  expect(() => getOfficeArtifactProxyPath('/api/v1/office-tools/jobs/abc/bundle?download=1')).toThrow(
    'Only office-tools artifact paths can be proxied',
  );
});
