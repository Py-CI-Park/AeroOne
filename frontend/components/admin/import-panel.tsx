'use client';

import React from 'react';

import { useState } from 'react';
import { syncNewsletters } from '@/lib/api';
import { getCookie } from '@/lib/cookies';
import type { SyncResponse } from '@/lib/types';

export function ImportPanel() {
  const [result, setResult] = useState<SyncResponse | null>(null);
  const [error, setError] = useState('');

  async function handleSync() {
    try {
      setError('');
      setResult(await syncNewsletters(getCookie('csrf_token')));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'sync failed');
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-2 text-lg font-semibold text-slate-900">Import / Sync</h2>
      <p className="text-sm text-slate-500">`Newsletter/output` 하위 HTML/PDF 파일을 스캔하고 DB 메타데이터와 동기화합니다.</p>
      <button type="button" onClick={handleSync} className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white">Import / Sync 실행</button>
      {result ? (
        <div className="mt-4 grid gap-2 text-sm text-slate-700 md:grid-cols-2">
          <div>created: {result.created}</div>
          <div>updated: {result.updated}</div>
          <div>deactivated: {result.deactivated}</div>
          <div>skipped: {result.skipped}</div>
          <div>issues: {result.issues}</div>
        </div>
      ) : null}
      {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}
    </section>
  );
}
