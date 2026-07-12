import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ReportForm } from '@/components/office-tools/report-form';
import type { ReportGenerateResponse } from '@/lib/types';

const { generateReportMock } = vi.hoisted(() => ({
  generateReportMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  generateReport: generateReportMock,
  fetchOfficeSamples: () => Promise.resolve([]),
}));

vi.mock('@/lib/cookies', () => ({
  getCsrfCookie: () => 'csrf-test-token',
}));

const RESPONSE: ReportGenerateResponse = {
  job_id: 'a'.repeat(32),
  status: 'completed',
  title: '분기 보고',
  ai_mode: 'none',
  llm_used: false,
  html: '<!doctype html><html><body><h1>분기 보고</h1></body></html>',
  warnings: [],
  artifacts: [],
  preview_url: '/api/v1/office-tools/jobs/aaaa/artifacts/aeroone_report.html',
  bundle_url: '/api/v1/office-tools/jobs/aaaa/bundle',
};

afterEach(() => {
  vi.clearAllMocks();
});

test('submitting the form uploads the markdown file and renders the preview iframe', async () => {
  generateReportMock.mockResolvedValue(RESPONSE);
  const user = userEvent.setup();
  render(<ReportForm />);

  const file = new File(['# 분기 보고\n\n본문'], 'report.md', { type: 'text/markdown' });
  fireEvent.change(screen.getByLabelText(/Markdown 파일/), { target: { files: [file] } });
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  await waitFor(() => expect(generateReportMock).toHaveBeenCalledTimes(1));
  const [input, token] = generateReportMock.mock.calls[0];
  expect(input.markdownFile).toBe(file);
  expect(input.aiMode).toBe('none');
  expect(token).toBe('csrf-test-token');

  const result = await screen.findByTestId('report-result');
  expect(result).toBeInTheDocument();
  const iframe = screen.getByTitle('보고서 미리보기') as HTMLIFrameElement;
  expect(iframe.getAttribute('srcdoc')).toContain('분기 보고');
});

test('shows an error message when generation fails', async () => {
  generateReportMock.mockRejectedValue(new Error('생성 실패'));
  const user = userEvent.setup();
  render(<ReportForm />);

  const file = new File(['# x'], 'report.md', { type: 'text/markdown' });
  fireEvent.change(screen.getByLabelText(/Markdown 파일/), { target: { files: [file] } });
  await user.click(screen.getByRole('button', { name: '보고서 생성' }));

  expect(await screen.findByRole('alert')).toHaveTextContent('생성 실패');
  expect(screen.queryByTestId('report-result')).not.toBeInTheDocument();
});
