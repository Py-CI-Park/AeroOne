'use client';

import { useMemo, useState } from 'react';

import { categoryToDraft, tagToDraft, useAdminConsoleData } from '../admin-console-tabs';
import { compareNumber, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

export function AdminTaxonomySection() {
  const { state, categoryForm, setCategoryForm, tagForm, setTagForm, categoryDrafts, setCategoryDrafts, tagDrafts, setTagDrafts, createTaxonomy, saveCategory, saveTag } = useAdminConsoleData();
  const [categorySearch, setCategorySearch] = useState('');
  const [categorySort, setCategorySort] = useState('sort-order-asc');
  const [tagSearch, setTagSearch] = useState('');
  const [tagSort, setTagSort] = useState('sort-order-asc');

  const visibleCategories = useMemo(() => {
    const query = normalizeListQuery(categorySearch);
    const filtered = state.categories.filter((category) => matchesListQuery(query, [category.name, category.slug, category.description]));
    return stableSort(filtered, (a, b) => {
      if (categorySort === 'name-asc') return compareText(a.name, b.name) || a.id - b.id;
      if (categorySort === 'name-desc') return compareText(b.name, a.name) || a.id - b.id;
      return compareNumber(a.sort_order, b.sort_order) || compareText(a.name, b.name) || a.id - b.id;
    });
  }, [categorySearch, categorySort, state.categories]);

  const visibleTags = useMemo(() => {
    const query = normalizeListQuery(tagSearch);
    const filtered = state.tags.filter((tag) => matchesListQuery(query, [tag.name, tag.slug]));
    return stableSort(filtered, (a, b) => {
      if (tagSort === 'name-asc') return compareText(a.name, b.name) || a.id - b.id;
      if (tagSort === 'name-desc') return compareText(b.name, a.name) || a.id - b.id;
      return compareNumber(a.sort_order, b.sort_order) || compareText(a.name, b.name) || a.id - b.id;
    });
  }, [tagSearch, tagSort, state.tags]);

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">카테고리/태그 관리</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="mb-2 grid gap-2 text-sm">
            <input placeholder="카테고리명" value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="카테고리명" />
            <input placeholder="설명" value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="카테고리 설명" />
            <input type="number" value={categoryForm.sort_order} onChange={(event) => setCategoryForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="카테고리 sort order" />
            <button type="button" onClick={() => void createTaxonomy('category')} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white">카테고리 생성</button>
          </div>
          <ListFilter
            id="admin-categories"
            searchLabel="카테고리 검색"
            searchPlaceholder="name / slug / description"
            searchValue={categorySearch}
            onSearchChange={setCategorySearch}
            sortLabel="카테고리 정렬"
            sortValue={categorySort}
            onSortChange={setCategorySort}
            sortOptions={[{ value: 'sort-order-asc', label: 'sort_order 오름차순' }, { value: 'name-asc', label: 'name 오름차순' }, { value: 'name-desc', label: 'name 내림차순' }]}
            totalCount={state.categories.length}
            filteredCount={visibleCategories.length}
          />
          <div className="space-y-2">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.categories.length} filteredCount={visibleCategories.length} emptyMessage="등록된 카테고리가 없습니다." noMatchesMessage="검색 조건에 맞는 카테고리가 없습니다." />
            {visibleCategories.map((category) => {
              const draft = categoryDrafts[category.id] ?? categoryToDraft(category);
              return <div key={category.id} className="rounded-lg border border-slate-100 p-2 text-sm"><input value={draft.name} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, name: event.target.value } }))} className="w-full rounded-md border border-slate-300 px-2 py-1" aria-label={`${category.name} category name`} /><div className="mt-1 flex items-center gap-2"><input type="number" value={draft.sort_order} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, sort_order: Number(event.target.value) } }))} className="w-20 rounded-md border border-slate-300 px-2 py-1" aria-label={`${category.name} category sort order`} /><label className="text-xs"><input type="checkbox" checked={draft.is_active} onChange={(event) => setCategoryDrafts((current) => ({ ...current, [category.id]: { ...draft, is_active: event.target.checked } }))} /> active</label><button type="button" onClick={() => void saveCategory(category)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">저장</button></div></div>;
            })}
          </div>
        </div>
        <div>
          <div className="mb-2 grid gap-2 text-sm">
            <input placeholder="태그명" value={tagForm.name} onChange={(event) => setTagForm((current) => ({ ...current, name: event.target.value }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="태그명" />
            <input type="number" value={tagForm.sort_order} onChange={(event) => setTagForm((current) => ({ ...current, sort_order: Number(event.target.value) }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label="태그 sort order" />
            <button type="button" onClick={() => void createTaxonomy('tag')} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white">태그 생성</button>
          </div>
          <ListFilter
            id="admin-tags"
            searchLabel="태그 검색"
            searchPlaceholder="name / slug"
            searchValue={tagSearch}
            onSearchChange={setTagSearch}
            sortLabel="태그 정렬"
            sortValue={tagSort}
            onSortChange={setTagSort}
            sortOptions={[{ value: 'sort-order-asc', label: 'sort_order 오름차순' }, { value: 'name-asc', label: 'name 오름차순' }, { value: 'name-desc', label: 'name 내림차순' }]}
            totalCount={state.tags.length}
            filteredCount={visibleTags.length}
          />
          <div className="space-y-2">
            <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.tags.length} filteredCount={visibleTags.length} emptyMessage="등록된 태그가 없습니다." noMatchesMessage="검색 조건에 맞는 태그가 없습니다." />
            {visibleTags.map((tag) => {
              const draft = tagDrafts[tag.id] ?? tagToDraft(tag);
              return <div key={tag.id} className="rounded-lg border border-slate-100 p-2 text-sm"><input value={draft.name} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, name: event.target.value } }))} className="w-full rounded-md border border-slate-300 px-2 py-1" aria-label={`${tag.name} tag name`} /><div className="mt-1 flex items-center gap-2"><input type="number" value={draft.sort_order} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, sort_order: Number(event.target.value) } }))} className="w-20 rounded-md border border-slate-300 px-2 py-1" aria-label={`${tag.name} tag sort order`} /><label className="text-xs"><input type="checkbox" checked={draft.is_active} onChange={(event) => setTagDrafts((current) => ({ ...current, [tag.id]: { ...draft, is_active: event.target.checked } }))} /> active</label><button type="button" onClick={() => void saveTag(tag)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">저장</button></div></div>;
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
