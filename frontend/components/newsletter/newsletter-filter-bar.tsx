import React from 'react';
import Link from 'next/link';

import type { SourceType } from '@/lib/types';

type Option = {
  slug: string;
  name: string;
};

export function NewsletterFilterBar({
  current,
  categories,
  tags,
}: {
  current: {
    q: string;
    category: string;
    tag: string;
    source_type: SourceType | '';
  };
  categories: Option[];
  tags: Option[];
}) {
  return (
    <form className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm" method="GET">
      <div className="grid gap-4 md:grid-cols-4">
        <div className="md:col-span-2">
          <label htmlFor="newsletter-q" className="mb-1 block text-sm font-medium text-slate-700">
            검색어
          </label>
          <input
            id="newsletter-q"
            name="q"
            defaultValue={current.q}
            placeholder="제목, 설명, 태그 검색"
            className="w-full rounded-md border border-slate-300 px-3 py-2"
          />
        </div>
        <div>
          <label htmlFor="newsletter-category-filter" className="mb-1 block text-sm font-medium text-slate-700">
            카테고리
          </label>
          <select
            id="newsletter-category-filter"
            name="category"
            defaultValue={current.category}
            className="w-full rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="">전체</option>
            {categories.map((category) => (
              <option key={category.slug} value={category.slug}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="newsletter-source-type-filter" className="mb-1 block text-sm font-medium text-slate-700">
            유형
          </label>
          <select
            id="newsletter-source-type-filter"
            name="source_type"
            defaultValue={current.source_type}
            className="w-full rounded-md border border-slate-300 px-3 py-2"
          >
            <option value="">전체</option>
            <option value="html">HTML</option>
            <option value="pdf">PDF</option>
            <option value="markdown">Markdown</option>
          </select>
        </div>
      </div>

      <div className="mt-4">
        <label htmlFor="newsletter-tag-filter" className="mb-1 block text-sm font-medium text-slate-700">
          태그
        </label>
        <select
          id="newsletter-tag-filter"
          name="tag"
          defaultValue={current.tag}
          className="w-full rounded-md border border-slate-300 px-3 py-2 md:max-w-sm"
        >
          <option value="">전체</option>
          {tags.map((tag) => (
            <option key={tag.slug} value={tag.slug}>
              #{tag.name}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="submit" className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white">
          검색 / 필터 적용
        </button>
        <Link href="/newsletters" className="rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
          초기화
        </Link>
      </div>
    </form>
  );
}
