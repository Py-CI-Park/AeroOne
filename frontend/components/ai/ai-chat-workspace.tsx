'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  deleteAiConversation,
  fetchClientSession,
  fetchAiStatus,
  fetchCollectionSearch,
  fetchCollectionContent,
  getAiConversation,
  listAiConversations,
  streamAiChat,
  updateAiConversation,
} from '@/lib/api';
import type {
  AiAttachment,
  AiCitation,
  AiConversationSummary,
  AiStatusResponse,
  CollectionSearchResult,
} from '@/lib/types';

import { validateAttachments } from '@/components/ai/ai-attachments';
import { AiCitationPanel } from '@/components/ai/ai-citation-panel';
import { AiComposer } from '@/components/ai/ai-composer';
import { AiConversationList } from '@/components/ai/ai-conversation-list';
import type { AiLocalMessage } from '@/components/ai/ai-message-list';
import { AiMessageList } from '@/components/ai/ai-message-list';
import { AiSearchPanel } from '@/components/ai/ai-search-panel';

const DEFAULT_STATUS: AiStatusResponse = {
  enabled: true,
  base_url: '',
  model: '',
  reachable: false,
  model_available: false,
  status: 'unavailable',
  detail: '상태를 확인하는 중입니다.',
};

const AI_DISPLAY_NAME = 'AeroAI';

function statusLabel(status: AiStatusResponse): string {
  if (status.status === 'ok') return `${AI_DISPLAY_NAME} 준비됨`;
  if (status.status === 'disabled') return 'AI 기능 비활성화';
  if (status.status === 'model_missing') return 'AI 모델을 사용할 수 없습니다';
  return 'AI 서버 연결 불가';
}

export function AiChatWorkspace() {
  const [status, setStatus] = useState<AiStatusResponse>(DEFAULT_STATUS);
  const [statusError, setStatusError] = useState('');
  const [messages, setMessages] = useState<AiLocalMessage[]>([]);
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
  const [attachments, setAttachments] = useState<AiAttachment[]>([]);

  const [conversations, setConversations] = useState<AiConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [listError, setListError] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const [previewCitation, setPreviewCitation] = useState<AiCitation | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [previewExpanded, setPreviewExpanded] = useState(false);

  async function handlePreview(citation: AiCitation) {
    setPreviewCitation(citation);
    setPreviewLoading(true);
    setPreviewError('');
    setPreviewHtml('');
    setPreviewExpanded(false);
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
    // NSA scope availability is derived from the shared ClientSession's can_view_nsa flag,
    // the single UI authority for NSA visibility (backend enforcement in can_read_collection
    // remains authoritative and drops unauthorized NSA scope/refs regardless).
    let cancelled = false;
    void fetchClientSession()
      .then((session) => {
        if (cancelled) return;
        setNsaUnlocked(session.can_view_nsa === true);
      })
      .catch(() => {
        // 세션 조회 실패 시 NSA 는 비활성(권한 없음) 상태로 둔다.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const scopeCollections = useMemo<Array<'document' | 'civil' | 'nsa'>>(
    () => (['document', 'civil', 'nsa'] as const).filter((key) => scope[key]),
    [scope],
  );

  const activeScopeCount = scopeCollections.length;

  function toggleScope(key: 'document' | 'civil' | 'nsa') {
    if (key === 'nsa' && !nsaUnlocked) return;
    setScope((prev) => {
      if (prev[key] && activeScopeCount <= 1) return prev;
      return { ...prev, [key]: !prev[key] };
    });
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

  const attachmentError = useMemo(() => validateAttachments(attachments), [attachments]);
  const canSubmit = useMemo(
    () => input.trim().length > 0 && !pending && !attachmentError,
    [input, pending, attachmentError],
  );

  function startNewConversation() {
    setActiveConversationId(null);
    setMessages([]);
    setCitations([]);
    setPreviewCitation(null);
    setPreviewExpanded(false);
    setChatError('');
  }

  async function handleSelectConversation(id: number) {
    if (pending) return;
    try {
      const detail = await getAiConversation(id);
      setActiveConversationId(id);
      setMessages(detail.messages.map((message) => ({ role: message.role as AiLocalMessage['role'], content: message.content })));
      const lastAssistant = [...detail.messages].reverse().find((message) => message.role === 'assistant');
      setCitations(lastAssistant ? lastAssistant.citations : []);
      setPreviewCitation(null);
      setPreviewExpanded(false);
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

  async function runChat(baseMessages: AiLocalMessage[]) {
    setMessages(baseMessages);
    setPending(true);
    setChatError('');
    setCitations([]);
    const controller = new AbortController();
    abortRef.current = controller;
    let accumulated = '';
    let assistantStarted = false;
    let doneReceived = false;
    try {
      await streamAiChat(
        {
          messages: baseMessages.map(({ role, content }) => ({ role, content })),
          use_search: useSearch,
          collections: scopeCollections,
          limit: 5,
          conversation_id: activeConversationId,
          selected_refs: selectedRefs,
          attachments,
        },
        controller.signal,
        {
          onCitations: (nextCitations) => setCitations(nextCitations),
          onDelta: (chunk) => {
            accumulated += chunk;
            setMessages((prev) => {
              if (!assistantStarted) {
                assistantStarted = true;
                return [...prev, { role: 'assistant' as const, content: accumulated }];
              }
              const next = [...prev];
              next[next.length - 1] = { role: 'assistant', content: accumulated };
              return next;
            });
          },
          onDone: (payload) => {
            doneReceived = true;
            if (payload.persist_error) {
              // 답변은 전달됐지만 저장 실패 — 답변을 지우지 않고 경고만 띄운다.
              setChatError('답변은 표시됐지만 대화 저장에 실패했습니다. 새로고침 시 이 턴이 남지 않을 수 있습니다.');
            }
            if (payload.conversation_id != null) {
              setActiveConversationId(payload.conversation_id);
              void refreshConversations(includeArchived);
            }
          },
          onError: (detail) => {
            setChatError(detail || 'AI 응답 생성에 실패했습니다.');
          },
        },
      );
      if (!doneReceived && !controller.signal.aborted) {
        // done/에러 프레임 없이 스트림이 조용히 끝난 경우(백엔드 이상): 부분 답변이
        // 표시됐더라도 미완결·미저장임을 알린다.
        setChatError((prev) => prev || (assistantStarted
          ? '응답 스트림이 완결되지 않았습니다. 표시된 답변은 저장되지 않았을 수 있습니다.'
          : 'AI 응답을 받지 못했습니다.'));
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setChatError('응답을 중지했습니다. 표시상 취소이며, 서버 생성이 끝나면 해당 턴이 저장되어 새로고침 시 다시 보일 수 있습니다.');
        setMessages((prev) => {
          if (prev.length === 0) return prev;
          const last = prev[prev.length - 1];
          if (last.role !== 'assistant') return prev;
          const next = [...prev];
          next[next.length - 1] = { ...last, interrupted: true };
          return next;
        });
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
    if (!content || pending || attachmentError) return;
    setInput('');
    setAttachments([]);
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
    <div className="grid min-h-[calc(100dvh-176px)] gap-5 xl:grid-cols-[minmax(220px,0.6fr)_minmax(0,1.4fr)_minmax(320px,0.85fr)]">
      <AiConversationList
        conversations={conversations}
        activeConversationId={activeConversationId}
        includeArchived={includeArchived}
        onIncludeArchivedChange={setIncludeArchived}
        listError={listError}
        onNewConversation={startNewConversation}
        onSelectConversation={handleSelectConversation}
        onTogglePin={handleTogglePin}
        onToggleArchive={handleToggleArchive}
        onDeleteConversation={handleDeleteConversation}
      />

      <section className="flex max-h-[calc(100dvh-176px)] min-h-0 flex-col rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-ink-1">AeroAI</h2>
            <p className="text-sm text-ink-3">사내 폐쇄망 문서를 근거로 답하는 AI 어시스턴트입니다.</p>
          </div>
          <div data-testid="ai-status" className="rounded-full bg-surface-sunken px-3 py-1 text-xs text-ink-2">
            {statusLabel(status)}
          </div>
        </div>

        {statusError ? <p className="mb-3 rounded bg-warn-soft px-3 py-2 text-sm text-warn">{statusError}</p> : null}
        {status.status !== 'ok' ? (
          <p data-testid="ai-degraded" className="mb-3 rounded bg-warn-soft px-3 py-2 text-sm text-warn">
            {status.status === 'model_missing' ? 'AI 모델을 사용할 수 없습니다. 관리자에게 문의하세요.' : 'AI 기능을 일시적으로 사용할 수 없습니다. 관리자에게 문의하세요.'}
          </p>
        ) : null}

        <AiMessageList messages={messages} pending={pending} onCopy={handleCopy} />

        {chatError ? <p role="alert" className="mb-3 rounded bg-danger-soft px-3 py-2 text-sm text-danger">{chatError}</p> : null}

        <AiComposer
          input={input}
          onInputChange={setInput}
          onSubmit={handleChatSubmit}
          canSubmit={canSubmit}
          pending={pending}
          onStop={handleStop}
          onRegenerate={handleRegenerate}
          hasMessages={messages.length > 0}
          useSearch={useSearch}
          onToggleSearch={setUseSearch}
          scope={scope}
          onToggleScope={toggleScope}
          nsaUnlocked={nsaUnlocked}
          attachments={attachments}
          onAttachmentsChange={setAttachments}
          attachmentError={attachmentError}
        />
      </section>

      <section className="flex max-h-[calc(100dvh-176px)] min-h-0 flex-col overflow-y-auto overscroll-contain rounded-2xl border border-line-subtle bg-surface-raised p-4 shadow-sm">
        <AiCitationPanel
          citations={citations}
          onPreview={handlePreview}
          previewCitation={previewCitation}
          previewHtml={previewHtml}
          previewLoading={previewLoading}
          previewError={previewError}
          previewExpanded={previewExpanded}
          onTogglePreviewExpanded={() => setPreviewExpanded((expanded) => !expanded)}
          onClosePreview={() => {
            setPreviewCitation(null);
            setPreviewExpanded(false);
          }}
        />

        <AiSearchPanel
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          onSearchSubmit={handleSearchSubmit}
          searchPending={searchPending}
          searchError={searchError}
          searchDegraded={searchDegraded}
          searchResults={searchResults}
          selectedRefs={selectedRefs}
          onClearSelectedRefs={() => setSelectedRefs([])}
          isRefSelected={isRefSelected}
          onToggleRef={toggleRef}
        />
      </section>
    </div>
  );
}
