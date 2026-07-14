import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { SamplePicker } from '@/components/office-tools/sample-picker';

const { fetchOfficeSamplesMock } = vi.hoisted(() => ({ fetchOfficeSamplesMock: vi.fn() }));

vi.mock('@/lib/api', () => ({ fetchOfficeSamples: fetchOfficeSamplesMock }));

const SAMPLES = [
  { key: 'chart-region-bar', tool: 'chart', filename: 'a.csv', media_type: 'text/csv', title: '지역 매출(막대)', description: '지역별', content: 'region,sales\n서울,1\n', hints: { chart_type: 'bar' } },
  { key: 'chart-channel-pie', tool: 'chart', filename: 'b.csv', media_type: 'text/csv', title: '채널 비중(파이)', description: '채널별', content: 'channel,revenue\n온라인,1\n', hints: { chart_type: 'pie' } },
  { key: 'diagram-flow', tool: 'diagram', filename: 'c.txt', media_type: 'text/plain', title: '흐름', description: '', content: 'A -> B', hints: {} },
];

afterEach(() => {
  fetchOfficeSamplesMock.mockReset();
});

test('renders only the given tool samples as chips and passes the picked sample up', async () => {
  fetchOfficeSamplesMock.mockResolvedValue(SAMPLES);
  const onPick = vi.fn();
  render(<SamplePicker tool="chart" onPick={onPick} />);

  await waitFor(() => expect(screen.getByRole('button', { name: '지역 매출(막대)' })).toBeInTheDocument());
  // 다른 도구(diagram)의 칩은 노출되지 않는다.
  expect(screen.queryByRole('button', { name: '흐름' })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: '채널 비중(파이)' }));
  expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ key: 'chart-channel-pie' }));
});

test('renders nothing when the samples fetch fails', async () => {
  fetchOfficeSamplesMock.mockRejectedValue(new Error('down'));
  const { container } = render(<SamplePicker tool="chart" onPick={vi.fn()} />);
  await waitFor(() => expect(fetchOfficeSamplesMock).toHaveBeenCalled());
  expect(container.querySelector('[data-testid="sample-picker"]')).toBeNull();
});
