'use client';

import React from 'react';

export type SortOption = {
  value: string;
  label: string;
};

type ListFilterProps = {
  id: string;
  searchLabel: string;
  searchPlaceholder?: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  sortLabel: string;
  sortValue: string;
  onSortChange: (value: string) => void;
  sortOptions: SortOption[];
  totalCount: number;
  filteredCount: number;
};

export function normalizeListQuery(value: string) {
  return value.trim().toLocaleLowerCase('ko-KR');
}

export function matchesListQuery(query: string, fields: Array<string | number | null | undefined>) {
  if (!query) return true;
  return fields.some((field) => String(field ?? '').toLocaleLowerCase('ko-KR').includes(query));
}

export function compareText(a: string | null | undefined, b: string | null | undefined) {
  return String(a ?? '').localeCompare(String(b ?? ''), 'ko-KR', { numeric: true, sensitivity: 'base' });
}

export function compareNumber(a: number | null | undefined, b: number | null | undefined) {
  return (a ?? 0) - (b ?? 0);
}

export function compareDate(a: string | null | undefined, b: string | null | undefined) {
  return new Date(a ?? 0).getTime() - new Date(b ?? 0).getTime();
}

export function stableSort<T>(items: T[], compare: (a: T, b: T) => number) {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => compare(a.item, b.item) || a.index - b.index)
    .map(({ item }) => item);
}
export function paginate<T>(items: T[], page: number, pageSize: number): { pageItems: T[]; page: number; totalPages: number } {
  if (pageSize <= 0) return { pageItems: items, page: 0, totalPages: 1 };

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const normalizedPage = Number.isFinite(page) ? Math.trunc(page) : 0;
  const clampedPage = Math.min(Math.max(0, normalizedPage), totalPages - 1);
  const start = clampedPage * pageSize;
  return { pageItems: items.slice(start, start + pageSize), page: clampedPage, totalPages };
}

export function ListPagination({
  id,
  page,
  totalPages,
  onPageChange,
}: {
  id: string;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav className="mt-3 flex items-center justify-between gap-2 text-sm" aria-label={`${id} 페이지 이동`}>
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 0} className="rounded-md border border-slate-200 px-3 py-1 font-semibold text-slate-700 disabled:opacity-50">
        이전 페이지
      </button>
      <p className="text-xs font-semibold text-slate-600" aria-live="polite">페이지 {page + 1} / {totalPages}</p>
      <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages - 1} className="rounded-md border border-slate-200 px-3 py-1 font-semibold text-slate-700 disabled:opacity-50">
        다음 페이지
      </button>
    </nav>
  );
}

export function ListFilter({
  id,
  searchLabel,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  sortLabel,
  sortValue,
  onSortChange,
  sortOptions,
  totalCount,
  filteredCount,
}: ListFilterProps) {
  const searchId = `${id}-search`;
  const sortId = `${id}-sort`;
  return (
    <div className="mb-3 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
      <div className="grid gap-2 md:grid-cols-[1fr_14rem_auto] md:items-end">
        <div className="grid gap-1">
          <label className="text-xs font-semibold text-slate-600" htmlFor={searchId}>
            {searchLabel}
          </label>
          <div className="flex gap-2">
            <input
              id={searchId}
              type="search"
              value={searchValue}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={searchPlaceholder}
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900"
            />
            {searchValue ? (
              <button type="button" onClick={() => onSearchChange('')} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600">
                지우기
              </button>
            ) : null}
          </div>
        </div>
        <label className="grid gap-1 text-xs font-semibold text-slate-600" htmlFor={sortId}>
          {sortLabel}
          <select
            id={sortId}
            value={sortValue}
            onChange={(event) => onSortChange(event.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-normal text-slate-900"
          >
            {sortOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <p className="text-xs font-semibold text-slate-600" aria-live="polite">결과 {filteredCount} / {totalCount}건</p>
      </div>
    </div>
  );
}

export function ListState({
  loading,
  error,
  totalCount,
  filteredCount,
  emptyMessage,
  noMatchesMessage,
}: {
  loading?: boolean;
  error?: string;
  totalCount: number;
  filteredCount: number;
  emptyMessage: string;
  noMatchesMessage: string;
}) {
  if (loading) return <p className="text-sm text-slate-500" role="status" aria-live="polite">불러오는 중입니다.</p>;
  if (error) return <p className="text-sm text-red-600" role="alert">{error}</p>;
  if (totalCount === 0) return <p className="text-sm text-slate-500">{emptyMessage}</p>;
  if (filteredCount === 0) return <p className="text-sm text-slate-500">{noMatchesMessage}</p>;
  return null;
}
