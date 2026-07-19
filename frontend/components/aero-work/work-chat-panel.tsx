'use client';

import { FormEvent, useEffect, useState } from 'react';

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

type LogEntry = { id: number; utterance: string; results: OrchestrateResult[] };

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
      setLog(history.items.map((item) => ({ id: item.id, utterance: item.utterance, results: item.results })));
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
    setBusy(true);
    setError(null);
    try {
      const response = await orchestrateAeroWork(text, getCsrfCookie(), activeSession, { synthesize: false });
      setActiveSession(response.session_id);
      const entryId = Date.now();
      setLog((prev) => [{ id: entryId, utterance: text, results: response.results }, ...prev]);
      setUtterance('');
      void loadSessions();

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
        void streamAeroWorkAnswer({ query: text }, getCsrfCookie(), {
          onDelta: (chunk) => setResultAnswer((previous) => (previous ?? '') + chunk),
          onDone: (answer) => setResultAnswer(() => answer),
          onError: () => setResultAnswer(() => undefined),
        });
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
            placeholder="예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘"
            className="flex-1 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <button
            type="submit"
            disabled={busy || !utterance.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {busy ? '처리 중…' : '보내기'}
          </button>
        </div>
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
