'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { fetchAiStatus, fetchCollectionSearch, sendAiChat } from '@/lib/api';
import type { AiChatMessage, AiCitation, AiStatusResponse, CollectionSearchResult } from '@/lib/types';

const DEFAULT_STATUS: AiStatusResponse = {
  enabled: true,
  base_url: '',
  model: 'gemma4:12b',
  reachable: false,
  model_available: false,
  status: 'unavailable',
  detail: '상태를 확인하는 중입니다.',
};

function statusLabel(status: AiStatusResponse): string {
  if (status.status === 'ok') return `${status.model} 준비됨`;
  if (status.status === 'disabled') return 'AI 기능 비활성화';
  if (status.status === 'model_missing') return `${status.model} 모델 없음`;
  return 'Ollama 연결 불가';
}

function citationKey(citation: AiCitation | CollectionSearchResult): string {
  return `${citation.collection}:${citation.path}`;
}

export function AiChatWorkspace() {
  const [status, setStatus] = useState<AiStatusResponse>(DEFAULT_STATUS);
  const [statusError, setStatusError] = useState('');
  const [messages, setMessages] = useState<AiChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [useSearch, setUseSearch] = useState(false);
  const [pending, setPending] = useState(false);
  const [chatError, setChatError] = useState('');
  const [citations, setCitations] = useState<AiCitation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchPending, setSearchPending] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searchResults, setSearchResults] = useState<CollectionSearchResult[]>([]);
  const [searchDegraded, setSearchDegraded] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetchAiStatus()
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload);
          setStatusError('');
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setStatus(DEFAULT_STATUS);
          setStatusError(error instanceof Error ? error.message : 'AI 상태를 확인하지 못했습니다.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit = useMemo(() => input.trim().length > 0 && !pending, [input, pending]);

  async function handleChatSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || pending) return;
    const nextMessages = [...messages, { role: 'user' as const, content }];
    setMessages(nextMessages);
    setInput('');
    setPending(true);
    setChatError('');
    setCitations([]);
    try {
      const response = await sendAiChat({
        messages: nextMessages,
        use_search: useSearch,
        collections: ['document', 'civil'],
        limit: 5,
      });
      setMessages([...nextMessages, response.message]);
      setCitations(response.citations);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'AI 응답 생성에 실패했습니다.');
    } finally {
      setPending(false);
    }
  }

  async function handleSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = searchQuery.trim();
    if (!q || searchPending) return;
    setSearchPending(true);
    setSearchError('');
    setSearchDegraded('');
    try {
      const response = await fetchCollectionSearch({ q, collections: ['document', 'civil'], limit: 20 });
      setSearchResults(response.results);
      setSearchDegraded(response.degraded ? response.reason ?? '검색 인덱스를 사용할 수 없습니다.' : '');
    } catch (error) {
      setSearchResults([]);
      setSearchError(error instanceof Error ? error.message : '문서 검색에 실패했습니다.');
    } finally {
      setSearchPending(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
      <section className="rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-ink-1">AI Chat</h2>
            <p className="text-sm text-ink-3">OpenWebUI / ollama run 처럼 gemma4:12b 와 대화합니다.</p>
          </div>
          <div data-testid="ai-status" className="rounded-full bg-surface-sunken px-3 py-1 text-xs text-ink-2">
            {statusLabel(status)}
          </div>
        </div>

        {statusError ? <p className="mb-3 rounded bg-warn-soft px-3 py-2 text-sm text-warn">{statusError}</p> : null}
        {status.status !== 'ok' ? (
          <p data-testid="ai-degraded" className="mb-3 rounded bg-warn-soft px-3 py-2 text-sm text-warn">
            {status.detail ?? 'Ollama 상태를 확인하세요.'}
          </p>
        ) : null}

        <div data-testid="ai-messages" className="mb-3 flex max-h-[520px] min-h-[260px] flex-col gap-3 overflow-y-auto rounded-xl border border-line-subtle bg-surface-elevated p-3">
          {messages.length === 0 ? (
            <div className="text-sm text-ink-3">질문을 입력하면 AI 답변이 여기에 표시됩니다.</div>
          ) : null}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`rounded-lg px-3 py-2 text-sm ${message.role === 'user' ? 'ml-8 bg-accent text-accent-on' : 'mr-8 bg-surface-sunken text-ink-1'}`}
            >
              <div className="mb-1 text-xs opacity-70">{message.role === 'user' ? '사용자' : 'AI'}</div>
              <div className="whitespace-pre-wrap">{message.content}</div>
            </div>
          ))}
          {pending ? (
            <div data-testid="ai-pending" className="mr-8 rounded-lg bg-surface-sunken px-3 py-2 text-sm text-ink-2">
              gemma4:12b 응답 생성 중… 잠시 기다려 주세요.
            </div>
          ) : null}
        </div>

        {citations.length > 0 ? (
          <div className="mb-3 rounded-lg border border-line-subtle bg-surface-elevated p-3">
            <h3 className="mb-2 text-sm font-semibold text-ink-1">답변 근거</h3>
            <div className="flex flex-col gap-1">
              {citations.map((citation) => (
                <a key={citationKey(citation)} href={citation.navigation_url} className="text-sm text-accent hover:underline">
                  {citation.collection} · {citation.folder ? `${citation.folder}/` : ''}{citation.name}
                </a>
              ))}
            </div>
          </div>
        ) : null}

        {chatError ? <p role="alert" className="mb-3 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{chatError}</p> : null}

        <form onSubmit={handleChatSubmit} className="flex flex-col gap-2">
          <textarea
            data-testid="ai-chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="gemma4:12b 에게 질문하세요"
            className="min-h-24 rounded border border-line-subtle bg-surface-elevated px-3 py-2 text-base text-ink-1 placeholder:text-ink-3"
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="inline-flex items-center gap-2 text-sm text-ink-2">
              <input type="checkbox" checked={useSearch} onChange={(event) => setUseSearch(event.target.checked)} />
              문서 검색 결과를 답변 근거로 사용(document/civil)
            </label>
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-md bg-accent px-4 py-2 text-base font-medium text-accent-on transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
            >
              {pending ? '응답 대기 중' : '보내기'}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-ink-1">HTML 본문 검색</h2>
        <p className="mb-3 text-sm text-ink-3">_database 의 Document/Civil HTML 본문을 빠르게 검색하고 파일로 바로 이동합니다.</p>
        <form onSubmit={handleSearchSubmit} className="mb-3 flex gap-2">
          <input
            data-testid="ai-search-input"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="문서 내용 검색"
            className="min-w-0 flex-1 rounded border border-line-subtle bg-surface-elevated px-3 py-2 text-base text-ink-1 placeholder:text-ink-3"
          />
          <button type="submit" disabled={searchPending} className="rounded-md bg-accent px-4 py-2 text-base font-medium text-accent-on disabled:opacity-60">
            {searchPending ? '검색 중' : '검색'}
          </button>
        </form>
        {searchPending ? <p data-testid="ai-search-pending" className="text-sm text-ink-3">본문 검색 중…</p> : null}
        {searchDegraded ? <p className="rounded bg-warn-soft px-3 py-2 text-sm text-warn">{searchDegraded}</p> : null}
        {searchError ? <p role="alert" className="rounded bg-danger-soft px-3 py-2 text-sm text-danger">{searchError}</p> : null}
        <div data-testid="ai-search-results" className="flex flex-col gap-2">
          {searchResults.map((result) => (
            <a key={citationKey(result)} href={result.navigation_url} className="rounded-lg border border-line-subtle bg-surface-elevated p-3 transition hover:bg-surface-sunken">
              <div className="text-sm font-semibold text-ink-1">{result.collection} · {result.folder ? `${result.folder}/` : ''}{result.name}</div>
              <div className="mt-1 text-sm text-ink-2">{result.snippet || result.path}</div>
              <div className="mt-1 text-xs text-accent">파일 열기</div>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
