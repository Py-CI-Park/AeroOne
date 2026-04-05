import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';

// @ts-expect-error -- Task 2 creates this component; Task 1 keeps the runtime import red on purpose.
import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import type { AssetType } from '@/lib/types';

test('renders a format panel with explicit asset choices and selected-state semantics', () => {
  const onChange = vi.fn();

  render(
    <NewsletterAssetSelector
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="markdown"
      onChange={onChange}
    />,
  );

  const panel = screen.getByTestId('newsletters-format-panel');
  const htmlButton = within(panel).getByRole('button', { name: 'HTML' });
  const markdownButton = within(panel).getByRole('button', { name: 'MARKDOWN' });
  const pdfButton = within(panel).getByRole('button', { name: 'PDF' });

  expect(within(panel).getByText('Format')).toBeInTheDocument();
  expect(within(panel).getByRole('heading', { name: '형식 선택' })).toBeInTheDocument();
  expect(htmlButton).toHaveAttribute('aria-pressed', 'false');
  expect(markdownButton).toHaveAttribute('aria-pressed', 'true');
  expect(pdfButton).toHaveAttribute('aria-pressed', 'false');

  fireEvent.click(pdfButton);

  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});
