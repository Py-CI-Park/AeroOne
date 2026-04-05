import React from 'react';
import { render, screen } from '@testing-library/react';

import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';

test('renders a dominant preview panel with title and asset badge', () => {
  render(
    <NewsletterPreviewPanel title="Preview Title" selectedAsset="html">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByRole('heading', { name: 'Preview Title' })).toBeInTheDocument();
  expect(screen.getByText('HTML')).toBeInTheDocument();
  expect(screen.getByTestId('preview-body')).toBeInTheDocument();
});
