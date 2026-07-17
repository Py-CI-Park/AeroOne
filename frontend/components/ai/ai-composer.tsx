'use client';

import React, { useRef, useState } from 'react';

import type { AiAttachment } from '@/lib/types';

import { dedupeAttachmentsByName, isAllowedAttachmentName, readAttachmentFiles } from '@/components/ai/ai-attachments';

const PROMPT_PRESETS: ReadonlyArray<{ label: string; prompt: string }> = [
  { label: '요약', prompt: '선택한 문서의 핵심 내용을 5줄 이내로 요약해 주세요.' },
  { label: '보고서 검토', prompt: '선택한 문서를 보고서 관점에서 검토하고, 누락·모호·근거 부족 부분을 항목별로 지적해 주세요.' },
  { label: '위험 식별', prompt: '선택한 문서에서 운영·안전·일정·비용 관점의 위험 요소를 찾아 우선순위와 함께 정리해 주세요.' },
  { label: '비교', prompt: '선택한 문서들의 핵심 항목을 표 형태로 비교하고 차이점을 설명해 주세요.' },
  { label: '핵심 추출', prompt: '선택한 문서에서 의사결정에 필요한 핵심 수치와 결론만 뽑아 주세요.' },
  { label: '후속 질문', prompt: '선택한 문서를 더 깊이 이해하기 위해 확인해야 할 후속 질문 5개를 제안해 주세요.' },
];

interface AiComposerProps {
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  canSubmit: boolean;
  pending: boolean;
  onStop: () => void;
  onRegenerate: () => void;
  hasMessages: boolean;
  useSearch: boolean;
  onToggleSearch: (checked: boolean) => void;
  scope: { document: boolean; civil: boolean; nsa: boolean };
  onToggleScope: (key: 'document' | 'civil' | 'nsa') => void;
  nsaUnlocked: boolean;
  attachments: AiAttachment[];
  onAttachmentsChange: (attachments: AiAttachment[]) => void;
  attachmentError: string;
}

export function AiComposer({
  input,
  onInputChange,
  onSubmit,
  canSubmit,
  pending,
  onStop,
  onRegenerate,
  hasMessages,
  useSearch,
  onToggleSearch,
  scope,
  onToggleScope,
  nsaUnlocked,
  attachments,
  onAttachmentsChange,
  attachmentError,
}: AiComposerProps) {
  const [dragOver, setDragOver] = useState(false);
  const [fileError, setFileError] = useState('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function addFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    const accepted = list.filter((file) => isAllowedAttachmentName(file.name));
    const rejected = list.filter((file) => !isAllowedAttachmentName(file.name));
    setFileError(rejected.length > 0 ? `${rejected.map((file) => file.name).join(', ')}: .md/.txt/.csv 파일만 첨부할 수 있습니다.` : '');
    if (accepted.length === 0) return;
    try {
      const read = await readAttachmentFiles(accepted);
      // 같은 이름은 마지막 것으로 대체(칩 key 충돌·중복 컨텍스트 방지).
      onAttachmentsChange(dedupeAttachmentsByName([...attachments, ...read]));
    } catch (error) {
      // 크기 초과/읽기 실패는 첨부하지 않고 사유만 표시한다.
      setFileError(error instanceof Error ? error.message : '파일을 읽지 못했습니다.');
    }
  }

  function removeAttachment(name: string) {
    onAttachmentsChange(attachments.filter((attachment) => attachment.name !== name));
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    if (event.dataTransfer.files?.length) void addFiles(event.dataTransfer.files);
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2">
      <div data-testid="ai-presets" className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-ink-2">프롬프트</span>
        {PROMPT_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => onInputChange(preset.prompt)}
            className="rounded-full border border-line-subtle px-2.5 py-1 text-xs text-ink-2 hover:bg-surface-sunken"
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div
        className={`flex flex-col gap-2 rounded ${dragOver ? 'ring-2 ring-accent' : ''}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <textarea
          data-testid="ai-chat-input"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="AeroAI 에게 질문하세요"
          className="min-h-24 rounded border border-line-subtle bg-surface-elevated px-3 py-2 text-base text-ink-1 placeholder:text-ink-3"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="파일 첨부"
            className="inline-flex items-center gap-1.5 rounded-md border border-line-subtle px-2.5 py-1 text-xs font-medium text-ink-2 hover:bg-surface-sunken"
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-3.5 w-3.5" aria-hidden>
              <path d="M13.5 5.5 7.2 11.8a2.2 2.2 0 0 0 3.1 3.1l6-6a3.8 3.8 0 0 0-5.4-5.4l-6 6a5.4 5.4 0 0 0 7.6 7.6l5.2-5.2" />
            </svg>
            파일 첨부
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
          <span className="text-xs text-ink-3">.md/.txt/.csv 파일을 끌어다 놓거나 첨부하세요(최대 5개).</span>
        </div>
        {attachments.length > 0 ? (
          <div data-testid="ai-attachments" className="flex flex-wrap items-center gap-2">
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
        {fileError || attachmentError ? (
          <p role="alert" className="rounded bg-warn-soft px-2 py-1 text-xs text-warn">{fileError || attachmentError}</p>
        ) : null}
      </div>
      <div data-testid="ai-scope" className="flex flex-wrap items-center gap-3 text-xs text-ink-2">
        <span className="font-medium">근거 범위</span>
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={scope.document} onChange={() => onToggleScope('document')} />
          Document
        </label>
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={scope.civil} onChange={() => onToggleScope('civil')} />
          Civil
        </label>
        <label className={`inline-flex items-center gap-1 ${nsaUnlocked ? '' : 'opacity-50'}`} title={nsaUnlocked ? '' : 'NSA 자료 접근 권한이 있는 계정만 사용할 수 있습니다'}>
          <input type="checkbox" checked={scope.nsa} disabled={!nsaUnlocked} onChange={() => onToggleScope('nsa')} />
          NSA{nsaUnlocked ? '' : ' (권한 없음)'}
        </label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" checked={useSearch} onChange={(event) => onToggleSearch(event.target.checked)} />
          문서 검색 결과를 답변 근거로 사용(document/civil)
        </label>
        <div className="flex items-center gap-2">
          {pending ? (
            <button
              type="button"
              onClick={onStop}
              className="rounded-md border border-line-strong px-3 py-2 text-sm font-medium text-ink-1 hover:bg-surface-sunken"
            >
              중지
            </button>
          ) : (
            <button
              type="button"
              onClick={onRegenerate}
              disabled={!hasMessages}
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
  );
}
