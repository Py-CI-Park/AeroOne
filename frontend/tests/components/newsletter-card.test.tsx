import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterCard } from '@/components/newsletter/newsletter-card';

it('renders newsletter metadata and tags', () => {
  render(
    <NewsletterCard
      item={{
        id: 1,
        title: 'AeroOne Daily',
        slug: 'aeroone-daily',
        description: 'briefing',
        source_type: 'html',
        category: { id: 1, name: 'Aerospace', slug: 'aerospace' },
        tags: [{ id: 1, name: 'Daily', slug: 'daily' }],
        available_assets: [],
      }}
    />
  );
  expect(screen.getByText('AeroOne Daily')).toBeInTheDocument();
  expect(screen.getByText('#Daily')).toBeInTheDocument();
});
