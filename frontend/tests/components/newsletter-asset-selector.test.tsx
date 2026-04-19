import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import type { AssetType } from '@/lib/types';

test('renders report-style format cards with explicit asset choices and selected-state semantics', () => {
  const onChange = vi.fn();

  render(
    <NewsletterAssetSelector
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="markdown"
      onChange={onChange}
    />,
  );

  const panel = screen.getByTestId('newsletters-format-panel');
  const htmlButton = within(panel).getByRole('button', { name: /HTML/ });
  const markdownButton = within(panel).getByRole('button', { name: /MARKDOWN/ });
  const pdfButton = within(panel).getByRole('button', { name: /PDF/ });

  expect(panel).toHaveClass('bg-white');
  expect(panel).toHaveClass('h-full');
  expect(panel.className).not.toContain('bg-slate-900');
  expect(within(panel).getByText('Report format')).toBeInTheDocument();
  expect(within(panel).queryByRole('heading')).not.toBeInTheDocument();
  expect(within(panel).queryByText(/HTML \/ Markdown \/ PDF/)).not.toBeInTheDocument();
  expect(within(panel).queryByText(/미리보기 영역/)).not.toBeInTheDocument();
  expect(within(panel).getByText('HT')).toBeInTheDocument();
  expect(within(panel).getByText('MD')).toBeInTheDocument();
  expect(htmlButton).toHaveAttribute('aria-pressed', 'false');
  expect(markdownButton).toHaveAttribute('aria-pressed', 'true');
  expect(pdfButton).toHaveAttribute('aria-pressed', 'false');

  fireEvent.click(pdfButton);

  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});

test('renders report-style format cards with dark theme classes', () => {
  render(
    <NewsletterAssetSelector
      theme="dark"
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="pdf"
      onChange={vi.fn()}
    />,
  );

  const panel = screen.getByTestId('newsletters-format-panel');

  expect(panel).toHaveClass('bg-slate-900/95');
  expect(within(panel).getByRole('button', { name: /PDF/ })).toHaveAttribute('aria-pressed', 'true');
});
