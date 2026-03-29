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
vi.spyOn(api, 'uploadThumbnail').mockResolvedValue({ thumbnail_path: 'thumbnails/sample.png' });

test('submits markdown form', async () => {
  render(<NewsletterForm mode="create" />);
  fireEvent.change(screen.getByLabelText('제목'), { target: { value: '새 Markdown' } });
  fireEvent.click(screen.getByRole('button', { name: 'Markdown 뉴스레터 생성' }));
  expect(await screen.findByText('생성되었습니다.')).toBeInTheDocument();
});

test('hides markdown editor and shows imported asset details for html newsletter edit', async () => {
  render(
    <NewsletterForm
      mode="edit"
      initialData={{
        id: 2,
        title: '가져온 뉴스레터',
        slug: 'newsletter-20260206',
        description: '설명',
        source_type: 'html',
        tags: [],
        available_assets: [
          {
            asset_type: 'html',
            content_url: '/api/v1/newsletters/2/content/html',
            download_url: '/api/v1/newsletters/2/download/html',
            is_primary: true,
            file_path: 'newsletter_20260206.html',
          },
        ],
        default_asset_type: 'html',
        is_active: true,
        source_file_path: 'newsletter_20260206.html',
        source_identifier: '20260206',
      }}
    />,
  );

  expect(await screen.findByText('연결 자산')).toBeInTheDocument();
  expect(screen.queryByLabelText('Markdown 본문')).not.toBeInTheDocument();
  expect(screen.getByText('소스 식별자:')).toBeInTheDocument();
  expect(screen.getAllByText('newsletter_20260206.html')).toHaveLength(2);
  expect(screen.getByLabelText('공개 활성 상태')).toBeChecked();
});
