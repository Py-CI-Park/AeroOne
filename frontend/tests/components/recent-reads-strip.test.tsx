import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import { RecentReadsStrip } from '@/components/dashboard/recent-reads-strip';

const { fetchMyRecentReadsMock } = vi.hoisted(() => ({
  fetchMyRecentReadsMock: vi.fn(),
}));

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>();
  return {
    ...actual,
    fetchMyRecentReads: fetchMyRecentReadsMock,
  };
});

afterEach(() => {
  fetchMyRecentReadsMock.mockReset();
});

test('renders a chip per item, linking to /newsletters/[slug] with a relative time label', async () => {
  fetchMyRecentReadsMock.mockResolvedValue({
    items: [
      { slug: 'first-post', title: '첫 번째 뉴스레터', last_seen_at: new Date(Date.now() - 60_000).toISOString() },
      { slug: 'second-post', title: '두 번째 뉴스레터', last_seen_at: new Date(Date.now() - 3_600_000).toISOString() },
    ],
  });

  render(<RecentReadsStrip />);

  expect(await screen.findByText('최근 본 뉴스레터')).toBeInTheDocument();
  const firstLink = screen.getByRole('link', { name: /첫 번째 뉴스레터/ });
  expect(firstLink).toHaveAttribute('href', '/newsletters/first-post');
  expect(firstLink).toHaveTextContent('분 전');

  const secondLink = screen.getByRole('link', { name: /두 번째 뉴스레터/ });
  expect(secondLink).toHaveAttribute('href', '/newsletters/second-post');
  expect(secondLink).toHaveTextContent('시간 전');
});

test('renders nothing when there are no recent reads', async () => {
  fetchMyRecentReadsMock.mockResolvedValue({ items: [] });

  const { container } = render(<RecentReadsStrip />);

  await waitFor(() => {
    expect(fetchMyRecentReadsMock).toHaveBeenCalledTimes(1);
  });
  expect(container).toBeEmptyDOMElement();
});

test('renders nothing when the fetch fails (does not pollute the dashboard)', async () => {
  fetchMyRecentReadsMock.mockRejectedValue(new Error('network down'));

  const { container } = render(<RecentReadsStrip />);

  await waitFor(() => {
    expect(fetchMyRecentReadsMock).toHaveBeenCalledTimes(1);
  });
  expect(container).toBeEmptyDOMElement();
});
