import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterFilterBar } from '@/components/newsletter/newsletter-filter-bar';


it('renders search and filter controls for newsletters', () => {
  render(
    <NewsletterFilterBar
      current={{ q: 'aero', category: 'briefing', tag: 'aerospace', source_type: 'html' }}
      categories={[{ slug: 'briefing', name: '브리핑' }]}
      tags={[{ slug: 'aerospace', name: '항공우주' }]}
    />,
  );

  expect(screen.getByLabelText('검색어')).toHaveValue('aero');
  expect(screen.getByLabelText('카테고리')).toHaveValue('briefing');
  expect(screen.getByLabelText('유형')).toHaveValue('html');
  expect(screen.getByLabelText('태그')).toHaveValue('aerospace');
  expect(screen.getByRole('button', { name: '검색 / 필터 적용' })).toBeInTheDocument();
});
