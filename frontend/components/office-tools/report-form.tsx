'use client';

import React from 'react';

import { generateReport } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { OfficeSample, ReportAiMode, ReportGenerateResponse } from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';
import { StepSection } from '@/components/office-tools/step-section';
import { DataInput, type DataInputMode } from '@/components/office-tools/data-input';
import { UsageGuide } from '@/components/office-tools/usage-guide';

const USAGE_WAYS = [
  { badge: '① 예제', title: '예제로 시작', detail: '아래 예제를 누르면 원문이 채워지고 바로 보고서가 만들어집니다.' },
  { badge: '② 원문', title: '파일 또는 정형 텍스트', detail: 'Markdown 파일을 올리거나, Markdown 텍스트를 직접 붙여넣습니다.' },
  { badge: '③ 옵션', title: '문서 정보·AI 편집', detail: '같은 입력 단계에서 제목·부제와 AI 다듬기(선택)를 함께 정합니다.' },
];

const MD_PLACEHOLDER ='# 보고서 제목\n\n## 요약\n\n핵심 결론을 먼저 씁니다.\n\n| 항목 | 값 |\n|---|---|\n| 매출 | 1,240 |';

const REPORT_STEPS: ProcessStep[] = [
  { label: 'Markdown 업로드', detail: '.md·.markdown·.txt' },
  { label: '서버 sanitize', detail: '안전한 HTML 만 허용' },
  { label: '이미지 임베드', detail: 'base64 로 내장(외부 요청 0)' },
  { label: 'AI 편집 / 변환만', detail: '원문 수치는 보존' },
  { label: '자립형 HTML', detail: 'HTML·zip 다운로드' },
];

const AI_MODES: { value: ReportAiMode; label: string; hint: string }[] = [
  { value: 'none', label: '변환만', hint: 'AI 편집 없이 Markdown 을 그대로 HTML 로 변환합니다.' },
  { value: 'polish', label: '문체 다듬기', hint: '맞춤법·가독성을 개선합니다. 원문 수치는 바꾸지 않습니다.' },
  { value: 'executive', label: '핵심 요약형', hint: '결론이 먼저 보이도록 재구성합니다(원문 정보만 사용).' },
];

export function ReportForm() {
  const [inputMode, setInputMode] = React.useState<DataInputMode>('file');
  const [markdownFile, setMarkdownFile] = React.useState<File | null>(null);
  const [markdownText, setMarkdownText] = React.useState('');
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
  const hasData = inputMode === 'text' ? !!markdownText.trim() : !!markdownFile;

  function effectiveFile(): File | null {
    if (inputMode === 'text') {
      return markdownText.trim() ? new File([markdownText], 'report.md', { type: 'text/markdown' }) : null;
    }
    return markdownFile;
  }

  const engineNote = result
    ? aiMode === 'none'
      ? '변환만 (AI 미사용)'
      : result.warnings.some((warning) => warning.includes('원문') || warning.includes('연결') || warning.includes('LLM'))
        ? 'AI 미연결 — 원문 유지'
        : 'AI 편집 사용'
    : undefined;

  function applySample(sample: OfficeSample) {
    // 예제는 텍스트 모드로 채워, 사용자가 Markdown 형식을 눈으로 확인하게 한다.
    setInputMode('text');
    setMarkdownText(sample.content);
    setMarkdownFile(null);
    setResult(null);
    const nextTitle = typeof sample.hints.title === 'string' ? sample.hints.title : title;
    const nextSubtitle = typeof sample.hints.subtitle === 'string' ? sample.hints.subtitle : subtitle;
    const nextAiMode = (typeof sample.hints.ai_mode === 'string' ? sample.hints.ai_mode : aiMode) as ReportAiMode;
    setTitle(nextTitle);
    setSubtitle(nextSubtitle);
    setAiMode(nextAiMode);
    setError('');
    // 예제는 채우기만 하지 않고 곧바로 생성까지 한다(원클릭 체험).
    const file = new File([sample.content], 'report.md', { type: 'text/markdown' });
    runGenerate({ file, title: nextTitle, subtitle: nextSubtitle, aiMode: nextAiMode });
  }

  // 실제 생성 — 상태가 아니라 명시 인자를 받아, 예제 클릭 직후에도 그 값으로 바로 실행한다.
  async function runGenerate(input: { file: File | null; title: string; subtitle: string; aiMode: ReportAiMode }) {
    if (busy || !input.file) return;
    setBusy(true);
    setError('');
    try {
      const response = await generateReport(
        { markdownFile: input.file, assets, title: input.title.trim(), subtitle: input.subtitle.trim(), documentVersion: documentVersion.trim(), tags: tags.trim(), aiMode: input.aiMode },
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

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runGenerate({ file: effectiveFile(), title, subtitle, aiMode });
  }

  return (
    <div className="flex flex-col gap-6">
      <UsageGuide
        intro="Markdown 을 이미지까지 내장한 단일 HTML 보고서로 변환합니다. 세 가지 방법 중 하나로 시작하세요."
        ways={USAGE_WAYS}
        output="이미지까지 내장한 자립형 HTML 보고서로 변환되어 HTML·zip 으로 내려받을 수 있습니다."
      />
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="보고서 생성 폼">
        <StepSection n={1} title="원문과 옵션 입력" hint="원문 · 문서 정보 · AI 편집을 한 곳에서" done={!!result}>
          <SamplePicker tool="report" onPick={applySample} disabled={busy} />
          <DataInput
            mode={inputMode}
            onModeChange={setInputMode}
            fileLabel="Markdown 파일 (.md / .markdown / .txt)"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            file={markdownFile}
            onFileChange={setMarkdownFile}
            text={markdownText}
            onTextChange={setMarkdownText}
            textPlaceholder={MD_PLACEHOLDER}
            textHint="Markdown 서술형으로 직접 붙여넣습니다(표·코드블록 지원)."
          />
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
          <div className="flex flex-col gap-2 rounded-lg border border-ink-3/15 bg-surface-sunken/40 px-4 py-3">
            <span className="text-sm font-semibold text-ink-1">
              문서 정보 <span className="font-normal text-ink-3">— 모두 선택, 비워도 됩니다</span>
            </span>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-2">제목</span>
                <input
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={200}
                  className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                  placeholder="비우면 원문 첫 # 제목을 사용"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-2">부제</span>
                <input
                  type="text"
                  value={subtitle}
                  onChange={(event) => setSubtitle(event.target.value)}
                  maxLength={200}
                  className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                  placeholder="문서 부제목"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-2">버전</span>
                <input
                  type="text"
                  value={documentVersion}
                  onChange={(event) => setDocumentVersion(event.target.value)}
                  maxLength={40}
                  className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                  placeholder="예: v1.0"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-ink-2">태그</span>
                <input
                  type="text"
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  maxLength={120}
                  className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                  placeholder="쉼표로 구분"
                />
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-2 rounded-lg border border-ink-3/15 bg-surface-sunken/40 px-4 py-3">
            <span className="text-sm font-semibold text-ink-1">
              AI 편집 <span className="font-normal text-ink-3">— 선택, 원문 수치는 그대로 보존</span>
            </span>
            <span className="text-xs text-ink-3">원문을 그대로 변환할지, AI 로 문체를 다듬거나 핵심만 요약할지 고릅니다.</span>
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
          </div>
        </StepSection>

        <StepSection n={2} title="생성" hint="보고서를 만들고 내려받습니다" done={!!result}>
          <button
            type="submit"
            disabled={busy || !hasData}
            className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? '생성 중…' : '보고서 생성'}
          </button>
        </StepSection>
      </form>

      <ProcessSteps steps={REPORT_STEPS} done={!!result} engineNote={engineNote} />

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
