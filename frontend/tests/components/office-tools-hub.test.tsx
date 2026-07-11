import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { OfficeToolsHub } from '@/components/office-tools/office-tools-hub';

// 각 폼은 dynamic import(mermaid/echarts)·업로드를 품으므로 허브 탭 테스트에서는 대체한다.
vi.mock('@/components/office-tools/diagram-form', () => ({
  DiagramForm: () => <div data-testid="diagram-form-stub">diagram</div>,
}));
vi.mock('@/components/office-tools/chart-form', () => ({
  ChartForm: () => <div data-testid="chart-form-stub">chart</div>,
}));
vi.mock('@/components/office-tools/report-form', () => ({
  ReportForm: () => <div data-testid="report-form-stub">report</div>,
}));

test('hub renders three tabs and shows the diagram tool by default', () => {
  render(<OfficeToolsHub />);
  expect(screen.getByRole('tab', { name: '다이어그램' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: '차트' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: '보고서' })).toBeInTheDocument();
  expect(screen.getByTestId('diagram-form-stub')).toBeInTheDocument();
});

test('hub honors the initial tab prop', () => {
  render(<OfficeToolsHub initialTab="chart" />);
  expect(screen.getByTestId('chart-form-stub')).toBeInTheDocument();
  expect(screen.queryByTestId('diagram-form-stub')).not.toBeInTheDocument();
});

test('clicking a tab switches the visible tool', async () => {
  const user = userEvent.setup();
  render(<OfficeToolsHub />);
  await user.click(screen.getByRole('tab', { name: '보고서' }));
  expect(screen.getByTestId('report-form-stub')).toBeInTheDocument();
  expect(screen.queryByTestId('diagram-form-stub')).not.toBeInTheDocument();
});
