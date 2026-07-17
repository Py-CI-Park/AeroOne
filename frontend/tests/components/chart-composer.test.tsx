import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ChartComposer, ChartFollowUp, fileFromPastedData, looksLikeTabularData } from '@/components/office-tools/chart-composer';
import type { ChartInspectResponse } from '@/lib/types';

const PROFILE: ChartInspectResponse = {
  row_count: 4,
  column_count: 2,
  columns: [
    { name: '지역', dtype: 'object', non_null: 4, null: 0, unique: 3, numeric: false, datetime: false },
    { name: '매출', dtype: 'int64', non_null: 4, null: 0, unique: 4, numeric: true, datetime: false },
  ],
  sample: [{ 지역: '서울', 매출: 120 }],
};

afterEach(() => {
  vi.clearAllMocks();
});

test('looksLikeTabularData recognizes multi-line tab/comma delimited text and rejects prose', () => {
  expect(looksLikeTabularData('region,sales\n서울,120\n부산,80')).toBe(true);
  expect(looksLikeTabularData('region\tsales\n서울\t120')).toBe(true);
  expect(looksLikeTabularData('지역별 매출을 비교해줘')).toBe(false);
  expect(looksLikeTabularData('한 줄만,콤마있음')).toBe(false);
});

test('fileFromPastedData builds a csv File from raw text', () => {
  const file = fileFromPastedData('a,b\n1,2\n');
  expect(file.name).toBe('pasted-data.csv');
  expect(file.type).toBe('text/csv');
});

function renderComposer(overrides: Partial<React.ComponentProps<typeof ChartComposer>> = {}) {
  const props: React.ComponentProps<typeof ChartComposer> = {
    file: null,
    onFileChange: vi.fn(),
    promptText: '',
    onPromptChange: vi.fn(),
    profile: null,
    inspectBusy: false,
    busy: false,
    onSubmit: vi.fn(),
    submitDisabled: true,
    ...overrides,
  };
  const view = render(<ChartComposer {...props} />);
  return { ...view, props };
}

test('typing a purpose sentence does not suggest data mode', () => {
  renderComposer({ promptText: '지역별 매출을 크기순으로 비교' });
  expect(screen.queryByText('표 형식 데이터로 보입니다.')).not.toBeInTheDocument();
});

test('typing tabular-looking text suggests using it as data, and confirming attaches a file', async () => {
  const onFileChange = vi.fn();
  const onPromptChange = vi.fn();
  const user = userEvent.setup();
  renderComposer({ promptText: 'region,sales\n서울,120\n부산,80', onFileChange, onPromptChange });

  expect(screen.getByText('표 형식 데이터로 보입니다.')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '데이터로 사용' }));

  expect(onFileChange).toHaveBeenCalledTimes(1);
  const [file] = onFileChange.mock.calls[0];
  expect(file).toBeInstanceOf(File);
  expect(onPromptChange).toHaveBeenCalledWith('');
});

test('does not suggest data mode once a file is already attached', () => {
  const file = new File(['a,b\n1,2\n'], 'data.csv', { type: 'text/csv' });
  renderComposer({ file, promptText: 'region,sales\n서울,120\n부산,80' });
  expect(screen.queryByText('표 형식 데이터로 보입니다.')).not.toBeInTheDocument();
});

test('attaching a file via the clip button notifies the parent', async () => {
  const onFileChange = vi.fn();
  const user = userEvent.setup();
  renderComposer({ onFileChange });

  const file = new File(['region,revenue\n서울,120\n'], 'sales.csv', { type: 'text/csv' });
  await user.upload(screen.getByLabelText('데이터 파일'), file);

  expect(onFileChange).toHaveBeenCalledWith(file);
  expect(await screen.findByText('첨부됨: sales.csv')).toBeInTheDocument();
});

test('renders a column chip per profiled column with its type badge', () => {
  renderComposer({ profile: PROFILE });
  const chips = screen.getByTestId('chart-column-chips');
  expect(chips).toHaveTextContent('지역');
  expect(chips).toHaveTextContent('범주');
  expect(chips).toHaveTextContent('매출');
  expect(chips).toHaveTextContent('숫자');
});

test('shows an inspecting indicator while profiling is busy', () => {
  renderComposer({ inspectBusy: true });
  expect(screen.getByText('열 확인 중…')).toBeInTheDocument();
});

test('the single submit button is disabled without data and enabled once data exists', () => {
  const { rerender } = render(
    <ChartComposer
      file={null}
      onFileChange={vi.fn()}
      promptText=""
      onPromptChange={vi.fn()}
      profile={null}
      inspectBusy={false}
      busy={false}
      onSubmit={vi.fn()}
      submitDisabled
    />,
  );
  expect(screen.getByRole('button', { name: '차트 생성' })).toBeDisabled();

  rerender(
    <ChartComposer
      file={new File(['a'], 'a.csv')}
      onFileChange={vi.fn()}
      promptText=""
      onPromptChange={vi.fn()}
      profile={null}
      inspectBusy={false}
      busy={false}
      onSubmit={vi.fn()}
      submitDisabled={false}
    />,
  );
  expect(screen.getByRole('button', { name: '차트 생성' })).toBeEnabled();
});

test('clicking submit invokes onSubmit', async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  renderComposer({ submitDisabled: false, onSubmit });

  await user.click(screen.getByRole('button', { name: '차트 생성' }));
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

test('dropping a file over the composer attaches it', async () => {
  const onFileChange = vi.fn();
  renderComposer({ onFileChange });

  const file = new File(['a,b\n1,2\n'], 'dropped.csv', { type: 'text/csv' });
  const dropZone = screen.getByTestId('chart-composer');
  const dataTransfer = { files: [file] } as unknown as DataTransfer;

  const dropEvent = new Event('drop', { bubbles: true, cancelable: true }) as unknown as Event & { dataTransfer: DataTransfer };
  Object.defineProperty(dropEvent, 'dataTransfer', { value: dataTransfer });
  await act(async () => {
    dropZone.dispatchEvent(dropEvent);
  });

  expect(onFileChange).toHaveBeenCalledWith(file);
});

test('ChartFollowUp sends the typed command and clears the input', async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(<ChartFollowUp onSubmit={onSubmit} busy={false} />);

  const input = screen.getByPlaceholderText('예: 상위 5개만, 가로 막대로');
  await user.type(input, '상위 3개만{Enter}');

  expect(onSubmit).toHaveBeenCalledWith('상위 3개만');
  expect(input).toHaveValue('');
});

test('ChartFollowUp example chips send immediately without typing', async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(<ChartFollowUp onSubmit={onSubmit} busy={false} />);

  await user.click(screen.getByRole('button', { name: '가로 막대로' }));
  expect(onSubmit).toHaveBeenCalledWith('가로 막대로');
});

test('ChartFollowUp disables send while busy', () => {
  render(<ChartFollowUp onSubmit={vi.fn()} busy />);
  expect(screen.getByRole('button', { name: '처리 중…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '상위 5개만' })).toBeDisabled();
});

test('ChartFollowUp in disabled mode blocks input, chips, and shows the reason hint', async () => {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(
    <ChartFollowUp
      onSubmit={onSubmit}
      busy={false}
      disabled
      disabledHint="다시 연 결과입니다 — 원본 데이터를 다시 첨부하면 새로 생성할 수 있습니다."
    />,
  );

  expect(screen.getByPlaceholderText('예: 상위 5개만, 가로 막대로')).toBeDisabled();
  expect(screen.getByRole('button', { name: '전송' })).toBeDisabled();
  expect(screen.getByRole('note')).toHaveTextContent('원본 데이터를 다시 첨부하면');

  await user.click(screen.getByRole('button', { name: '상위 5개만' }));
  expect(onSubmit).not.toHaveBeenCalled();
});
