'use client';

import React from 'react';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { bulkUpdateNewsletters, fetchAdminNewsletters, fetchAssetHealth } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { AssetHealthResponse, NewsletterItem } from '@/lib/types';

const assetStatusMeta = {
  ok: { label: 'OK', className: 'bg-emerald-50 text-emerald-700' },
  missing: { label: '파일 없음', className: 'bg-red-50 text-red-700' },
  checksum_mismatch: { label: '체크섬 불일치', className: 'bg-amber-50 text-amber-800' },
  misconfig: { label: '설정 오류', className: 'bg-purple-50 text-purple-700' },
} as const;

export function AdminNewsletterList() {
  const [items, setItems] = useState<NewsletterItem[]>([]);
  const [health, setHealth] = useState<AssetHealthResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void Promise.all([fetchAdminNewsletters(), fetchAssetHealth()])
      .then(([newsletters, assetHealth]) => {
        setItems(newsletters);
        setHealth(assetHealth);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function runBulk(action: 'publish' | 'archive' | 'draft') {
    if (selectedIds.length === 0) return;
    const csrf = getCsrfCookie();
    await bulkUpdateNewsletters(selectedIds, action, csrf);
    const refreshed = await fetchAdminNewsletters();
    setItems(refreshed);
    setSelectedIds([]);
  }

  const filteredItems = items.filter((item) => {
    const matchesQuery = query.trim()
      ? item.title.toLowerCase().includes(query.trim().toLowerCase())
      : true;
    const matchesStatus = status ? (item.status ?? 'published') === status : true;
    return matchesQuery && matchesStatus;
  });

  const healthByNewsletter = new Map(
    (health?.items ?? []).map((asset) => [asset.newsletter_id, asset]),
  );

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-between gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">관리자 뉴스레터</h1>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin" className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">관리자 홈</Link>
          <Link href="/admin/read-events" className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">읽음 현황</Link>
          <Link href="/admin/imports" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white">Import / Sync</Link>
          <Link href="/admin/newsletters/new" className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white">새 Markdown</Link>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="제목 검색"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
          <option value="">전체 상태</option>
          <option value="draft">초안</option>
          <option value="scheduled">예약</option>
          <option value="published">게시</option>
          <option value="archived">보관</option>
        </select>
        <button type="button" onClick={() => void runBulk('publish')} className="rounded-md border border-emerald-300 px-3 py-2 text-sm font-semibold text-emerald-700">선택 게시</button>
        <button type="button" onClick={() => void runBulk('archive')} className="rounded-md border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-700">선택 보관</button>
        <span className="ml-auto text-xs text-slate-500">자산 OK {health?.ok ?? 0} · 파일 없음 {health?.missing ?? 0} · 체크섬 {health?.checksum_mismatch ?? 0} · 설정 오류 {health?.misconfig ?? 0}</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-4 py-3">선택</th>
              <th className="px-4 py-3">제목</th>
              <th className="px-4 py-3">유형</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">자산</th>
              <th className="px-4 py-3">작업</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => {
              const assetHealth = healthByNewsletter.get(item.id);
              const statusMeta = assetHealth ? assetStatusMeta[assetHealth.status] : assetStatusMeta.ok;
              return (
                <tr key={item.id} className="border-t border-slate-200">
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(item.id)}
                      onChange={(event) => {
                        setSelectedIds((current) =>
                          event.target.checked
                            ? [...current, item.id]
                            : current.filter((id) => id !== item.id),
                        );
                      }}
                    />
                  </td>
                  <td className="px-4 py-3">{item.title}</td>
                  <td className="px-4 py-3 uppercase">{item.source_type}</td>
                  <td className="px-4 py-3">{item.status ?? 'published'}</td>
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      <span className={`rounded px-2 py-1 text-xs font-semibold ${statusMeta.className}`}>{statusMeta.label}</span>
                      {assetHealth && !assetHealth.ok ? (
                        <div className="max-w-md text-xs text-slate-600">
                          <p>점검 필요 = DB 자산을 해석된 루트/경로에서 검증할 수 없음.</p>
                          <p>{assetHealth.remediation}</p>
                          <p className="font-mono text-[11px] text-slate-500">{assetHealth.resolved_path ?? assetHealth.resolved_root ?? assetHealth.file_path}</p>
                        </div>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/admin/newsletters/${item.id}/edit`} className="text-blue-700">편집</Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
