'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  deleteAiConversation,
  fetchAiStatus,
  fetchCollectionSearch,
  fetchCollectionContent,
  getAiConversation,
  listAiConversations,
  sendAiChat,
  updateAiConversation,
} from '@/lib/api';
import type {
  AiChatMessage,
  AiCitation,
  AiConversationSummary,
  AiStatusResponse,
  CollectionSearchResult,
} from '@/lib/types';

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

const PROMPT_PRESETS: ReadonlyArray<{ label: string; prompt: string }> = [
  { label: '요약', prompt: '선택한 문서의 핵심 내용을 5줄 이내로 요약해 주세요.' },
  { label: '보고서 검토', prompt: '선택한 문서를 보고서 관점에서 검토하고, 누락·모호·근거 부족 부분을 항목별로 지적해 주세요.' },
  { label: '위험 식별', prompt: '선택한 문서에서 운영·안전·일정·비용 관점의 위험 요소를 찾아 우선순위와 함께 정리해 주세요.' },
  { label: '비교', prompt: '선택한 문서들의 핵심 항목을 표 형태로 비교하고 차이점을 설명해 주세요.' },
  { label: '핵심 추출', prompt: '선택한 문서에서 의사결정에 필요한 핵심 수치와 결론만 뽑아 주세요.' },
  { label: '후속 질문', prompt: '선택한 문서를 더 깊이 이해하기 위해 확인해야 할 후속 질문 5개를 제안해 주세요.' },
];

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

  const [conversations, setConversations] = useState<AiConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [listError, setListError] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const [previewCitation, setPreviewCitation] = useState<AiCitation | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  async function handlePreview(citation: AiCitation) {
    setPreviewCitation(citation);
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewHtml('');
    try {
      const { content_html } = await fetchCollectionContent(citation.collection, citation.path);
      setPreviewHtml(content_html);
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : '문서를 불러오지 못했습니다.');
    } finally {
      setPreviewLoading(false);
    }
  }
  const [selectedRefs, setSelectedRefs] = useState<Array<{ collection: 'document' | 'civil' | 'nsa'; path: string }>>([]);
  const [scope, setScope] = useState<{ document: boolean; civil: boolean; nsa: boolean }>({
    document: true,
    civil: true,
    nsa: false,
  });
  const [nsaUnlocked, setNsaUnlocked] = useState(false);

  useEffect(() => {
    try {
      setNsaUnlocked(window.localStorage.getItem('aeroone.collection.nsa.unlocked') === '1');
    } catch {
      // localStorage 접근 불가 환경은 nsa 잠금 상태로 둔다.
    }
  }, []);

  const scopeCollections = useMemo<Array<'document' | 'civil' | 'nsa'>>(() => {
    const chosen = (['document', 'civil', 'nsa'] as const).filter((key) => scope[key]);
    return chosen.length > 0 ? chosen : ['document', 'civil'];
  }, [scope]);

  function toggleScope(key: 'document' | 'civil' | 'nsa') {
    if (key === 'nsa' && !nsaUnlocked) return;
    setScope((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function isRefSelected(result: CollectionSearchResult): boolean {
    return selectedRefs.some((ref) => ref.collection === result.collection && ref.path === result.path);
  }

  function toggleRef(result: CollectionSearchResult): void {
    setSelectedRefs((prev) =>
      prev.some((ref) => ref.collection === result.collection && ref.path === result.path)
        ? prev.filter((ref) => !(ref.collection === result.collection && ref.path === result.path))
        : [...prev, { collection: result.collection as 'document' | 'civil' | 'nsa', path: result.path }],
    );
  }

  const refreshConversations = useCallback(async (archived: boolean) => {
    try {
      const payload = await listAiConversations(archived);
      setConversations(payload.conversations);
      setListError('');
    } catch (error) {
      setListError(error instanceof Error ? error.message : '대화 목록을 불러오지 못했습니다.');
    }
  }, []);

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

  useEffect(() => {
    void refreshConversations(includeArchived);
  }, [includeArchived, refreshConversations]);

  const canSubmit = useMemo(() => input.trim().length > 0 && !pending, [input, pending]);

  function startNewConversation() {
    setActiveConversationId(null);
    setMessages([]);
    setCitations([]);
    setPreviewCitation(null);
    setChatError('');
  }

  async function handleSelectConversation(id: number) {
    if (pending) return;
    try {
      const detail = await getAiConversation(id);
      setActiveConversationId(id);
      setMessages(detail.messages.map((message) => ({ role: message.role as AiChatMessage['role'], content: message.content })));
      const lastAssistant = [...detail.messages].reverse().find((message) => message.role === 'assistant');
      setCitations(lastAssistant ? lastAssistant.citations : []);
      setPreviewCitation(null);
      setChatError('');
    } catch (error) {
      setChatError(error instanceof Error ? error.message : '대화를 불러오지 못했습니다.');
    }
  }

  async function handleDeleteConversation(id: number) {
    try {
      await deleteAiConversation(id);
      if (activeConversationId === id) startNewConversation();
      await refreshConversations(includeArchived);
    } catch (error) {
      setListError(error instanceof Error ? error.message : '대화를 삭제하지 못했습니다.');
    }
  }

  async function handleTogglePin(conversation: AiConversationSummary) {
    try {
      await updateAiConversation(conversation.id, { is_pinned: !conversation.is_pinned });
      await refreshConversations(includeArchived);
    } catch (error) {
      setListError(error instanceof Error ? error.message : '대화를 고정하지 못했습니다.');
    }
  }

  async function handleToggleArchive(conversation: AiConversationSummary) {
    try {
      await updateAiConversation(conversation.id, { is_archived: !conversation.is_archived });
      if (!conversation.is_archived && activeConversationId === conversation.id) startNewConversation();
      await refreshConversations(includeArchived);
    } catch (error) {
      setListError(error instanceof Error ? error.message : '대화를 보관하지 못했습니다.');
    }
  }

  async function runChat(baseMessages: AiChatMessage[]) {
    setMessages(baseMessages);
    setPending(true);
    setChatError('');
    setCitations([]);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await sendAiChat(
        {
          messages: baseMessages,
          use_search: useSearch,
          collections: scopeCollections,
          limit: 5,
          conversation_id: activeConversationId,
          selected_refs: selectedRefs,
        },
        { signal: controller.signal },
      );
      setMessages([...baseMessages, response.message]);
      setCitations(response.citations);
      if (response.conversation_id != null) {
        setActiveConversationId(response.conversation_id);
        await refreshConversations(includeArchived);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setChatError('응답을 중지했습니다. 표시상 취소이며, 서버 생성이 끝나면 해당 턴이 저장되어 새로고침 시 다시 보일 수 있습니다.');
      } else {
        setChatError(error instanceof Error ? error.message : 'AI 응답 생성에 실패했습니다.');
      }
    } finally {
      setPending(false);
      abortRef.current = null;
    }
  }

  async function handleChatSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || pending) return;
    setInput('');
    await runChat([...messages, { role: 'user' as const, content }]);
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  async function handleCopy(content: string) {
    try {
      await navigator.clipboard?.writeText(content);
    } catch {
      // 클립보드 접근 불가(권한/비보안 컨텍스트)는 조용히 무시한다.
    }
  }

  async function handleRegenerate() {
    if (pending) return;
    // 마지막 AI 응답을 제거하고 직전 사용자 질문 기준으로 다시 생성한다.
    let base = messages;
    if (base.length > 0 && base[base.length - 1].role === 'assistant') {
      base = base.slice(0, -1);
    }
    if (!base.some((message) => message.role === 'user')) return;
    await runChat(base);
  }

  async function handleSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = searchQuery.trim();
    if (!q || searchPending) return;
    setSearchPending(true);
    setSearchError('');
    setSearchDegraded('');
    try {
      const response = await fetchCollectionSearch({ q, collections: scopeCollections, limit: 20 });
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
    <div className="grid gap-5 xl:grid-cols-[minmax(220px,0.6fr)_minmax(0,1.4fr)_minmax(300px,0.8fr)]">
      <section
        data-testid="ai-conversation-list"
        className="rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm"
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-ink-1">대화</h2>
          <button
            type="button"
            onClick={startNewConversation}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-on transition-colors hover:bg-accent-hover"
          >
            새 대화
          </button>
        </div>
        <label className="mb-3 inline-flex items-center gap-2 text-xs text-ink-2">
          <input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />
          보관함 포함
        </label>
        {listError ? <p role="alert" className="mb-2 rounded bg-warn-soft px-2 py-1 text-xs text-warn">{listError}</p> : null}
        <div className="flex flex-col gap-1">
          {conversations.length === 0 ? (
            <p className="text-sm text-ink-3">저장된 대화가 없습니다. 영속화가 켜져 있으면 대화가 여기에 쌓입니다.</p>
          ) : null}
          {conversations.map((conversation) => (
            <div
              key={conversation.id}
              className={`group flex items-center gap-1 rounded-lg border px-2 py-1.5 text-sm ${
                conversation.id === activeConversationId
                  ? 'border-accent bg-accent-soft'
                  : 'border-line-subtle bg-surface-elevated'
              }`}
            >
              <button
                type="button"
                onClick={() => handleSelectConversation(conversation.id)}
                className="min-w-0 flex-1 truncate text-left text-ink-1"
                title={conversation.title}
              >
                {conversation.is_pinned ? '📌 ' : ''}
                {conversation.title || '제목 없는 대화'}
              </button>
              <button
                type="button"
                aria-label={conversation.is_pinned ? '고정 해제' : '고정'}
                onClick={() => handleTogglePin(conversation)}
                className="shrink-0 rounded px-1 text-xs text-ink-3 hover:text-ink-1"
              >
                {conversation.is_pinned ? '핀해제' : '핀'}
              </button>
              <button
                type="button"
                aria-label={conversation.is_archived ? '보관 해제' : '보관'}
                onClick={() => handleToggleArchive(conversation)}
                className="shrink-0 rounded px-1 text-xs text-ink-3 hover:text-ink-1"
              >
                {conversation.is_archived ? '복원' : '보관'}
              </button>
              <button
                type="button"
                aria-label="삭제"
                onClick={() => handleDeleteConversation(conversation.id)}
                className="shrink-0 rounded px-1 text-xs text-danger hover:underline"
              >
                삭제
              </button>
            </div>
          ))}
        </div>
      </section>

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
              className={`group rounded-lg px-3 py-2 text-sm ${message.role === 'user' ? 'ml-8 bg-accent text-accent-on' : 'mr-8 bg-surface-sunken text-ink-1'}`}
            >
              <div className="mb-1 flex items-center justify-between gap-2 text-xs opacity-70">
                <span>{message.role === 'user' ? '사용자' : 'AI'}</span>
                <button
                  type="button"
                  aria-label="메시지 복사"
                  onClick={() => handleCopy(message.content)}
                  className="rounded px-1 text-[11px] underline-offset-2 hover:underline"
                >
                  복사
                </button>
              </div>
              <div className="whitespace-pre-wrap">{message.content}</div>
            </div>
          ))}
          {pending ? (
            <div data-testid="ai-pending" className="mr-8 rounded-lg bg-surface-sunken px-3 py-2 text-sm text-ink-2">
              gemma4:12b 응답 생성 중… 잠시 기다려 주세요.
            </div>
          ) : null}
        </div>

        {chatError ? <p role="alert" className="mb-3 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{chatError}</p> : null}

        <form onSubmit={handleChatSubmit} className="flex flex-col gap-2">
          <div data-testid="ai-presets" className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-ink-2">프롬프트</span>
            {PROMPT_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => setInput(preset.prompt)}
                className="rounded-full border border-line-subtle px-2.5 py-1 text-xs text-ink-2 hover:bg-surface-sunken"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <textarea
            data-testid="ai-chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="gemma4:12b 에게 질문하세요"
            className="min-h-24 rounded border border-line-subtle bg-surface-elevated px-3 py-2 text-base text-ink-1 placeholder:text-ink-3"
          />
          <div data-testid="ai-scope" className="flex flex-wrap items-center gap-3 text-xs text-ink-2">
            <span className="font-medium">근거 범위</span>
            <label className="inline-flex items-center gap-1">
              <input type="checkbox" checked={scope.document} onChange={() => toggleScope('document')} />
              Document
            </label>
            <label className="inline-flex items-center gap-1">
              <input type="checkbox" checked={scope.civil} onChange={() => toggleScope('civil')} />
              Civil
            </label>
            <label className={`inline-flex items-center gap-1 ${nsaUnlocked ? '' : 'opacity-50'}`} title={nsaUnlocked ? '' : 'NSA 화면에서 잠금 해제 후 사용 가능'}>
              <input type="checkbox" checked={scope.nsa} disabled={!nsaUnlocked} onChange={() => toggleScope('nsa')} />
              NSA{nsaUnlocked ? '' : ' (잠금)'}
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="inline-flex items-center gap-2 text-sm text-ink-2">
              <input type="checkbox" checked={useSearch} onChange={(event) => setUseSearch(event.target.checked)} />
              문서 검색 결과를 답변 근거로 사용(document/civil)
            </label>
            <div className="flex items-center gap-2">
              {pending ? (
                <button
                  type="button"
                  onClick={handleStop}
                  className="rounded-md border border-line-strong px-3 py-2 text-sm font-medium text-ink-1 hover:bg-surface-sunken"
                >
                  중지
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleRegenerate}
                  disabled={messages.length === 0}
                  className="rounded-md border border-line-subtle px-3 py-2 text-sm font-medium text-ink-2 hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
                >
                  재생성
                </button>
              )}
              <button
                type="submit"
                disabled={!canSubmit}
                className="rounded-md bg-accent px-4 py-2 text-base font-medium text-accent-on transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                {pending ? '응답 대기 중' : '보내기'}
              </button>
            </div>
          </div>
          <p className="text-xs text-ink-3">중지는 화면 표시상 취소입니다. 서버 생성이 이미 끝났다면 해당 턴이 저장되어 새로고침 시 다시 보일 수 있습니다.</p>
        </form>
      </section>

      <section className="rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm">
        {citations.length > 0 ? (
          <div data-testid="ai-citations" className="mb-4 rounded-lg border border-line-subtle bg-surface-elevated p-3">
            <h3 className="mb-2 text-sm font-semibold text-ink-1">답변 근거</h3>
            <div className="flex flex-col gap-2">
              {citations.map((citation) => (
                <div key={citationKey(citation)} className="flex items-center justify-between gap-2">
                  <a
                    href={citation.navigation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="min-w-0 flex-1 truncate text-sm text-accent hover:underline"
                    title={`${citation.collection}/${citation.folder ? `${citation.folder}/` : ''}${citation.name}`}
                  >
                    {citation.collection} · {citation.folder ? `${citation.folder}/` : ''}{citation.name}
                  </a>
                  <button
                    type="button"
                    onClick={() => handlePreview(citation)}
                    className="shrink-0 rounded border border-line-subtle px-2 py-0.5 text-xs text-ink-2 hover:bg-surface-sunken"
                  >
                    미리보기
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {previewCitation ? (
          <div data-testid="ai-citation-preview" className="mb-4 rounded-lg border border-accent bg-surface-elevated p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="min-w-0 truncate text-sm font-semibold text-ink-1">미리보기 · {previewCitation.name}</h3>
              <div className="flex shrink-0 items-center gap-2">
                <a href={previewCitation.navigation_url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent hover:underline">새 탭에서 열기</a>
                <button type="button" onClick={() => setPreviewCitation(null)} className="text-xs text-ink-3 hover:text-ink-1">닫기</button>
              </div>
            </div>
            {previewLoading ? <p className="text-sm text-ink-3">문서를 불러오는 중…</p> : null}
            {previewError ? <p role="alert" className="rounded bg-danger-soft px-2 py-1 text-sm text-danger">{previewError}</p> : null}
            {!previewLoading && !previewError ? (
              <iframe
                title={`citation-preview-${previewCitation.name}`}
                sandbox=""
                srcDoc={previewHtml}
                className="h-72 w-full rounded border border-line-subtle bg-white"
              />
            ) : null}
          </div>
        ) : null}

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
        {selectedRefs.length > 0 ? (
          <p className="mb-2 text-xs text-ink-2">
            선택한 문서 {selectedRefs.length}건을 다음 질문의 근거로 사용합니다.{' '}
            <button type="button" onClick={() => setSelectedRefs([])} className="text-accent underline">
              선택 해제
            </button>
          </p>
        ) : null}
        <div data-testid="ai-search-results" className="flex flex-col gap-2">
          {searchResults.map((result) => (
            <div
              key={citationKey(result)}
              className={`flex items-start gap-2 rounded-lg border p-3 transition ${
                isRefSelected(result) ? 'border-accent bg-accent-soft' : 'border-line-subtle bg-surface-elevated'
              }`}
            >
              <input
                type="checkbox"
                className="mt-1"
                aria-label={`근거로 선택: ${result.name}`}
                checked={isRefSelected(result)}
                onChange={() => toggleRef(result)}
              />
              <a href={result.navigation_url} className="min-w-0 flex-1 hover:bg-surface-sunken">
                <div className="text-sm font-semibold text-ink-1">{result.collection} · {result.folder ? `${result.folder}/` : ''}{result.name}</div>
                <div className="mt-1 text-sm text-ink-2">{result.snippet || result.path}</div>
                <div className="mt-1 text-xs text-accent">파일 열기</div>
              </a>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
