'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';

import {
  approveAeroWorkDocument,
  composeAeroWorkDocument,
  deleteSavedAeroWorkDocument,
  downloadSavedAeroWorkDocument,
  fetchSavedAeroWorkDocuments,
  generateAeroWorkHwpx,
  previewAeroWorkDocument,
  saveAeroWorkDocumentRequest,
  streamAeroWorkCompose,
  type SavedAeroWorkDocument,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work P3 문서작성 — 제목 + 본문(한 줄=한 문단)을 즉시 미리보고 HWPX(한글, OWPML) 로
// 내려받는다. OWPML 구조 유효성은 백엔드 테스트로 보장하지만, 한컴 오피스 실제 서식/호환은
// 실기(한컴 설치 PC) 확인이 필요한 실험적 기능이라 화면에 명시한다. 임의형식 슬롯 채움은 후속.
//
// G005 종이(양식) 미리보기 — 서버가 gongmuwon §5.3 양식 5종 위계를 반영해 만든
// self-contained HTML 조각(previewAeroWorkDocument)만 A4 비율 종이 프레임 안에
// dangerouslySetInnerHTML 로 렌더한다. 사용자 입력을 프런트에서 직접 HTML 로 주입하는 것은
// 금지 — 서버가 텍스트를 escape 해 만든 HTML 만 신뢰한다. 실제 문서 소프트웨어 수준의
// WASM(한글/오피스 엔진) 정밀 렌더는 범위 밖이며 후속 작업으로 남긴다.

const PREVIEW_DEBOUNCE_MS = 500;

export function DocumentPanel() {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [format, setFormat] = useState('onepage');
  const [busy, setBusy] = useState(false);
  const [composing, setComposing] = useState(false);
  const [savedDocs, setSavedDocs] = useState<SavedAeroWorkDocument[]>([]);

  const [paperPreviewOn, setPaperPreviewOn] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [instruction, setInstruction] = useState('');
  const [revising, setRevising] = useState(false);
  // M3: 재생성 문단 수가 이전의 50% 미만으로 급감하면 즉시 교체하지 않고 인라인 확인을 거친다
  // (window.confirm 대신 화면 안 확인 버튼 — 테스트 가능하고 화면 흐름을 벗어나지 않는다).
  const [pendingRevision, setPendingRevision] = useState<
    { paragraphs: string[]; previousCount: number; truncated: boolean } | null
  >(null);

  const loadSaved = async () => {
    try {
      const data = await fetchSavedAeroWorkDocuments();
      setSavedDocs(data.documents);
    } catch {
      setSavedDocs([]);
    }
  };

  useEffect(() => {
    void loadSaved();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const paragraphs = useMemo(
    () => body.split('\n').map((line) => line.trim()).filter(Boolean),
    [body],
  );

  // 종이 미리보기가 켜져 있는 동안 제목/본문/양식 변경을 500ms 디바운스로 반영한다.
  // M1: 세대 토큰으로 늦게 도착한 이전 요청 응답을 폐기한다 — 빠른 연속 변경(또는 토글 off)
  // 이후 먼저 시작된 느린 응답이 나중에 도착해 최신 화면을 덮어쓰는 경합을 막는다.
  const previewGenerationRef = useRef(0);
  useEffect(() => {
    previewGenerationRef.current += 1;
    const generation = previewGenerationRef.current;
    if (!paperPreviewOn) {
      return;
    }
    const timer = setTimeout(() => {
      void (async () => {
        setPreviewLoading(true);
        setPreviewError(null);
        try {
          const result = await previewAeroWorkDocument(
            { format_id: format, title: title.trim() || '무제', paragraphs },
            getCsrfCookie(),
          );
          if (previewGenerationRef.current !== generation) {
            return; // 이 요청보다 나중 요청이 이미 시작됨(또는 토글 off) — 화면을 덮어쓰지 않는다.
          }
          setPreviewHtml(result.html);
        } catch {
          if (previewGenerationRef.current !== generation) {
            return;
          }
          setPreviewError('미리보기 생성 실패.');
        } finally {
          if (previewGenerationRef.current === generation) {
            setPreviewLoading(false);
          }
        }
      })();
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [paperPreviewOn, title, format, paragraphs]);

  const handleGenerate = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() && !body.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const blob = await generateAeroWorkHwpx({ title: title.trim(), body, format }, getCsrfCookie());
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${title.trim() || '무제'}.hwpx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setDone('HWPX 파일을 내려받았음.');
    } catch {
      setError('HWPX 생성 실패. 로그인 상태를 확인할 것.');
    } finally {
      setBusy(false);
    }
  };

  // M3: 문단 수 급감(이전의 50% 미만) 시 즉시 교체하지 않고 확인 대기 상태로 돌린다.
  const applyRevisionResult = (revisedParagraphs: string[], previousCount: number, truncated: boolean) => {
    const droppedSharply = previousCount > 0 && revisedParagraphs.length < previousCount * 0.5;
    if (droppedSharply) {
      setPendingRevision({ paragraphs: revisedParagraphs, previousCount, truncated });
      return;
    }
    setBody(revisedParagraphs.join('\n'));
    setInstruction('');
    setDone(
      truncated
        ? `AI가 지시를 반영해 ${revisedParagraphs.length}문장으로 재생성했음. (일부만 반영됨: 지시/이전 본문이 길어 일부만 반영되었습니다.)`
        : `AI가 지시를 반영해 ${revisedParagraphs.length}문장으로 재생성했음.`,
    );
  };

  const confirmPendingRevision = () => {
    if (!pendingRevision) {
      return;
    }
    setBody(pendingRevision.paragraphs.join('\n'));
    setInstruction('');
    setDone(
      pendingRevision.truncated
        ? `AI가 지시를 반영해 ${pendingRevision.paragraphs.length}문장으로 재생성했음. (일부만 반영됨: 지시/이전 본문이 길어 일부만 반영되었습니다.)`
        : `AI가 지시를 반영해 ${pendingRevision.paragraphs.length}문장으로 재생성했음.`,
    );
    setPendingRevision(null);
  };

  const cancelPendingRevision = () => setPendingRevision(null);

  const handleRevise = async () => {
    if (!instruction.trim()) {
      setError('수정 지시를 입력하세요.');
      return;
    }
    setRevising(true);
    setError(null);
    setDone(null);
    setPendingRevision(null);
    const currentInstruction = instruction.trim();
    const previousParagraphs = paragraphs;
    let fallbackPending: Promise<void> | undefined;
    try {
      await streamAeroWorkCompose(
        { title: title.trim(), instruction: currentInstruction, format, previous_paragraphs: previousParagraphs },
        getCsrfCookie(),
        {
          onDelta: () => {
            // 수정 지시 재생성은 완료본만 반영한다(부분 델타로 본문을 덮어쓰지 않음).
          },
          onDone: (revised, truncated) => {
            applyRevisionResult(revised, previousParagraphs.length, truncated ?? false);
          },
          onError: () => {
            fallbackPending = (async () => {
              try {
                const result = await composeAeroWorkDocument(
                  { title: title.trim(), instruction: currentInstruction, format, previous_paragraphs: previousParagraphs },
                  getCsrfCookie(),
                );
                applyRevisionResult(result.paragraphs, previousParagraphs.length, result.truncated);
              } catch {
                setError('수정 지시 반영 실패. 로컬 AI(또는 OpenAI 호환 연결) 상태를 확인할 것.');
              }
            })();
          },
        },
      );
      if (fallbackPending) {
        await fallbackPending;
      }
    } catch {
      setError('수정 지시 반영 실패. 로컬 AI(또는 OpenAI 호환 연결) 상태를 확인할 것.');
    } finally {
      setRevising(false);
    }
  };

  return (
    <form onSubmit={handleGenerate} className="mt-4 space-y-4">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}
      {done ? (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600">{done}</p>
      ) : null}

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <div className="mb-2 flex flex-wrap gap-1">
          {[
            ['onepage', '1페이지'],
            ['official', '시행문'],
            ['full', '풀버전'],
            ['email', '이메일'],
            ['freeform', '임의형식'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setFormat(value)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                format === value ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2 hover:bg-accent-soft'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="문서 제목"
          className="w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm font-medium text-ink-1"
        />
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="본문을 입력하세요. 한 줄이 한 문단이 됩니다."
          rows={10}
          readOnly={composing || revising}
          className="mt-2 w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm leading-relaxed text-ink-1"
        />
        <div className="mt-3 flex items-center gap-2">
          <button
            type="submit"
            disabled={busy || revising || (!title.trim() && !body.trim())}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {busy ? '생성 중…' : 'HWPX 생성·다운로드'}
          </button>
          <button
            type="button"
            onClick={() => {
              void (async () => {
                if (!body.trim()) {
                  setError('지시(개요)를 본문 칸에 먼저 적으세요. AI가 개조식 내용으로 확장합니다.');
                  return;
                }
                const genInstruction = body;
                setComposing(true);
                setError(null);
                setDone(null);
                setBody('');
                let fallbackPending: Promise<void> | undefined;
                try {
                  await streamAeroWorkCompose(
                    { title: title.trim(), instruction: genInstruction, format },
                    getCsrfCookie(),
                    {
                      onDelta: (chunk) => setBody((prev) => prev + chunk),
                      onDone: (composedParagraphs) => {
                        setBody(composedParagraphs.join('\n'));
                        setDone(`AI가 ${composedParagraphs.length}문장으로 확장했음. 검토·수정 후 HWPX로 내려받으세요.`);
                      },
                      onError: () => {
                        // 스트리밍 실패 시 기존 비스트리밍 composeAeroWorkDocument 로 폴백한다.
                        fallbackPending = (async () => {
                          try {
                            const result = await composeAeroWorkDocument(
                              { title: title.trim(), instruction: genInstruction, format },
                              getCsrfCookie(),
                            );
                            setBody(result.paragraphs.join('\n'));
                            setDone(`AI가 ${result.paragraphs.length}문장으로 확장했음. 검토·수정 후 HWPX로 내려받으세요.`);
                          } catch {
                            setBody(genInstruction);
                            setError('AI 내용 생성 실패. 로컬 AI(또는 OpenAI 호환 연결) 상태를 확인할 것.');
                          }
                        })();
                      },
                    },
                  );
                  if (fallbackPending) {
                    await fallbackPending;
                  }
                } catch {
                  setBody(genInstruction);
                  setError('AI 내용 생성 실패. 로컬 AI(또는 OpenAI 호환 연결) 상태를 확인할 것.');
                } finally {
                  setComposing(false);
                }
              })();
            }}
            disabled={composing || busy || revising || !body.trim()}
            className="rounded-lg border border-accent bg-accent-soft px-4 py-2 text-sm font-medium text-accent disabled:opacity-50"
          >
            {composing ? 'AI 생성 중…' : '🪄 AI로 내용 생성'}
          </button>
          <span className="text-xs text-ink-3">{paragraphs.length}개 문단</span>
        </div>
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-ink-1">미리보기</p>
          <label className="flex items-center gap-2 text-xs font-medium text-ink-2">
            <input
              type="checkbox"
              checked={paperPreviewOn}
              onChange={(event) => setPaperPreviewOn(event.target.checked)}
            />
            종이 미리보기
          </label>
        </div>

        {paperPreviewOn ? (
          <div className="mt-2">
            {previewError ? (
              <p className="mb-2 text-xs text-rose-600">{previewError}</p>
            ) : null}
            {previewLoading ? <p className="mb-2 text-xs text-ink-3">미리보기 생성 중…</p> : null}
            {/* A4 비율(210:297) 종이 프레임 — 회색 배경 위 흰 종이 + 그림자. HTML 은 서버가
                생성한 self-contained 조각만 신뢰하며, dangerouslySetInnerHTML 에 사용자 텍스트를
                직접 넣지 않는다(previewAeroWorkDocument 응답만 사용). WASM 정밀 렌더는 후속. */}
            <div className="rounded-lg bg-surface-sunken p-4">
              <div
                className="mx-auto aspect-[210/297] w-full max-w-[420px] overflow-auto bg-white p-6 text-black shadow-lg"
                data-testid="paper-preview"
                // eslint-disable-next-line react/no-danger
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            </div>

            <div className="mt-3 rounded-lg border border-line-subtle bg-surface-raised p-3">
              <p className="text-xs font-semibold text-ink-2">수정 지시</p>
              <textarea
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="예: 3번째 문단을 더 구체적으로 수정해줘"
                rows={2}
                className="mt-1 w-full rounded-lg border border-line-subtle bg-surface-base px-3 py-2 text-sm text-ink-1"
              />
              <button
                type="button"
                onClick={() => void handleRevise()}
                disabled={revising || composing || !instruction.trim()}
                className="mt-2 rounded-lg border border-accent bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent disabled:opacity-50"
              >
                {revising ? '반영 중…' : '지시 반영 재생성'}
              </button>
              {pendingRevision ? (
                <div
                  data-testid="revision-drop-confirm"
                  className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700"
                >
                  <p>
                    문단 수가 {pendingRevision.previousCount}개에서 {pendingRevision.paragraphs.length}개로
                    크게 줄었습니다. 교체할까요?
                  </p>
                  <div className="mt-1.5 flex gap-2">
                    <button
                      type="button"
                      onClick={confirmPendingRevision}
                      className="rounded px-2 py-0.5 text-[11px] font-medium text-accent hover:bg-accent-soft"
                    >
                      교체
                    </button>
                    <button
                      type="button"
                      onClick={cancelPendingRevision}
                      className="rounded px-2 py-0.5 text-[11px] font-medium text-ink-2 hover:bg-surface-sunken"
                    >
                      취소
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="mt-2 rounded-lg border border-line-subtle bg-surface-raised px-4 py-3">
            <h3 className="text-base font-semibold text-ink-1">{title.trim() || '무제'}</h3>
            {paragraphs.length === 0 ? (
              <p className="mt-2 text-sm text-ink-3">본문을 입력하면 여기에 문단으로 표시됩니다.</p>
            ) : (
              <div className="mt-2 space-y-2">
                {paragraphs.map((paragraph, index) => (
                  <p key={index} className="text-sm leading-relaxed text-ink-1">{paragraph}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-ink-1">최종 저장 (승인형)</p>
            <p className="mt-0.5 text-xs text-ink-3">되돌리기 어려운 최종 저장은 승인 대기를 거친 뒤 HWPX 로 내려받습니다.</p>
          </div>
          <button
            type="button"
            disabled={busy || composing || revising || (!title.trim() && !body.trim())}
            onClick={() => {
              void (async () => {
                setError(null);
                try {
                  await saveAeroWorkDocumentRequest({ title: title.trim(), body, format }, getCsrfCookie());
                  setDone('최종 저장을 요청했음 — 아래 목록에서 승인 후 내려받으세요.');
                  await loadSaved();
                } catch {
                  setError('최종 저장 요청 실패.');
                }
              })();
            }}
            className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken disabled:opacity-50"
          >
            최종 저장 요청
          </button>
        </div>
        {savedDocs.length === 0 ? (
          <p className="mt-2 text-xs text-ink-3">저장 요청한 문서가 없음.</p>
        ) : (
          <ul className="mt-2 space-y-1">
            {savedDocs.map((doc) => (
              <li key={doc.id} className="flex items-center gap-2 rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs">
                <span className="truncate font-medium text-ink-1">{doc.title}</span>
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${doc.status === 'approved' ? 'bg-emerald-500/15 text-emerald-600' : 'bg-amber-500/15 text-amber-600'}`}>
                  {doc.status === 'approved' ? '승인됨' : '승인 대기'}
                </span>
                <div className="ml-auto flex gap-1">
                  {doc.status !== 'approved' ? (
                    <button
                      type="button"
                      onClick={() => { void approveAeroWorkDocument(doc.id, getCsrfCookie()).then(loadSaved).catch(() => setError('승인 실패.')); }}
                      className="rounded px-2 py-0.5 text-[11px] text-accent hover:bg-accent-soft"
                    >
                      승인
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        void downloadSavedAeroWorkDocument(doc.id)
                          .then((blob) => {
                            const url = URL.createObjectURL(blob);
                            const anchor = document.createElement('a');
                            anchor.href = url;
                            anchor.download = `${doc.title}.hwpx`;
                            anchor.click();
                            URL.revokeObjectURL(url);
                          })
                          .catch(() => setError('다운로드 실패.'));
                      }}
                      className="rounded px-2 py-0.5 text-[11px] text-accent hover:bg-accent-soft"
                    >
                      HWPX
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => { void deleteSavedAeroWorkDocument(doc.id, getCsrfCookie()).then(loadSaved).catch(() => setError('삭제 실패.')); }}
                    className="rounded px-2 py-0.5 text-[11px] text-rose-600 hover:bg-rose-500/10"
                  >
                    삭제
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs leading-relaxed text-ink-3">
        ※ 표준 HWPX(한글, OWPML) 포맷으로 생성합니다. 파일 구조 유효성은 검증되었으나, 한컴 오피스에서의
        서식·호환은 한컴 설치 PC에서 실제 열어 확인하는 것을 권장합니다(실험적 기능). 시행문·양식 슬롯
        채움 등 서식 템플릿은 후속에서 확장합니다.
      </p>
    </form>
  );
}
