'use client';

import React from 'react';

import { generateReport } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { ReportAiMode, ReportGenerateResponse } from '@/lib/types';

const AI_MODES: { value: ReportAiMode; label: string; hint: string }[] = [
  { value: 'none', label: '변환만', hint: 'AI 편집 없이 Markdown 을 그대로 HTML 로 변환합니다.' },
  { value: 'polish', label: '문체 다듬기', hint: '맞춤법·가독성을 개선합니다. 원문 수치는 바꾸지 않습니다.' },
  { value: 'executive', label: '핵심 요약형', hint: '결론이 먼저 보이도록 재구성합니다(원문 정보만 사용).' },
];

export function ReportForm() {
  const [markdownFile, setMarkdownFile] = React.useState<File | null>(null);
  const [assets, setAssets] = React.useState<File[]>([]);
  const [title, setTitle] = React.useState('');
  const [subtitle, setSubtitle] = React.useState('');
  const [documentVersion, setDocumentVersion] = React.useState('');
  const [tags, setTags] = React.useState('');
  const [aiMode, setAiMode] = React.useState<ReportAiMode>('none');
  const [result, setResult] = React.useState<ReportGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const activeHint = AI_MODES.find((item) => item.value === aiMode)?.hint ?? '';

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !markdownFile) return;
    setBusy(true);
    setError('');
    try {
      const response = await generateReport(
        { markdownFile, assets, title: title.trim(), subtitle: subtitle.trim(), documentVersion: documentVersion.trim(), tags: tags.trim(), aiMode },
        getCsrfCookie(),
      );
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : '보고서 생성에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="보고서 생성 폼">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">Markdown 파일 (.md / .markdown / .txt)</span>
          <input
            type="file"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            onChange={(event) => setMarkdownFile(event.target.files?.[0] ?? null)}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">이미지 / ZIP (선택, 여러 개 가능)</span>
          <input
            type="file"
            multiple
            accept=".png,.jpg,.jpeg,.gif,.webp,.svg,.zip"
            onChange={(event) => setAssets(Array.from(event.target.files ?? []))}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          />
          <span className="text-xs text-ink-3">Markdown 안 ![alt](파일명) 참조가 base64 로 문서에 임베드됩니다(외부 요청 0).</span>
        </label>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">제목 (선택)</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
              placeholder="비우면 첫 # 제목을 사용합니다"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">부제 (선택)</span>
            <input
              type="text"
              value={subtitle}
              onChange={(event) => setSubtitle(event.target.value)}
              maxLength={200}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">버전 (선택)</span>
            <input
              type="text"
              value={documentVersion}
              onChange={(event) => setDocumentVersion(event.target.value)}
              maxLength={40}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">태그 (선택)</span>
            <input
              type="text"
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              maxLength={120}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            />
          </label>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">AI 편집</span>
          <select
            value={aiMode}
            onChange={(event) => setAiMode(event.target.value as ReportAiMode)}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          >
            {AI_MODES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <span className="text-xs text-ink-3">{activeHint}</span>
        </label>

        <button
          type="submit"
          disabled={busy || !markdownFile}
          className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? '생성 중…' : '보고서 생성'}
        </button>
      </form>

      {error ? (
        <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <section className="flex flex-col gap-3" data-testid="report-result">
          {result.warnings.length > 0 ? (
            <ul className="rounded-md border border-amber-400/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : null}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium text-ink-1">{result.title}</span>
            <a
              href={`/api/frontend/office-tools/jobs/${result.job_id}/artifacts/aeroone_report.html`}
              download
              className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
            >
              HTML 다운로드
            </a>
            <a
              href={`/api/frontend/office-tools/jobs/${result.job_id}/bundle`}
              download
              className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
            >
              전체 번들(zip)
            </a>
          </div>
          <iframe
            title="보고서 미리보기"
            sandbox=""
            srcDoc={result.html}
            className="h-[640px] w-full rounded-md border border-ink-3/30 bg-white"
          />
        </section>
      ) : null}
    </div>
  );
}
