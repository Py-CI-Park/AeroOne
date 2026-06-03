import React from 'react';
import { render, screen } from '@testing-library/react';

import * as api from '@/lib/api';
import { ReadEventsList } from '@/components/admin/read-events-list';

afterEach(() => {
  vi.restoreAllMocks();
});

test('renders newsletter summaries and per-IP event rows', async () => {
  vi.spyOn(api, 'fetchAdminReadEvents').mockResolvedValue({
    summaries: [{ newsletter_id: 1, title: '테스트 뉴스레터', slug: 'x', total_reads: 5, unique_ips: 2 }],
    events: [
      { newsletter_id: 1, client_ip: '192.168.1.9', read_count: 5, first_seen_at: null, last_seen_at: '2026-06-03T00:00:00Z' },
    ],
    loopback_only: false,
  });

  render(<ReadEventsList />);

  expect(await screen.findByText('테스트 뉴스레터')).toBeInTheDocument();
  expect(screen.getByText('192.168.1.9')).toBeInTheDocument();
  expect(screen.queryByTestId('loopback-banner')).not.toBeInTheDocument();
});

test('shows the loopback banner when only loopback addresses are recorded', async () => {
  vi.spyOn(api, 'fetchAdminReadEvents').mockResolvedValue({
    summaries: [{ newsletter_id: 1, title: 'L', slug: 'x', total_reads: 1, unique_ips: 1 }],
    events: [{ newsletter_id: 1, client_ip: '127.0.0.1', read_count: 1, first_seen_at: null, last_seen_at: null }],
    loopback_only: true,
  });

  render(<ReadEventsList />);

  expect(await screen.findByTestId('loopback-banner')).toBeInTheDocument();
});

test('shows the empty state when there are no events', async () => {
  vi.spyOn(api, 'fetchAdminReadEvents').mockResolvedValue({ summaries: [], events: [], loopback_only: false });

  render(<ReadEventsList />);

  expect(await screen.findByTestId('read-events-empty')).toBeInTheDocument();
});
