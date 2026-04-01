'use client';

import React from 'react';

import { FormEvent, useEffect, useState } from 'react';
import { createNewsletter, fetchCategories, fetchTags, updateNewsletter, uploadThumbnail } from '@/lib/api';
import { getBrowserApiBase } from '@/lib/api';
import { getCookie } from '@/lib/cookies';
import type { NewsletterDetail } from '@/lib/types';

type Props = {
  mode: 'create' | 'edit';
  initialData?: NewsletterDetail;
};

export function NewsletterForm({ mode, initialData }: Props) {
  const isEdit = mode === 'edit';
  const isMarkdown = (initialData?.source_type ?? 'markdown') === 'markdown';
  const [title, setTitle] = useState(initialData?.title ?? '');
  const [description, setDescription] = useState(initialData?.description ?? '');
  const [summary, setSummary] = useState(initialData?.summary ?? '');
  const [markdownBody, setMarkdownBody] = useState(initialData?.markdown_body ?? '');
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);
  const [tags, setTags] = useState<{ id: number; name: string }[]>([]);
  const [categoryId, setCategoryId] = useState<number | ''>(initialData?.category?.id ?? '');
  const [tagIds, setTagIds] = useState<number[]>(initialData?.tags.map((tag) => tag.id) ?? []);
  const [isActive, setIsActive] = useState(initialData?.is_active ?? true);
  const [message, setMessage] = useState('');
  const [thumbnailFile, setThumbnailFile] = useState<File | null>(null);
  const [thumbnailPath, setThumbnailPath] = useState(initialData?.thumbnail_path ?? '');
  const [thumbnailUrl, setThumbnailUrl] = useState(initialData?.thumbnail_url ?? '');

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
      is_active: isActive,
      ...(isMarkdown ? { source_type: 'markdown', markdown_body: markdownBody || undefined } : {}),
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

  async function handleThumbnailUpload() {
    if (!initialData || !thumbnailFile) {
      return;
    }
    const formData = new FormData();
    formData.append('file', thumbnailFile);
    const csrfToken = getCookie('csrf_token');
    const response = await uploadThumbnail(initialData.id, formData, csrfToken);
    setThumbnailPath(response.thumbnail_path);
    setThumbnailUrl(`${getBrowserApiBase()}/storage/${response.thumbnail_path}`);
    setMessage('썸네일이 업로드되었습니다.');
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      {isEdit ? (
        <section className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          <div className="mb-2 flex flex-wrap gap-2">
            <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-medium uppercase text-white">{initialData?.source_type}</span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${isActive ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-700'}`}>
              {isActive ? '활성' : '비활성'}
            </span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <div><span className="font-medium text-slate-900">슬러그:</span> {initialData?.slug}</div>
            <div><span className="font-medium text-slate-900">소스 식별자:</span> {initialData?.source_identifier ?? '-'}</div>
            <div className="md:col-span-2"><span className="font-medium text-slate-900">기본 파일 경로:</span> {initialData?.source_file_path ?? initialData?.markdown_file_path ?? '-'}</div>
          </div>
          <div className="mt-3">
            <div className="mb-2 font-medium text-slate-900">연결 자산</div>
            <ul className="space-y-2">
              {initialData?.available_assets.map((asset) => (
                <li key={`${asset.asset_type}-${asset.file_path ?? asset.content_url}`} className="rounded-md border border-slate-200 bg-white px-3 py-2">
                  <span className="mr-2 rounded bg-slate-100 px-2 py-1 text-xs uppercase">{asset.asset_type}</span>
                  <span className="text-xs text-slate-600">{asset.file_path ?? '-'}</span>
                  {asset.is_primary ? <span className="ml-2 text-xs font-medium text-blue-700">기본 자산</span> : null}
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

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
      {isMarkdown ? (
        <div>
          <label htmlFor="newsletter-markdown" className="mb-1 block text-sm font-medium text-slate-700">Markdown 본문</label>
          <textarea id="newsletter-markdown" value={markdownBody} onChange={(event) => setMarkdownBody(event.target.value)} className="min-h-64 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm" />
        </div>
      ) : null}
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
      {isEdit ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
            <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
            공개 활성 상태
          </label>
          <div className="mt-4 space-y-3">
            <div className="text-sm font-medium text-slate-700">썸네일</div>
            {thumbnailUrl ? (
              <img src={thumbnailUrl} alt="thumbnail preview" className="h-32 rounded-md border border-slate-200 object-cover" />
            ) : (
              <div className="rounded-md border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">등록된 썸네일이 없습니다.</div>
            )}
            <div className="text-xs text-slate-500">{thumbnailPath || '현재 경로 없음'}</div>
            <div className="flex flex-wrap items-center gap-3">
              <input type="file" accept="image/*" onChange={(event) => setThumbnailFile(event.target.files?.[0] ?? null)} className="text-sm" />
              <button type="button" onClick={handleThumbnailUpload} disabled={!thumbnailFile || !initialData} className="rounded-md bg-slate-700 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300">
                썸네일 업로드
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <button type="submit" className="rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white">
        {mode === 'create' ? 'Markdown 뉴스레터 생성' : '변경 저장'}
      </button>
      {message ? <p className="text-sm text-green-700">{message}</p> : null}
    </form>
  );
}
