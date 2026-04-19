'use client';

import React from 'react';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { fetchAdminNewsletters } from '@/lib/api';
import type { NewsletterItem } from '@/lib/types';

export function AdminNewsletterList() {
  const [items, setItems] = useState<NewsletterItem[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    void fetchAdminNewsletters().then(setItems).catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">관리자 뉴스레터</h1>
        <div className="flex gap-2">
          <Link href="/admin/imports" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white">Import / Sync</Link>
          <Link href="/admin/newsletters/new" className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white">새 Markdown</Link>
        </div>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-4 py-3">제목</th>
              <th className="px-4 py-3">유형</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">작업</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-t border-slate-200">
                <td className="px-4 py-3">{item.title}</td>
                <td className="px-4 py-3 uppercase">{item.source_type}</td>
                <td className="px-4 py-3">활성</td>
                <td className="px-4 py-3">
                  <Link href={`/admin/newsletters/${item.id}/edit`} className="text-blue-700">편집</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
