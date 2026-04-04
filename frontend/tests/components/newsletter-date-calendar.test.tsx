import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';

it('shows the calendar grid by default without a dedicated open toggle', () => {
  render(
    <NewsletterDateCalendar
      selectedSlug="newsletter-20260326"
      entries={[
        { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
        { date: '2026-03-25', slug: 'newsletter-20260325', title: '2026-03-25 뉴스레터', source_type: 'html' },
      ]}
    />,
  );

  expect(screen.getByRole('link', { name: /26/ })).toHaveAttribute(
    'href',
    '/newsletters?slug=newsletter-20260326',
  );
  expect(screen.getByRole('link', { name: /25/ })).toBeInTheDocument();
  expect(screen.getAllByRole('button')).toHaveLength(2);
  expect(screen.queryByRole('button', { name: /달력 열기|달력 닫기/ })).not.toBeInTheDocument();
});
