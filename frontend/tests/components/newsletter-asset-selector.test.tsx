import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import type { AssetType } from '@/lib/types';

test('renders every explicit asset choice and reports selection changes', () => {
  const onChange = vi.fn();

  render(
    <NewsletterAssetSelector
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="markdown"
      onChange={onChange}
    />,
  );

  expect(screen.getByRole('button', { name: 'HTML' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'MARKDOWN' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));

  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});
