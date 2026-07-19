'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';

import {
  deleteKnowledgeFolder,
  fetchKnowledgeFolders,
  registerKnowledgeFolder,
  reindexKnowledgeFolder,
  keywordSearchKnowledge,
  searchKnowledge,
  type KnowledgeFolder,
  type KnowledgeSearchHit,
} from '@/lib/api';
import { KnowledgeWiki } from '@/components/aero-work/knowledge-wiki';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work P2 '내 지식폴더' — 지정 폴더를 in-place 색인(Ollama nomic-embed 임베딩)하고
// 코사인 벡터 검색으로 근거를 찾는다. 폴더는 복사하지 않으며, 변경분만 증분 재색인한다.

const STATUS_META: Record<string, { label: string; tone: string }> = {
  pending: { label: '색인 대기', tone: 'bg-ink-3/10 text-ink-2' },
  ready: { label: '색인 완료', tone: 'bg-emerald-500/15 text-emerald-600' },
  error: { label: '오류', tone: 'bg-rose-500/15 text-rose-600' },
  indexing: { label: '색인 중', tone: 'bg-amber-500/15 text-amber-600' },
};

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, tone: 'bg-ink-3/10 text-ink-2' };
}

export function KnowledgePanel() {
  const [folders, setFolders] = useState<KnowledgeFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | 'register' | null>(null);
  const [form, setForm] = useState({ name: '', path: '' });
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<string>('all');
  const [mode, setMode] = useState<'semantic' | 'keyword'>('semantic');
  const [hits, setHits] = useState<KnowledgeSearchHit[] | null>(null);
  const [searchModel, setSearchModel] = useState<string>('');
  const [searching, setSearching] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchKnowledgeFolders();
      setFolders(data.folders);
      setError(null);
    } catch {
      setError('지식폴더 목록을 불러오지 못했음. 로그인 상태를 확인할 것.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.path.trim()) {
      return;
    }
    setBusyId('register');
    setError(null);
    try {
      await registerKnowledgeFolder({ name: form.name.trim(), path: form.path.trim() }, getCsrfCookie());
      setForm({ name: '', path: '' });
      await load();
    } catch {
      setError('폴더 등록 실패. 서버에 존재하는 절대 경로인지, 중복 등록이 아닌지 확인할 것.');
    } finally {
      setBusyId(null);
    }
  };

  const handleReindex = async (folder: KnowledgeFolder) => {
    setBusyId(folder.id);
    setError(null);
    try {
      await reindexKnowledgeFolder(folder.id, getCsrfCookie());
    } catch {
      setError('색인 실패. Ollama 임베딩 서버(nomic-embed-text) 기동 상태를 확인할 것.');
    } finally {
      await load();
      setBusyId(null);
    }
  };

  const handleDelete = async (folder: KnowledgeFolder) => {
    setBusyId(folder.id);
    setError(null);
    try {
      await deleteKnowledgeFolder(folder.id, getCsrfCookie());
      await load();
    } catch {
      setError('폴더 삭제 실패.');
      setBusyId(null);
    }
  };

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const request = { query: query.trim(), folder_id: scope === 'all' ? null : Number(scope), top_k: 8 };
      const response = mode === 'keyword' ? await keywordSearchKnowledge(request) : await searchKnowledge(request);
      setHits(response.hits);
      setSearchModel(response.model);
    } catch {
      setError('검색 실패. 색인된 폴더가 있는지, Ollama 가 켜져 있는지 확인할 것.');
      setHits([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="mt-4 space-y-6">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}

      {/* 폴더 등록 */}
      <form onSubmit={handleRegister} className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">지식폴더 등록</p>
        <p className="mt-1 text-xs text-ink-3">서버에서 접근 가능한 폴더의 절대 경로를 입력. 원본은 복사하지 않고 그 자리에서 색인함.</p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="이름(선택)"
            className="w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1 sm:w-40"
          />
          <input
            value={form.path}
            onChange={(event) => setForm((prev) => ({ ...prev, path: event.target.value }))}
            placeholder="D:\\업무\\지식자료 또는 /srv/kb"
            className="flex-1 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <button
            type="submit"
            disabled={busyId === 'register' || !form.path.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {busyId === 'register' ? '등록 중…' : '등록'}
          </button>
        </div>
      </form>

      {/* 폴더 목록 */}
      <div>
        <p className="text-sm font-semibold text-ink-1">등록된 폴더</p>
        {loading ? (
          <p className="mt-2 text-sm text-ink-3">불러오는 중…</p>
        ) : folders.length === 0 ? (
          <p className="mt-2 rounded-lg border border-dashed border-line-subtle bg-surface-base px-3 py-4 text-sm text-ink-3">
            아직 등록된 지식폴더가 없음. 위에서 폴더 경로를 등록하고 색인할 것.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {folders.map((folder) => {
              const meta = statusMeta(folder.status);
              const busy = busyId === folder.id;
              return (
                <li key={folder.id} className="rounded-xl border border-line-subtle bg-surface-base p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink-1">{folder.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${meta.tone}`}>{meta.label}</span>
                    <span className="text-xs text-ink-3">파일 {folder.file_count} · 청크 {folder.chunk_count}</span>
                  </div>
                  <p className="mt-1 break-all font-mono text-xs text-ink-3">{folder.path}</p>
                  {folder.status_detail ? <p className="mt-1 text-xs text-ink-2">{folder.status_detail}</p> : null}
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => void handleReindex(folder)}
                      disabled={busy}
                      className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken disabled:opacity-50"
                    >
                      {busy ? '색인 중…' : '재색인'}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(folder)}
                      disabled={busy}
                      className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-500/10 disabled:opacity-50"
                    >
                      삭제
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* 검색 */}
      <form onSubmit={handleSearch} className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">지식 검색</p>
        <p className="mt-1 text-xs text-ink-3">의미 검색은 벡터 유사도(질문 뜻), 키워드 검색은 단어 포함(즉시·Ollama 불필요)으로 근거를 찾음.</p>
        <div className="mt-2 flex gap-1">
          {[
            ['semantic', '의미 검색'],
            ['keyword', '키워드 검색'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value as 'semantic' | 'keyword')}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                mode === value ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2 hover:bg-accent-soft'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value)}
            className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          >
            <option value="all">전체 폴더</option>
            {folders.map((folder) => (
              <option key={folder.id} value={String(folder.id)}>{folder.name}</option>
            ))}
          </select>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="예: 출장 정산 규정, 보안 서약서 절차"
            className="flex-1 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {searching ? '검색 중…' : '검색'}
          </button>
        </div>

        {hits !== null ? (
          <div className="mt-4">
            {hits.length === 0 ? (
              <p className="text-sm text-ink-3">일치하는 근거가 없음.</p>
            ) : (
              <ul className="space-y-2">
                {hits.map((hit, index) => (
                  <li key={`${hit.folder_id}-${hit.rel_path}-${hit.chunk_index}-${index}`} className="rounded-lg border border-line-subtle bg-surface-raised p-3">
                    <div className="flex items-center gap-2 text-xs text-ink-3">
                      <span className="font-medium text-ink-2">{hit.folder_name}</span>
                      <span className="font-mono break-all">{hit.rel_path}</span>
                      <span className="ml-auto rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">유사도 {hit.score.toFixed(3)}</span>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink-1">{hit.content}</p>
                  </li>
                ))}
              </ul>
            )}
            {searchModel ? <p className="mt-2 text-[11px] text-ink-3">임베딩 모델: {searchModel}</p> : null}
          </div>
        ) : null}
      </form>

      <KnowledgeWiki />
    </div>
  );
}
