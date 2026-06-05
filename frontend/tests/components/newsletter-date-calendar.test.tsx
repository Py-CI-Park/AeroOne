import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';

const entries = [
  { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
  { date: '2026-03-25', slug: 'newsletter-20260325', title: '2026-03-25 뉴스레터', source_type: 'html' },
] as const;

it('starts collapsed and expands the light calendar on click', () => {
  const { container } = render(
    <NewsletterDateCalendar
      selectedSlug="newsletter-20260326"
      entries={[...entries]}
    />,
  );

  const panel = container.querySelector('section');
  const toggle = screen.getByRole('button', { name: '달력 펼치기' });

  // Collapsed state: slim bar with p-2, no month label, no grid
  expect(panel).toHaveClass('bg-surface-raised');
  expect(panel).toHaveClass('h-full');
  expect(panel).toHaveClass('p-2');
  expect(panel?.className).not.toContain('bg-slate-900');
  expect(screen.queryByText('2026년 3월')).toBeNull();
  ['일', '월', '화', '수', '목', '금', '토'].forEach((weekday) => {
    expect(screen.queryByText(weekday)).toBeNull();
  });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('button', { name: '이전 달' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '다음 달' })).not.toBeInTheDocument();
  expect(screen.queryByTestId('newsletter-calendar-grid')).toBeNull();

  fireEvent.click(toggle);

  // Expanded state: month label, grid, nav buttons all present
  const expandedPanel = container.querySelector('section');
  expect(expandedPanel).toHaveClass('p-4');
  expect(screen.getByRole('button', { name: '달력 접기' })).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('button', { name: '이전 달' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '다음 달' })).toBeInTheDocument();
  expect(screen.getByText('2026년 3월')).toBeInTheDocument();
  expect(screen.getByTestId('newsletter-calendar-grid')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326&theme=light',
  );
  expect(screen.getByRole('link', { name: /25/ })).toBeInTheDocument();
});

it('can render the calendar panel with dark theme classes', () => {
  const { container } = render(
    <NewsletterDateCalendar
      theme="dark"
      selectedSlug="newsletter-20260326"
      entries={[entries[0]]}
    />,
  );

  const panel = container.querySelector('section');

  // Collapsed by default
  expect(panel).toHaveClass('bg-surface-raised');
  expect(panel).toHaveClass('p-2');
  expect(screen.getByRole('button', { name: '달력 펼치기' })).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByTestId('newsletter-calendar-grid')).toBeNull();
  expect(screen.queryByText('2026년 3월')).toBeNull();

  // Expand and check dark-theme link
  fireEvent.click(screen.getByRole('button', { name: '달력 펼치기' }));

  expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326&theme=dark',
  );
});
