'use client';

import React from 'react';

import { generateReport, getOfficeArtifactProxyPath } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { OfficeArtifact, OfficeJobDetail, OfficeSample, ReportAiMode, ReportGenerateResponse } from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';
import { StepSection } from '@/components/office-tools/step-section';
import { DataInput, type DataInputMode } from '@/components/office-tools/data-input';
import { UsageGuide } from '@/components/office-tools/usage-guide';
import { useOfficeWorkspaceSelection } from '@/components/office-tools/workspace-context';

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

const OFFICE_ARTIFACT_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/artifacts\/[A-Za-z0-9-][A-Za-z0-9._-]*$/;
const OFFICE_BUNDLE_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/bundle$/;
const OFFICE_JOB_ID = /^[0-9a-f]{32}$/;

type ReportWorkspaceMetadata = {
  jobId?: string;
  title?: string;
  subtitle?: string;
  documentVersion?: string;
  tags?: string;
  aiMode?: ReportAiMode;
  llmUsed?: boolean;
  previewUrl?: string;
  bundleUrl?: string;
  warnings: string[];
  artifacts: OfficeArtifact[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringValue(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === 'string' ? value : undefined;
}

function booleanValue(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === 'boolean' ? value : undefined;
}
function firstBoolean(sources: Record<string, unknown>[], keys: string[]) {
  for (const source of sources) {
    for (const key of keys) {
      const value = booleanValue(source, key);
      if (value !== undefined) return value;
    }
  }
  return undefined;
}


function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function isReportAiMode(value: unknown): value is ReportAiMode {
  return value === 'none' || value === 'polish' || value === 'executive';
}

function firstString(sources: Record<string, unknown>[], keys: string[]) {
  for (const source of sources) {
    for (const key of keys) {
      const value = stringValue(source, key);
      if (value !== undefined) return value;
    }
  }
  return undefined;
}

function firstReportAiMode(sources: Record<string, unknown>[]) {
  for (const source of sources) {
    for (const key of ['ai_mode', 'aiMode']) {
      const value = source[key];
      if (isReportAiMode(value)) return value;
    }
  }
  return undefined;
}

function proxyOfficePath(path: unknown, pattern: RegExp) {
  if (typeof path !== 'string' || !pattern.test(path)) return null;
  try {
    return getOfficeArtifactProxyPath(path);
  } catch {
    return null;
  }
}

function officeArtifact(value: unknown): OfficeArtifact | null {
  if (!isRecord(value)) return null;

  const filename = stringValue(value, 'filename');
  const mediaType = stringValue(value, 'media_type');
  const sizeBytes = value.size_bytes;
  const sha256 = stringValue(value, 'sha256');
  const downloadUrl = stringValue(value, 'download_url');
  if (
    filename === undefined ||
    mediaType === undefined ||
    typeof sizeBytes !== 'number' ||
    !Number.isFinite(sizeBytes) ||
    sizeBytes < 0 ||
    sha256 === undefined ||
    downloadUrl === undefined
  ) {
    return null;
  }

  return { filename, media_type: mediaType, size_bytes: sizeBytes, sha256, download_url: downloadUrl };
}

function officeArtifacts(value: unknown) {
  return Array.isArray(value) ? value.flatMap((artifact) => {
    const validArtifact = officeArtifact(artifact);
    return validArtifact ? [validArtifact] : [];
  }) : [];
}

function manifestArtifactLinks(artifacts: unknown) {
  return officeArtifacts(artifacts).flatMap((artifact) => {
    const href = proxyOfficePath(artifact.download_url, OFFICE_ARTIFACT_PATH);
    return href ? [{ ...artifact, href }] : [];
  });
}

function reportWorkspaceMetadata(job: OfficeJobDetail): ReportWorkspaceMetadata | null {
  const detail = isRecord(job) ? job : null;
  if (!detail || detail.service !== 'report' || detail.status !== 'completed') return null;

  const requestSummary = isRecord(detail.request_summary) ? detail.request_summary : {};
  const sources = [detail, requestSummary];
  // Provenance는 완료된 레코드(detail)에서만 읽는다. request_summary는 요청 의도라 신뢰하지 않는다.
  const llmUsed = firstBoolean([detail], ['llm_used', 'llmUsed']);

  return {
    jobId: firstString(sources, ['job_id']),
    title: firstString(sources, ['title']),
    subtitle: firstString(sources, ['subtitle']),
    documentVersion: firstString(sources, ['document_version', 'documentVersion', 'version']),
    tags: firstString(sources, ['tags']),
    aiMode: firstReportAiMode(sources),
    llmUsed,
    previewUrl: firstString(sources, ['preview_url', 'previewUrl']),
    bundleUrl: firstString(sources, ['bundle_url', 'bundleUrl']),
    warnings: stringArray(detail.warnings),
    artifacts: officeArtifacts(detail.artifacts),
  };
}

function restoredReportResult(metadata: ReportWorkspaceMetadata): ReportGenerateResponse | null {
  if (!metadata.jobId || !OFFICE_JOB_ID.test(metadata.jobId) || metadata.llmUsed === undefined) return null;
  if (!metadata.previewUrl || !OFFICE_ARTIFACT_PATH.test(metadata.previewUrl)) return null;

  return {
    job_id: metadata.jobId,
    status: 'completed',
    title: metadata.title ?? '',
    ai_mode: metadata.aiMode ?? 'none',
    llm_used: metadata.llmUsed,
    html: '',
    warnings: metadata.warnings,
    artifacts: metadata.artifacts,
    preview_url: metadata.previewUrl,
    bundle_url: metadata.bundleUrl ?? '',
  };
}

function isAbortError(error: unknown) {
  return isRecord(error) && error.name === 'AbortError';
}

export function ReportForm() {
  const workspaceSelection = useOfficeWorkspaceSelection();
  const [inputMode, setInputMode] = React.useState<DataInputMode>('file');
  const [markdownFile, setMarkdownFile] = React.useState<File | null>(null);
  const [markdownText, setMarkdownText] = React.useState('');
  const [assets, setAssets] = React.useState<File[]>([]);
  const [sourceResetKey, setSourceResetKey] = React.useState(0);
  const [title, setTitle] = React.useState('');
  const [subtitle, setSubtitle] = React.useState('');
  const [documentVersion, setDocumentVersion] = React.useState('');
  const [tags, setTags] = React.useState('');
  const [aiMode, setAiMode] = React.useState<ReportAiMode>('none');
  const [result, setResult] = React.useState<ReportGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [workspaceNotice, setWorkspaceNotice] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const activeControllerRef = React.useRef<AbortController | null>(null);
  const latestRequestRef = React.useRef(0);
  const appliedSelectionSequenceRef = React.useRef<number | null>(null);

  const invalidateRequests = React.useCallback(() => {
    latestRequestRef.current += 1;
    activeControllerRef.current?.abort();
    activeControllerRef.current = null;
  }, []);

  const clearGeneratedState = React.useCallback(() => {
    invalidateRequests();
    setResult(null);
    setError('');
    setWorkspaceNotice('');
    setBusy(false);
  }, [invalidateRequests]);

  React.useEffect(() => () => {
    invalidateRequests();
  }, [invalidateRequests]);

  React.useEffect(() => {
    if (!workspaceSelection || appliedSelectionSequenceRef.current === workspaceSelection.sequence) return;
    appliedSelectionSequenceRef.current = workspaceSelection.sequence;

    clearGeneratedState();
    const metadata = reportWorkspaceMetadata(workspaceSelection.job);
    if (!metadata) return;

    setInputMode('file');
    setMarkdownFile(null);
    setMarkdownText('');
    setAssets([]);
    setSourceResetKey((key) => key + 1);
    setTitle(metadata.title ?? '');
    setSubtitle(metadata.subtitle ?? '');
    setDocumentVersion(metadata.documentVersion ?? '');
    setTags(metadata.tags ?? '');
    setAiMode(metadata.aiMode ?? 'none');

    if (workspaceSelection.mode === 'duplicate') {
      setWorkspaceNotice('설정만 복제했습니다. 원본 Markdown과 첨부 자산을 다시 첨부하세요.');
      return;
    }

    if (workspaceSelection.mode === 'reopen') {
      const restoredResult = restoredReportResult(metadata);
      if (restoredResult) setResult(restoredResult);
    }
  }, [clearGeneratedState, workspaceSelection]);

  const activeHint = AI_MODES.find((item) => item.value === aiMode)?.hint ?? '';
  const hasData = inputMode === 'text' ? !!markdownText.trim() : !!markdownFile;
  const engineNote = result ? (result.llm_used ? 'AI 편집 사용' : 'AI 미사용') : undefined;
  const hasInlinePreview = typeof result?.html === 'string' && result.html.trim().length > 0;
  const previewHref = result && !hasInlinePreview ? proxyOfficePath(result.preview_url, OFFICE_ARTIFACT_PATH) : null;
  const bundleHref = result ? proxyOfficePath(result.bundle_url, OFFICE_BUNDLE_PATH) : null;
  const artifactLinks = result ? manifestArtifactLinks(result.artifacts) : [];

  function effectiveFile(): File | null {
    if (inputMode === 'text') {
      return markdownText.trim() ? new File([markdownText], 'report.md', { type: 'text/markdown' }) : null;
    }
    return markdownFile;
  }

  function editInput(update: () => void) {
    clearGeneratedState();
    update();
  }

  function applySample(sample: OfficeSample) {
    const nextTitle = typeof sample.hints.title === 'string' ? sample.hints.title : title;
    const nextSubtitle = typeof sample.hints.subtitle === 'string' ? sample.hints.subtitle : subtitle;
    const nextAiMode = isReportAiMode(sample.hints.ai_mode) ? sample.hints.ai_mode : aiMode;
    const file = new File([sample.content], 'report.md', { type: 'text/markdown' });

    clearGeneratedState();
    setInputMode('text');
    setMarkdownText(sample.content);
    setMarkdownFile(null);
    setTitle(nextTitle);
    setSubtitle(nextSubtitle);
    setAiMode(nextAiMode);
    // 예제는 채우기만 하지 않고 곧바로 생성까지 한다(원클릭 체험).
    runGenerate({ file, title: nextTitle, subtitle: nextSubtitle, aiMode: nextAiMode, assets, documentVersion, tags });
  }

  // 실제 생성 — 상태가 아니라 명시 인자를 받아, 예제 클릭 직후에도 그 값으로 바로 실행한다.
  async function runGenerate(input: {
    file: File | null;
    title: string;
    subtitle: string;
    aiMode: ReportAiMode;
    assets: File[];
    documentVersion: string;
    tags: string;
  }) {
    if (!input.file) return;

    invalidateRequests();
    const token = ++latestRequestRef.current;
    const controller = new AbortController();
    activeControllerRef.current = controller;
    setBusy(true);
    setResult(null);
    setError('');
    setWorkspaceNotice('');

    try {
      const response = await generateReport(
        {
          markdownFile: input.file,
          assets: input.assets,
          title: input.title.trim(),
          subtitle: input.subtitle.trim(),
          documentVersion: input.documentVersion.trim(),
          tags: input.tags.trim(),
          aiMode: input.aiMode,
        },
        getCsrfCookie(),
        controller.signal,
      );
      if (latestRequestRef.current !== token) return;
      setResult(response);
    } catch (cause) {
      if (latestRequestRef.current !== token || isAbortError(cause)) return;
      setResult(null);
      setError(cause instanceof Error ? cause.message : '보고서 생성에 실패했습니다.');
    } finally {
      if (latestRequestRef.current !== token) return;
      if (activeControllerRef.current === controller) activeControllerRef.current = null;
      setBusy(false);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runGenerate({ file: effectiveFile(), title, subtitle, aiMode, assets, documentVersion, tags });
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
            key={sourceResetKey}
            mode={inputMode}
            onModeChange={(mode) => editInput(() => setInputMode(mode))}
            fileLabel="Markdown 파일 (.md / .markdown / .txt)"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            file={markdownFile}
            onFileChange={(file) => editInput(() => setMarkdownFile(file))}
            text={markdownText}
            onTextChange={(text) => editInput(() => setMarkdownText(text))}
            textPlaceholder={MD_PLACEHOLDER}
            textHint="Markdown 서술형으로 직접 붙여넣습니다(표·코드블록 지원)."
          />
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">이미지 / ZIP (선택, 여러 개 가능)</span>
            <input
              key={sourceResetKey}
              type="file"
              multiple
              accept=".png,.jpg,.jpeg,.gif,.webp,.svg,.zip"
              onChange={(event) => editInput(() => setAssets(Array.from(event.target.files ?? [])))}
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
                  onChange={(event) => editInput(() => setTitle(event.target.value))}
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
                  onChange={(event) => editInput(() => setSubtitle(event.target.value))}
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
                  onChange={(event) => editInput(() => setDocumentVersion(event.target.value))}
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
                  onChange={(event) => editInput(() => setTags(event.target.value))}
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
              onChange={(event) => {
                const nextMode = event.target.value;
                if (isReportAiMode(nextMode)) editInput(() => setAiMode(nextMode));
              }}
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

      {workspaceNotice ? <p role="status" className="text-sm text-ink-2">{workspaceNotice}</p> : null}

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
            {artifactLinks.map((artifact) => (
              <a
                key={`${artifact.filename}-${artifact.download_url}`}
                href={artifact.href}
                download
                className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
              >
                {artifact.filename}
              </a>
            ))}
            {bundleHref ? (
              <a
                href={bundleHref}
                download
                className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
              >
                전체 번들(zip)
              </a>
            ) : null}
          </div>
          {hasInlinePreview ? (
            <iframe
              title="보고서 미리보기"
              sandbox=""
              srcDoc={result.html}
              className="h-[640px] w-full rounded-md border border-ink-3/30 bg-white"
            />
          ) : previewHref ? (
            <iframe
              title="보고서 미리보기"
              sandbox=""
              src={previewHref}
              className="h-[640px] w-full rounded-md border border-ink-3/30 bg-white"
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
