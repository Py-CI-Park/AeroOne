'use client';
import { useMemo, useState } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import { compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

export function AdminSearchSection() {
  const { state, searchForm, setSearchForm, runSearch } = useAdminConsoleData();
  const [resultSearch, setResultSearch] = useState('');
  const [resultSort, setResultSort] = useState('source-asc');
  const visibleResults = useMemo(() => {
    const query = normalizeListQuery(resultSearch);
    const filtered = state.searchResults.filter((result) => matchesListQuery(query, [result.title, result.snippet, result.source, result.url]));
    return stableSort(filtered, (a, b) => {
      if (resultSort === 'title-asc') return compareText(a.title, b.title) || compareText(a.source, b.source) || compareText(a.url, b.url);
      if (resultSort === 'url-asc') return compareText(a.url, b.url) || compareText(a.source, b.source) || compareText(a.title, b.title);
      return compareText(a.source, b.source) || compareText(a.title, b.title) || compareText(a.url, b.url);
    });
  }, [resultSearch, resultSort, state.searchResults]);
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">통합 검색 / AI 운영</h2>
      <div className="flex flex-wrap gap-2 text-sm"><input placeholder="뉴스레터·Document·Civil 검색" value={searchForm.q} onChange={(event) => setSearchForm((current) => ({ ...current, q: event.target.value }))} className="min-w-64 flex-1 rounded-md border border-slate-300 px-2 py-1" aria-label="통합 검색어" /><label className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={searchForm.includeNsa} onChange={(event) => setSearchForm((current) => ({ ...current, includeNsa: event.target.checked }))} /> NSA 포함</label><button type="button" onClick={() => void runSearch()} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white">검색</button></div>
      <ListFilter
        id="admin-search-results"
        searchLabel="결과 내 검색"
        searchPlaceholder="title / snippet / source / url"
        searchValue={resultSearch}
        onSearchChange={setResultSearch}
        sortLabel="검색 결과 정렬"
        sortValue={resultSort}
        onSortChange={setResultSort}
        sortOptions={[
          { value: 'source-asc', label: 'source ↑ / title ↑' },
          { value: 'title-asc', label: 'title ↑ / source ↑' },
          { value: 'url-asc', label: 'url ↑ / source ↑' },
        ]}
        totalCount={state.searchResults.length}
        filteredCount={visibleResults.length}
      />
      <div className="mt-3 space-y-2">
        <ListState loading={state.busy === 'search'} error={state.error} totalCount={state.searchResults.length} filteredCount={visibleResults.length} emptyMessage="2글자 이상 입력하면 뉴스레터와 문서를 한 번에 검색합니다. NSA는 권한이 있을 때만 포함됩니다." noMatchesMessage="결과 내 검색 조건에 맞는 통합 검색 결과가 없습니다." />
        {visibleResults.map((result, index) => <a key={`${result.source}-${result.url}-${index}`} href={result.url} className="block rounded-lg border border-slate-100 px-3 py-2 text-sm"><div className="flex items-center justify-between gap-2"><strong>{result.title}</strong><Badge tone="blue">{result.source}</Badge></div><p className="mt-1 text-slate-500">{result.snippet || result.url}</p></a>)}
      </div>
    </section>
  );
}
