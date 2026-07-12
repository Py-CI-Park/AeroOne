'use client';

import React from 'react';

export type DataInputMode = 'file' | 'text';

type DataInputProps = {
  mode: DataInputMode;
  onModeChange: (mode: DataInputMode) => void;
  fileLabel: string;
  accept: string;
  fileHint?: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  text: string;
  onTextChange: (text: string) => void;
  textPlaceholder: string;
};

/**
 * 데이터 입력 — 파일 업로드와 직접 텍스트 입력을 토글로 전환한다.
 *
 * 파일이 없거나 형식이 낯선 사용자도 텍스트로 붙여넣어 바로 시험할 수 있게 한다. 예제 칩을
 * 누르면 상위 폼이 텍스트 모드로 전환하고 내용을 채워, 사용자가 "어떤 형식인지" 눈으로
 * 확인하도록 돕는다. 파일 입력의 접근성 라벨(fileLabel)은 그대로 유지한다.
 */
export function DataInput({
  mode,
  onModeChange,
  fileLabel,
  accept,
  fileHint,
  file,
  onFileChange,
  text,
  onTextChange,
  textPlaceholder,
}: DataInputProps) {
  const tabClass = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-xs font-medium transition ${
      active ? 'bg-surface-raised text-ink-1 shadow-sm ring-1 ring-accent/30' : 'text-ink-3 hover:text-ink-1'
    }`;

  return (
    <div className="flex flex-col gap-2">
      <div className="inline-flex w-fit gap-1 rounded-lg bg-surface-sunken p-1">
        <button type="button" onClick={() => onModeChange('file')} className={tabClass(mode === 'file')} aria-pressed={mode === 'file'}>
          파일 업로드
        </button>
        <button type="button" onClick={() => onModeChange('text')} className={tabClass(mode === 'text')} aria-pressed={mode === 'text'}>
          직접 입력
        </button>
      </div>

      {mode === 'file' ? (
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">{fileLabel}</span>
          <input
            type="file"
            accept={accept}
            onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          />
          {file ? <span className="text-xs text-ink-3">선택됨: {file.name}</span> : null}
          {fileHint ? <span className="text-xs text-ink-3">{fileHint}</span> : null}
        </label>
      ) : (
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">{fileLabel}</span>
          <textarea
            value={text}
            onChange={(event) => onTextChange(event.target.value)}
            rows={8}
            spellCheck={false}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 font-mono text-xs text-ink-1"
            placeholder={textPlaceholder}
          />
          <span className="text-xs text-ink-3">붙여넣거나 직접 입력하세요. 위 예제 칩을 누르면 형식이 채워집니다.</span>
        </label>
      )}
    </div>
  );
}
