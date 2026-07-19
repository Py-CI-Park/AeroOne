'use client';

import { FormEvent, useMemo, useState } from 'react';

import { generateAeroWorkHwpx } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work P3 문서작성 — 제목 + 본문(한 줄=한 문단)을 즉시 미리보고 HWPX(한글, OWPML) 로
// 내려받는다. OWPML 구조 유효성은 백엔드 테스트로 보장하지만, 한컴 오피스 실제 서식/호환은
// 실기(한컴 설치 PC) 확인이 필요한 실험적 기능이라 화면에 명시한다. 임의형식 슬롯 채움은 후속.

export function DocumentPanel() {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const paragraphs = useMemo(
    () => body.split('\n').map((line) => line.trim()).filter(Boolean),
    [body],
  );

  const handleGenerate = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() && !body.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const blob = await generateAeroWorkHwpx({ title: title.trim(), body }, getCsrfCookie());
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

  return (
    <form onSubmit={handleGenerate} className="mt-4 space-y-4">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600">{error}</p>
      ) : null}
      {done ? (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600">{done}</p>
      ) : null}

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
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
          className="mt-2 w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm leading-relaxed text-ink-1"
        />
        <div className="mt-3 flex items-center gap-2">
          <button
            type="submit"
            disabled={busy || (!title.trim() && !body.trim())}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
          >
            {busy ? '생성 중…' : 'HWPX 생성·다운로드'}
          </button>
          <span className="text-xs text-ink-3">{paragraphs.length}개 문단</span>
        </div>
      </div>

      <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
        <p className="text-sm font-semibold text-ink-1">미리보기</p>
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
      </div>

      <p className="text-xs leading-relaxed text-ink-3">
        ※ 표준 HWPX(한글, OWPML) 포맷으로 생성합니다. 파일 구조 유효성은 검증되었으나, 한컴 오피스에서의
        서식·호환은 한컴 설치 PC에서 실제 열어 확인하는 것을 권장합니다(실험적 기능). 시행문·양식 슬롯
        채움 등 서식 템플릿은 후속에서 확장합니다.
      </p>
    </form>
  );
}
