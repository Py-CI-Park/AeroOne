'use client';

import React from 'react';

import { FormEvent, useEffect, useState } from 'react';
import { createNewsletter, fetchCategories, fetchTags, updateNewsletter } from '@/lib/api';
import { getCookie } from '@/lib/cookies';
import type { NewsletterDetail } from '@/lib/types';

type Props = {
  mode: 'create' | 'edit';
  initialData?: NewsletterDetail;
};

export function NewsletterForm({ mode, initialData }: Props) {
  const [title, setTitle] = useState(initialData?.title ?? '');
  const [description, setDescription] = useState(initialData?.description ?? '');
  const [summary, setSummary] = useState(initialData?.summary ?? '');
  const [markdownBody, setMarkdownBody] = useState('');
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);
  const [tags, setTags] = useState<{ id: number; name: string }[]>([]);
  const [categoryId, setCategoryId] = useState<number | ''>(initialData?.category?.id ?? '');
  const [tagIds, setTagIds] = useState<number[]>(initialData?.tags.map((tag) => tag.id) ?? []);
  const [message, setMessage] = useState('');

  useEffect(() => {
    void fetchCategories().then(setCategories);
    void fetchTags().then(setTags);
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const payload = {
      title,
      description,
      summary,
      category_id: categoryId || null,
      tag_ids: tagIds,
      source_type: 'markdown',
      markdown_body: markdownBody || undefined,
    };
    const csrfToken = getCookie('csrf_token');

    if (mode === 'create') {
      await createNewsletter(payload, csrfToken);
      setMessage('생성되었습니다.');
      return;
    }

    if (initialData) {
      await updateNewsletter(initialData.id, payload, csrfToken);
      setMessage('저장되었습니다.');
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <label htmlFor="newsletter-title" className="mb-1 block text-sm font-medium text-slate-700">제목</label>
        <input id="newsletter-title" value={title} onChange={(event) => setTitle(event.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2" />
      </div>
      <div>
        <label htmlFor="newsletter-description" className="mb-1 block text-sm font-medium text-slate-700">설명</label>
        <textarea id="newsletter-description" value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2" />
      </div>
      <div>
        <label htmlFor="newsletter-summary" className="mb-1 block text-sm font-medium text-slate-700">요약</label>
        <textarea id="newsletter-summary" value={summary} onChange={(event) => setSummary(event.target.value)} className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2" />
      </div>
      <div>
        <label htmlFor="newsletter-markdown" className="mb-1 block text-sm font-medium text-slate-700">Markdown 본문</label>
        <textarea id="newsletter-markdown" value={markdownBody} onChange={(event) => setMarkdownBody(event.target.value)} className="min-h-64 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label htmlFor="newsletter-category" className="mb-1 block text-sm font-medium text-slate-700">카테고리</label>
          <select id="newsletter-category" value={categoryId} onChange={(event) => setCategoryId(event.target.value ? Number(event.target.value) : '')} className="w-full rounded-md border border-slate-300 px-3 py-2">
            <option value="">선택 안 함</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">태그</label>
          <div className="flex flex-wrap gap-2 rounded-md border border-slate-300 p-3">
            {tags.map((tag) => {
              const selected = tagIds.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => setTagIds((current) => selected ? current.filter((id) => id !== tag.id) : [...current, tag.id])}
                  className={`rounded-full px-3 py-1 text-sm ${selected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'}`}
                >
                  #{tag.name}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <button type="submit" className="rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white">
        {mode === 'create' ? 'Markdown 뉴스레터 생성' : '변경 저장'}
      </button>
      {message ? <p className="text-sm text-green-700">{message}</p> : null}
    </form>
  );
}
