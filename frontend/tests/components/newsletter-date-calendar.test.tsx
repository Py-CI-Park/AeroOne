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
  const calendarGrid = screen.getByTestId('newsletter-calendar-grid');

  expect(panel).toHaveClass('bg-white');
  expect(panel).toHaveClass('h-full');
  expect(panel?.className).not.toContain('bg-slate-900');
  expect(screen.getByText('2026년 3월')).toBeInTheDocument();
  ['일', '월', '화', '수', '목', '금', '토'].forEach((weekday) => {
    expect(screen.getByText(weekday)).toBeInTheDocument();
  });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('button', { name: '이전 달' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '다음 달' })).not.toBeInTheDocument();
  expect(calendarGrid).not.toBeVisible();

  fireEvent.click(toggle);

  expect(screen.getByRole('button', { name: '달력 접기' })).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('button', { name: '이전 달' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '다음 달' })).toBeInTheDocument();
  expect(calendarGrid).toBeVisible();
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

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(screen.getByRole('button', { name: '달력 펼치기' })).toHaveAttribute('aria-expanded', 'false');
  expect(screen.getByTestId('newsletter-calendar-grid')).not.toBeVisible();
  expect(screen.getByRole('link', { name: /26/, hidden: true })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326&theme=dark',
  );
});
