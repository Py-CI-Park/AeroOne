import { formatRelativeTime } from '@/lib/relative-time';

const now = new Date('2026-07-05T12:00:00Z');

test('formatRelativeTime returns Korean relative buckets', () => {
  expect(formatRelativeTime('2026-07-05T11:59:55Z', now)).toBe('방금');
  expect(formatRelativeTime('2026-07-05T11:59:49Z', now)).toBe('1분 전');
  expect(formatRelativeTime('2026-07-05T11:01:00Z', now)).toBe('59분 전');
  expect(formatRelativeTime('2026-07-05T11:00:00Z', now)).toBe('1시간 전');
  expect(formatRelativeTime('2026-07-04T12:01:00Z', now)).toBe('23시간 전');
  expect(formatRelativeTime('2026-07-04T12:00:00Z', now)).toBe('1일 전');
});

test('formatRelativeTime returns empty string for empty or invalid input', () => {
  expect(formatRelativeTime(null, now)).toBe('');
  expect(formatRelativeTime(undefined, now)).toBe('');
  expect(formatRelativeTime('', now)).toBe('');
  expect(formatRelativeTime('not-a-date', now)).toBe('');
  expect(formatRelativeTime('2026-07-05T12:00:00Z', Number.NaN)).toBe('');
});
