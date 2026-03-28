import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { NewsletterForm } from '@/components/admin/newsletter-form';
import * as api from '@/lib/api';

vi.spyOn(api, 'fetchCategories').mockResolvedValue([]);
vi.spyOn(api, 'fetchTags').mockResolvedValue([]);
vi.spyOn(api, 'createNewsletter').mockResolvedValue({
  id: 1,
  title: '새 Markdown',
  slug: 'new-markdown',
  source_type: 'markdown',
  tags: [],
  available_assets: [],
  default_asset_type: 'markdown',
} as never);

test('submits markdown form', async () => {
  render(<NewsletterForm mode="create" />);
  fireEvent.change(screen.getByLabelText('제목'), { target: { value: '새 Markdown' } });
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 뉴스레터 생성' }));
  expect(await screen.findByText('생성되었습니다.')).toBeInTheDocument();
});
