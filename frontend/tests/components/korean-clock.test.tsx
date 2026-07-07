import React from 'react';
import { act, render, screen } from '@testing-library/react';

import { formatKoreanDateTime, KoreanClock } from '@/components/layout/korean-clock';

afterEach(() => {
  vi.useRealTimers();
});

test('formats dates in Korean time', () => {
  expect(formatKoreanDateTime(new Date('2026-07-06T03:04:05Z'))).toMatch(/2026\. 07\. 06\./);
  expect(formatKoreanDateTime(new Date('2026-07-06T03:04:05Z'))).toContain('12:04:05');
});

test('renders a live Korean clock from the client clock', async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-07-06T03:04:05Z'));

  render(<KoreanClock />);
  await act(async () => {});
  expect(screen.getByLabelText('한국 시간')).toHaveTextContent('12:04:05');
  expect(screen.getByLabelText('한국 시간')).toHaveTextContent('KST');

  act(() => {
    vi.advanceTimersByTime(1000);
  });

  expect(screen.getByLabelText('한국 시간')).toHaveTextContent('12:04:06');
});
