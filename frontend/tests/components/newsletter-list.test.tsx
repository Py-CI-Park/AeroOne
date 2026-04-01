import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterList } from '@/components/newsletter/newsletter-list';


it('shows sync guidance when the list is empty', () => {
  render(<NewsletterList items={[]} />);

  expect(screen.getByText('표시할 뉴스레터가 없습니다.')).toBeInTheDocument();
  expect(screen.getByText(/Import \/ Sync/)).toBeInTheDocument();
});
