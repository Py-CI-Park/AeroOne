import React from 'react';
import { render, screen, within } from '@testing-library/react';

import { NewsletterPreviewPanel } from '@/components/newsletter/newsletter-preview-panel';

test('renders a dominant preview panel with stable wrapper identity, title, and asset badge', () => {
  render(
    <NewsletterPreviewPanel title="Preview Title" selectedAsset="html">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  const panel = screen.getByTestId('newsletters-preview-panel');

  expect(panel).toHaveClass('bg-white');
  expect(panel.className).not.toContain('bg-slate-900');
  expect(within(panel).getByText('Preview')).toBeInTheDocument();
  expect(within(panel).getByRole('heading', { name: 'Preview Title' })).toBeInTheDocument();
  expect(within(panel).getByText('HTML')).toBeInTheDocument();
  expect(within(panel).getByTestId('preview-body')).toBeInTheDocument();
});

test('renders the preview panel with dark theme classes', () => {
  render(
    <NewsletterPreviewPanel title="Dark Preview" selectedAsset="pdf" theme="dark">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  const panel = screen.getByTestId('newsletters-preview-panel');

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(within(panel).getByRole('heading', { name: 'Dark Preview' })).toHaveClass('text-slate-100');
});
