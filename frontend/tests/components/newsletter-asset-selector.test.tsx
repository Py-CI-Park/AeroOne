import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { NewsletterAssetSelector } from '@/components/newsletter/newsletter-asset-selector';
import type { AssetType } from '@/lib/types';

test('renders explicit asset choices and reports selection changes', () => {
  const onChange = vi.fn();

  render(
    <NewsletterAssetSelector
      availableAssetTypes={['html', 'markdown', 'pdf']}
      selectedAsset="markdown"
      onChange={onChange}
    />,
  );

  expect(screen.getByRole('heading', { name: '형식 선택' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));
  expect(onChange).toHaveBeenCalledWith('pdf' satisfies AssetType);
});
