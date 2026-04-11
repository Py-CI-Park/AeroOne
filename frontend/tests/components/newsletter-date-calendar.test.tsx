import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';

it('shows the calendar grid by default and can collapse or expand the top calendar panel', () => {
  render(
    <NewsletterDateCalendar
      selectedSlug="newsletter-20260326"
      entries={[
        { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
        { date: '2026-03-25', slug: 'newsletter-20260325', title: '2026-03-25 뉴스레터', source_type: 'html' },
      ]}
    />,
  );

  const panel = screen.getByTestId('newsletter-date-calendar-panel');
  const toggle = screen.getByRole('button', { name: '달력 접기' });
  const calendarGrid = screen.getByTestId('newsletter-calendar-grid');

  expect(panel).toHaveClass('bg-white');
  expect(panel.className).not.toContain('bg-slate-900');
  expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326',
  );
  expect(screen.getByRole('link', { name: /25/ })).toBeInTheDocument();
  expect(screen.getByText('2026년 3월')).toBeInTheDocument();
  ['일', '월', '화', '수', '목', '금', '토'].forEach((weekday) => {
    expect(screen.getByText(weekday)).toBeInTheDocument();
  });
  expect(calendarGrid).toBeVisible();

  fireEvent.click(toggle);

  expect(screen.getByRole('button', { name: '달력 펼치기' })).toHaveAttribute('aria-expanded', 'false');
  expect(calendarGrid).not.toBeVisible();

  fireEvent.click(screen.getByRole('button', { name: '달력 펼치기' }));

  expect(screen.getByRole('button', { name: '달력 접기' })).toHaveAttribute('aria-expanded', 'true');
  expect(calendarGrid).toBeVisible();
});
