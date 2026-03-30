import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterDateCalendar } from '@/components/newsletter/newsletter-date-calendar';

it('shows calendar only after opening toggle', () => {
  render(
    <NewsletterDateCalendar
      selectedSlug="newsletter-20260326"
      entries={[
        { date: '2026-03-26', slug: 'newsletter-20260326', title: '2026-03-26 뉴스레터', source_type: 'html' },
        { date: '2026-03-25', slug: 'newsletter-20260325', title: '2026-03-25 뉴스레터', source_type: 'html' },
      ]}
    />,
  );

  expect(screen.queryByRole('link', { name: /26/i })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '달력 열기' }));
  expect(screen.getByRole('link', { name: /26/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /25/i })).toBeInTheDocument();
  expect(screen.getByText('2026년 3월')).toBeInTheDocument();
});
