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

  expect(within(panel).getByText('Report format')).toBeInTheDocument();
  expect(within(panel).getByRole('heading', { name: 'HTML / Markdown / PDF 선택' })).toBeInTheDocument();
  expect(within(panel).getByText('HT')).toBeInTheDocument();
  expect(within(panel).getByText('MD')).toBeInTheDocument();
  expect(htmlButton).toHaveAttribute('aria-pressed', 'false');
  expect(markdownButton).toHaveAttribute('aria-pressed', 'true');
  expect(pdfButton).toHaveAttribute('aria-pressed', 'false');

  fireEvent.click(pdfButton);

  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});
