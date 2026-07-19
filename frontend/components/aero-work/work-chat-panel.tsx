'use client';

import { ClipboardEvent, FormEvent, useEffect, useRef, useState } from 'react';

import { dedupeAttachmentsByName, isAllowedAttachmentName, readAttachmentFiles, validateAttachments } from '@/components/ai/ai-attachments';
import {
  deleteAeroWorkChatSession,
  fetchAeroWorkChatHistory,
  fetchAeroWorkChatSessions,
  generateAeroWorkHwpx,
  orchestrateAeroWork,
  streamAeroWorkAnswer,
  type AeroWorkChatSession,
  type OrchestrateResult,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { AiAttachment } from '@/lib/types';

// Aero Work F1 업무대화 오케스트레이션 — 대화 한 줄을 일정/문서/지식/도움말로 라우팅한다.
// gongmuwon 정체성인 "대화에서 시작해 실무로 이어지는" 흐름의 프런트. 자유 LLM 대화는
// 아래 AiChatWorkspace(별도)로 이어서 할 수 있다.

const EXAMPLES = [
  '내일 오전 10시 주간회의 일정 등록해줘',
  '이번 주 일정 알려줘',
  '회의 내용을 1페이지 보고서로 작성해줘',
  '지식폴더에서 예산 편성 근거 찾아줘',
  '내일 오후 2시 워크숍 등록하고 그 내용으로 보고서 작성해줘',
];

type LogEntry = { id: number; utterance: string; results: OrchestrateResult[]; routedBy?: 'rule' | 'llm' };

// B3: routed_by 는 응답 최상위가 아니라 결과 항목(OrchestrateResult)마다 온다 — 하나라도
// 'llm' 이면 배지를 표시한다(회귀 고정: work-chat-panel/히스토리 로드가 동일 매핑을 쓴다).
function hasLlmRoutedResult(results: OrchestrateResult[]): boolean {
  return results.some((result) => result.routed_by === 'llm');
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function WorkChatPanel() {
  const [utterance, setUtterance] = useState('');
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AeroWorkChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<number | null>(null);
  const [attachments, setAttachments] = useState<AiAttachment[]>([]);
  const [fileError, setFileError] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadSessions = async () => {
    try {
      const data = await fetchAeroWorkChatSessions();
      setSessions(data.sessions);
      return data.sessions;
    } catch {
      return [];
    }
  };

  const loadHistory = async (sessionId: number) => {
    try {
      const history = await fetchAeroWorkChatHistory(50, sessionId);
      setLog(
        history.items.map((item) => ({
          id: item.id,
          utterance: item.utterance,
          results: item.results,
          routedBy: hasLlmRoutedResult(item.results) ? 'llm' : undefined,
        })),
      );
    } catch {
      setLog([]);
    }
  };

  const selectSession = (sessionId: number) => {
    setActiveSession(sessionId);
    void loadHistory(sessionId);
  };

  const newSession = () => {
    setActiveSession(null);
    setLog([]);
  };

  useEffect(() => {
    let alive = true;
    void (async () => {
      const list = await loadSessions();
      if (alive && list.length > 0) {
        setActiveSession(list[0].id);
        await loadHistory(list[0].id);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (value: string) => {
    const text = value.trim();
    if (!text) {
      return;
    }
    const attachmentError = validateAttachments(attachments);
    if (attachmentError) {
      setError(attachmentError);
      return;
    }
    // B2: 첨부가 있으면 SSE 스트림 경로 대신 orchestrateAeroWork(synthesize:true, attachments
    // 동반) 비스트리밍 경로로 분기한다 — 스트리밍은 첨부를 지원하지 않는 계약이다(첨부 없이
    // 조립된 지식 합성 프롬프트만 스트리밍할 수 있다). 첨부가 없으면 기존 스트림 경로를 그대로 쓴다.
    const pendingAttachments = attachments;
    const hasAttachments = pendingAttachments.length > 0;
    setBusy(true);
    setError(null);
    try {
      const response = await orchestrateAeroWork(text, getCsrfCookie(), activeSession, {
        synthesize: hasAttachments,
        attachments: hasAttachments ? pendingAttachments : undefined,
      });
      setActiveSession(response.session_id);
      const entryId = Date.now();
      setLog((prev) => [
        { id: entryId, utterance: text, results: response.results, routedBy: hasLlmRoutedResult(response.results) ? 'llm' : undefined },
        ...prev,
      ]);
      setUtterance('');
      setAttachments([]);
      setFileError('');
      void loadSessions();

      if (hasAttachments) {
        // 첨부 요청은 synthesize:true 로 이미 완성된 답변을 받았다 — 스트리밍/재시도가 불필요하다.
        return;
      }

      response.results.forEach((result, resultIndex) => {
        if (result.kind !== 'knowledge' || result.hits.length === 0) {
          return;
        }
        const setResultAnswer = (updater: (previous: string | undefined) => string | undefined) => {
          setLog((prev) =>
            prev.map((entry) =>
              entry.id === entryId
                ? {
                    ...entry,
                    results: entry.results.map((r, i) => (i === resultIndex ? { ...r, answer: updater(r.answer) } : r)),
                  }
                : entry,
            ),
          );
        };
        const setResultHits = (hits: OrchestrateResult['hits']) => {
          setLog((prev) =>
            prev.map((entry) =>
              entry.id === entryId
                ? {
                    ...entry,
                    results: entry.results.map((r, i) => (i === resultIndex ? { ...r, hits } : r)),
                  }
                : entry,
            ),
          );
        };
        const retryWithOrchestrate = () => {
          // M1: 스트림 실패 시 비스트리밍 orchestrateAeroWork(synthesize:true) 로 재요청해
          // 그 지식 답변만 추출해 반영한다(B2: 원 요청의 첨부가 있었다면 재시도에도 동일하게
          // 동반한다). 재요청은 세션에 새 대화 메시지를 추가하는 부작용이 있다(세션 중복 기록을
          // 피하는 전용 유틸은 없음 — 단순성을 우선해 허용). 재요청마저 실패하면 답변 없이
          // 근거(hits)만 유지한다.
          void orchestrateAeroWork(text, getCsrfCookie(), response.session_id, {
            synthesize: true,
            attachments: hasAttachments ? pendingAttachments : undefined,
          })
            .then((fallback) => {
              const knowledgeResult = fallback.results.find((r) => r.kind === 'knowledge');
              setResultAnswer(() => knowledgeResult?.answer || undefined);
            })
            .catch(() => setResultAnswer(() => undefined));
        };
        // 지식 답변 스트림 호출 자체(네트워크 예외 등)도 try/catch 로 감싸 실패 시 동일하게
        // 비스트리밍 재요청으로 폴백한다(onError 콜백은 SSE error 프레임 수신 시에만 불린다).
        streamAeroWorkAnswer({ query: text, top_k: 5 }, getCsrfCookie(), {
          // top_k 를 오케스트레이션과 동일하게 고정하고, 스트림이 되돌려주는 hits 로 엔트리의
          // 근거를 교체해 번호-근거(각주)가 실제 스트리밍 답변과 항상 일치하도록 한다.
          onHits: (hits) => setResultHits(hits),
          onDelta: (chunk) => setResultAnswer((previous) => (previous ?? '') + chunk),
          onDone: (answer) => setResultAnswer(() => answer),
          onError: retryWithOrchestrate,
        }).catch(retryWithOrchestrate);
      });
    } catch {
      setError('처리 실패. 로그인 상태를 확인할 것.');
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(utterance);
  };
  const addFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (list.length === 0) return;
    const accepted = list.filter((file) => isAllowedAttachmentName(file.name));
    const rejected = list.filter((file) => !isAllowedAttachmentName(file.name));
    setFileError(rejected.length > 0 ? `${rejected.map((file) => file.name).join(', ')}: .md/.txt/.csv 파일만 첨부할 수 있습니다.` : '');
    if (accepted.length === 0) return;
    try {
      const read = await readAttachmentFiles(accepted);
      setAttachments((prev) => dedupeAttachmentsByName([...prev, ...read]));
    } catch (error) {
      setFileError(error instanceof Error ? error.message : '파일을 읽지 못했습니다.');
    }
  };

  const removeAttachment = (name: string) => {
    setAttachments((prev) => prev.filter((attachment) => attachment.name !== name));
  };

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const files = Array.from(event.clipboardData?.files ?? []);
    if (files.length === 0) return;
    event.preventDefault();
    void addFiles(files);
  };

  const handleDownload = async (doc: { format: string; title: string; content: string }) => {
    setError(null);
    try {
      const blob = await generateAeroWorkHwpx({ title: doc.title, body: doc.content, format: doc.format }, getCsrfCookie());
      downloadBlob(blob, `${doc.title || '무제'}.hwpx`);
    } catch {
      setError('HWPX 생성 실패.');
    }
  };

  return (
    <div className="space-y-4">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-1">
        <button
          type="button"
          onClick={newSession}
          className={`rounded-full px-3 py-1 text-xs font-medium ${activeSession === null ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2 hover:bg-accent-soft'}`}
        >
          + 새 세션
        </button>
        {sessions.map((session) => (
          <span key={session.id} className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs ${activeSession === session.id ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2'}`}>
            <button type="button" onClick={() => selectSession(session.id)} className="max-w-[160px] truncate">{session.title}</button>
            <button
              type="button"
              aria-label="세션 삭제"
              onClick={() => {
                void deleteAeroWorkChatSession(session.id, getCsrfCookie())
                  .then(async () => {
                    if (activeSession === session.id) {
                      newSession();
                    }
                    await loadSessions();
                  })
                  .catch(() => setError('세션 삭제 실패.'));
              }}
              className="opacity-60 hover:opacity-100"
            >
              ×
            </button>
          </span>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <div className="flex gap-2">
          <input
            value={utterance}
            onChange={(event) => setUtterance(event.target.value)}
            onPaste={handlePaste}
            placeholder="예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘"
            className="flex-1 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="파일 첨부"
            className="inline-flex items-center gap-1.5 rounded-lg border border-line-subtle px-2.5 py-2 text-xs font-medium text-ink-2 hover:bg-surface-sunken"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-3.5 w-3.5" aria-hidden>
              <path d="M13.5 5.5 7.2 11.8a2.2 2.2 0 0 0 3.1 3.1l6-6a3.8 3.8 0 0 0-5.4-5.4l-6 6a5.4 5.4 0 0 0 7.6 7.6l5.2-5.2" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".md,.txt,.csv,text/markdown,text/plain,text/csv"
            className="hidden"
            aria-label="첨부 파일 선택"
            onChange={(event) => {
              if (event.target.files?.length) void addFiles(event.target.files);
              event.target.value = '';
            }}
          />
          <button
            type="submit"
            disabled={busy || !utterance.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {busy ? '처리 중…' : '보내기'}
          </button>
        </div>
        {attachments.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {attachments.map((attachment) => (
              <span
                key={attachment.name}
                className="inline-flex items-center gap-1.5 rounded-full border border-line-subtle bg-surface-elevated px-2.5 py-1 text-xs text-ink-2"
              >
                {attachment.name}
                <button
                  type="button"
                  aria-label={`첨부 제거: ${attachment.name}`}
                  onClick={() => removeAttachment(attachment.name)}
                  className="text-ink-3 hover:text-danger"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <p className="mt-1 text-xs text-ink-3">
          .md/.txt/.csv 파일을 첨부하거나 붙여넣으세요(최대 5개, 합계 200,000자 이하).
        </p>
        {fileError ? (
          <p role="alert" className="mt-1 rounded bg-warn-soft px-2 py-1 text-xs text-warn">{fileError}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap gap-1">
          <span className="text-xs text-ink-3">이렇게 말해보세요:</span>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => void submit(example)}
              className="rounded-full bg-surface-sunken px-2 py-0.5 text-[11px] text-ink-2 hover:bg-accent-soft hover:text-accent"
            >
              {example}
            </button>
          ))}
        </div>
      </form>

      {log.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-subtle bg-surface-base px-3 py-4 text-sm text-ink-3">
          대화 한 줄로 일정 등록·문서작성·지식 검색을 이어서 할 수 있습니다.
        </p>
      ) : (
        <ul className="space-y-3">
          {log.map((entry) => (
            <li key={entry.id} className="space-y-2">
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-tr-sm bg-accent px-3 py-2 text-sm text-accent-on">{entry.utterance}</p>
              {entry.routedBy === 'llm' ? (
                <span className="inline-flex w-fit items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
                  AI 보조 분류
                </span>
              ) : null}
              {entry.results.map((result, index) => (
                <div key={index} className="max-w-[92%] rounded-2xl rounded-tl-sm border border-line-subtle bg-surface-base px-3 py-2">
                  <p className="text-sm text-ink-1">{result.summary}</p>

                  {result.events.length > 0 ? (
                    <ul className="mt-2 space-y-1">
                      {result.events.map((event) => (
                        <li key={event.id} className="flex gap-2 text-xs text-ink-2">
                          <span className="font-medium text-ink-1">
                            {event.all_day ? event.starts_at.slice(5, 10) : `${event.starts_at.slice(5, 10)} ${event.starts_at.slice(11, 16)}`}
                          </span>
                          <span className="truncate">{event.title}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {result.answer ? (
                    <p className="mt-2 whitespace-pre-wrap rounded-lg bg-accent-soft px-3 py-2 text-sm leading-relaxed text-ink-1">{result.answer}</p>
                  ) : null}

                  {result.hits.length > 0 ? (
                    <ul className="mt-2 space-y-1">
                      {result.hits.map((hit, hitIndex) => (
                        <li key={hitIndex} className="rounded-lg border border-line-subtle bg-surface-raised px-2 py-1">
                          <div className="flex items-center gap-2 text-[11px] text-ink-3">
                            <span className="font-medium text-ink-2">{hit.folder_name}</span>
                            <span className="font-mono">{hit.rel_path}</span>
                            {hit.is_latest ? <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">최신본</span> : null}
                            <span className="ml-auto text-accent">유사도 {hit.score.toFixed(3)}</span>
                          </div>
                          <p className="mt-0.5 line-clamp-2 text-xs text-ink-1">{hit.content}</p>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  {result.document ? (
                    <button
                      type="button"
                      onClick={() => void handleDownload(result.document!)}
                      className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-on"
                    >
                      HWPX 생성·다운로드
                    </button>
                  ) : null}
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
