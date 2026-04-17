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

test('renders selected issue date and previous next navigation', () => {
  render(
    <NewsletterPreviewPanel
      title="Aerospace Daily News"
      selectedAsset="html"
      displayDate="2026-03-26"
      dateNavigation={{
        previous: { label: '이전 날짜', href: '/newsletters?slug=old&theme=dark' },
        next: { label: '다음 날짜', href: '/newsletters?slug=new&theme=dark' },
      }}
      theme="dark"
    >
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByText('2026-03-26')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '이전 날짜' })).toHaveAttribute('href', '/newsletters?slug=old&theme=dark');
  expect(screen.getByRole('link', { name: '다음 날짜' })).toHaveAttribute('href', '/newsletters?slug=new&theme=dark');
});

test('renders disabled previous next labels when adjacent issues are missing', () => {
  render(
    <NewsletterPreviewPanel title="Only Issue" selectedAsset="html" displayDate="2026-03-26">
      <div data-testid="preview-body">body</div>
    </NewsletterPreviewPanel>,
  );

  expect(screen.getByText('이전 날짜')).toHaveAttribute('aria-disabled', 'true');
  expect(screen.getByText('다음 날짜')).toHaveAttribute('aria-disabled', 'true');
});
