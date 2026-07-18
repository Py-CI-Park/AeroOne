'use client';

import React from 'react';

import type { ChartInspectResponse } from '@/lib/types';

const FOLLOW_UP_EXAMPLES = ['상위 5개만', '가로 막대로', '누적으로'];

// 탭 또는 콤마로 구분된 2줄 이상의 텍스트는 표 형식 데이터로 취급할 수 있다는 신호로 본다.
const TABULAR_DELIMITER = /[\t,]/;

export function looksLikeTabularData(text: string): boolean {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (lines.length < 2) return false;
  return lines.every((line) => TABULAR_DELIMITER.test(line));
}

export function fileFromPastedData(text: string, filename = 'pasted-data.csv'): File {
  return new File([text], filename, { type: 'text/csv' });
}

type ChartComposerProps = {
  file: File | null;
  onFileChange: (file: File | null) => void;
  promptText: string;
  onPromptChange: (text: string) => void;
  profile: ChartInspectResponse | null;
  inspectBusy: boolean;
  busy: boolean;
  onSubmit: () => void;
  submitDisabled: boolean;
};

/**
 * 차트 스튜디오의 단일 입력 컴포저 — 목적 문장 입력과 표 데이터 붙여넣기를 한 텍스트 영역이
 * 겸한다. 붙여넣은(또는 입력된) 내용이 표 형식으로 보이면 "데이터로 사용"을 제안하고, 파일은
 * 클립 버튼 또는 드래그앤드롭으로 첨부한다. 데이터가 확정되면 상위 컴포넌트가 디바운스된
 * 자동 미리보기(inspect)를 수행해 열 칩으로 보여 준다.
 */
export function ChartComposer({
  file,
  onFileChange,
  promptText,
  onPromptChange,
  profile,
  inspectBusy,
  busy,
  onSubmit,
  submitDisabled,
}: ChartComposerProps) {
  const [dragOver, setDragOver] = React.useState(false);
  const [attachNotice, setAttachNotice] = React.useState('');
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const suggestDataFromText = !file && looksLikeTabularData(promptText);

  function attach(next: File) {
    onFileChange(next);
    setAttachNotice(`첨부됨: ${next.name}`);
  }

  function acceptSuggestedData() {
    attach(fileFromPastedData(promptText));
    onPromptChange('');
    setAttachNotice('붙여넣은 표 형식 데이터를 데이터로 사용합니다.');
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) attach(dropped);
  }

  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border p-4 transition ${
        dragOver ? 'border-accent bg-accent-soft' : 'border-ink-3/30 bg-surface-sunken/30'
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      data-testid="chart-composer"
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-ink-1">목적 문장 또는 데이터</span>
        <textarea
          value={promptText}
          onChange={(event) => onPromptChange(event.target.value)}
          rows={5}
          className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          placeholder={'예: 지역별 매출을 크기순으로 비교\n또는 표 형식(CSV) 데이터를 그대로 붙여넣으세요'}
        />
      </label>

      {suggestDataFromText ? (
        <div className="flex items-center gap-2 rounded-md border border-accent/40 bg-accent-soft px-3 py-2 text-xs text-ink-1" role="status">
          <span>표 형식 데이터로 보입니다.</span>
          <button
            type="button"
            onClick={acceptSuggestedData}
            className="rounded-md bg-accent px-2 py-1 font-medium text-accent-on hover:bg-accent-hover"
          >
            데이터로 사용
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-md border border-ink-3/40 px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-ink-3/10"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-3.5 w-3.5" aria-hidden>
            <path d="M13.5 5.5 7.2 11.8a2.2 2.2 0 0 0 3.1 3.1l6-6a3.8 3.8 0 0 0-5.4-5.4l-6 6a5.4 5.4 0 0 0 7.6 7.6l5.2-5.2" />
          </svg>
          파일 첨부
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xlsm,.json,text/csv,application/json"
          className="hidden"
          aria-label="데이터 파일"
          onChange={(event) => {
            const next = event.target.files?.[0] ?? null;
            if (next) attach(next);
          }}
        />
        {file ? (
          <span className="text-xs text-ink-3">선택됨: {file.name}</span>
        ) : (
          <span className="text-xs text-ink-3">파일을 끌어다 놓거나 첨부하세요.</span>
        )}
        {inspectBusy ? <span className="text-xs text-ink-3">열 확인 중…</span> : null}
      </div>

      {attachNotice ? <p className="text-xs text-ink-3">{attachNotice}</p> : null}

      {profile ? (
        <div className="flex flex-wrap gap-1.5" data-testid="chart-column-chips">
          {profile.columns.map((column) => (
            <span
              key={column.name}
              className="inline-flex items-center gap-1 rounded-full border border-ink-3/30 bg-surface-raised px-2.5 py-1 text-xs text-ink-1"
            >
              {column.name}
              <span className="rounded-full bg-ink-3/10 px-1.5 text-[10px] text-ink-3">
                {column.numeric ? '숫자' : column.datetime ? '날짜' : '범주'}
              </span>
            </span>
          ))}
        </div>
      ) : null}

      <div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={submitDisabled || busy}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? '처리 중…' : '차트 생성'}
        </button>
      </div>
    </div>
  );
}

type ChartFollowUpProps = {
  onSubmit: (text: string) => void;
  busy: boolean;
  /** 원본 데이터가 없어(예: 이력에서 다시 연 결과) 후속 명령을 보낼 수 없는 상태. */
  disabled?: boolean;
  disabledHint?: string;
};

/**
 * 결과 아래 후속 명령 입력 — 직전 성공 결과(previousSpec)를 기준으로 한 줄 명령을 덧붙여
 * 다시 생성한다. 예시 칩은 자주 쓰는 다듬기 명령을 곧바로 전송한다. `disabled` 이면
 * 입력을 막고 사유(hint)를 보여 줘 '눌러도 안 되는' 막다른 UI 를 만들지 않는다.
 */
export function ChartFollowUp({ onSubmit, busy, disabled = false, disabledHint }: ChartFollowUpProps) {
  const [text, setText] = React.useState('');
  const blocked = disabled || busy;

  function submit(value: string) {
    const trimmed = value.trim();
    if (!trimmed || blocked) return;
    onSubmit(trimmed);
    setText('');
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-ink-3/30 bg-surface-sunken/30 p-4" data-testid="chart-follow-up">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-ink-1">후속 명령으로 다듬기</span>
        <div className="flex gap-2">
          <input
            type="text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                submit(text);
              }
            }}
            disabled={disabled}
            placeholder="예: 상위 5개만, 가로 막대로"
            className="flex-1 rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => submit(text)}
            disabled={blocked || !text.trim()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? '처리 중…' : '전송'}
          </button>
        </div>
      </label>
      {disabled && disabledHint ? (
        <p className="text-xs text-ink-3" role="note">{disabledHint}</p>
      ) : null}
      <span className="flex flex-wrap gap-1.5">
        <span className="text-xs text-ink-3">예시</span>
        {FOLLOW_UP_EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => submit(example)}
            disabled={blocked}
            className="rounded-full border border-ink-3/30 px-2.5 py-0.5 text-xs text-ink-2 transition hover:border-accent/50 hover:bg-accent-soft disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </span>
    </div>
  );
}
