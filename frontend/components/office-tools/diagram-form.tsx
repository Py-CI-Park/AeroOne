'use client';

import React from 'react';
import dynamic from 'next/dynamic';

import { generateDiagram, getOfficeArtifactProxyPath } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { DiagramGenerateResponse, DiagramType, OfficeJobDetail, OfficeSample } from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';
import { StepSection } from '@/components/office-tools/step-section';
import { UsageGuide } from '@/components/office-tools/usage-guide';
import { useOfficeWorkspaceSelection } from '@/components/office-tools/workspace-context';

const USAGE_WAYS = [
  { badge: '① 예제', title: '예제로 시작', detail: '아래 예제를 누르면 설명이 채워지고 곧바로 다이어그램이 그려집니다.' },
  { badge: '② 유형', title: '유형 선택', detail: '플로우·시퀀스·상태·간트 중 목적에 맞는 유형을 고릅니다.' },
  { badge: '③ 서술', title: '서술형 입력', detail: '"수집 -> 정제 -> 발행"처럼 단계·관계를 자연어로 적습니다.' },
];

// 유형별 "이렇게 입력해 보세요" 예시. 칩을 누르면 설명란에 채워진다.
const DESCRIPTION_EXAMPLES: Record<DiagramType, string[]> = {
  flowchart: ['수집 -> 정제 -> 발행', '주문 -> 결제 -> 배송 -> 완료'],
  sequence: ['사용자 -> 서버: 요청\n서버 -> DB: 조회\nDB -> 서버: 결과', '클라이언트 -> API: 로그인\nAPI -> 클라이언트: 토큰'],
  state: ['대기\n진행\n완료', '접수\n검토\n승인\n반려'],
  gantt: ['설계 | 2026-03-02 | 5d\n개발 | 2026-03-09 | 10d\n테스트 | 2026-03-19 | 5d'],
};

// mermaid 렌더는 SSR 비호환이라 미리보기를 클라이언트 전용 dynamic import 로 로드한다.
const DiagramPreview = dynamic(
  () => import('@/components/office-tools/diagram-preview').then((mod) => mod.DiagramPreview),
  { ssr: false, loading: () => <p className="text-sm text-ink-3">미리보기 로딩 중…</p> },
);

const DIAGRAM_STEPS: ProcessStep[] = [
  { label: '설명 입력', detail: '단계·관계를 자연어로 작성' },
  { label: 'AI 제안 / 규칙', detail: 'LLM 연결이 있으면 제안, 없으면 규칙 생성' },
  { label: '서버 검증', detail: 'script·click 등 금지 지시어 차단' },
  { label: '브라우저 렌더', detail: 'Mermaid strict 모드로 그리기' },
  { label: '산출물', detail: '.mmd·SVG·PNG 다운로드' },
];

const DIAGRAM_TYPES: { value: DiagramType; label: string; hint: string }[] = [
  { value: 'flowchart', label: '플로우차트', hint: '단계를 화살표(->)나 줄바꿈으로 구분하세요.' },
  { value: 'sequence', label: '시퀀스', hint: '"보낸이 -> 받는이: 메시지" 형식이면 그대로 반영됩니다.' },
  { value: 'state', label: '상태', hint: '상태 이름을 줄 단위로 나열하세요.' },
  { value: 'gantt', label: '간트', hint: '규칙 기반은 "업무명 | YYYY-MM-DD | 5d" 행이 필요합니다.' },
];

const MANIFEST_ARTIFACT_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/artifacts\/[A-Za-z0-9-][A-Za-z0-9._-]*$/;
const BUNDLE_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/bundle$/;

function isDiagramType(value: unknown): value is DiagramType {
  return DIAGRAM_TYPES.some((type) => type.value === value);
}

function isAbortError(cause: unknown) {
  return typeof cause === 'object' && cause !== null && 'name' in cause && cause.name === 'AbortError';
}

function workspaceDiagramResult(job: OfficeJobDetail): DiagramGenerateResponse | null {
  if (job.service !== 'diagram' || job.status !== 'completed') return null;

  const detail = job as unknown as Record<string, unknown>;
  const title = detail.title;
  const diagramType = detail.diagram_type;
  const mermaid = detail.mermaid;
  const llmUsed = detail.llm_used;
  const previewUrl = detail.preview_url;
  const bundleUrl = detail.bundle_url;

  if (
    typeof title !== 'string' ||
    !title.trim() ||
    !isDiagramType(diagramType) ||
    typeof mermaid !== 'string' ||
    !mermaid.trim() ||
    typeof llmUsed !== 'boolean' ||
    typeof previewUrl !== 'string' ||
    typeof bundleUrl !== 'string'
  ) {
    return null;
  }

  return {
    job_id: job.job_id,
    status: job.status,
    title,
    diagram_type: diagramType,
    mermaid,
    warnings: job.warnings,
    artifacts: job.artifacts,
    preview_url: previewUrl,
    bundle_url: bundleUrl,
    llm_used: llmUsed,
  };
}

function workspaceDiagramConfiguration(job: OfficeJobDetail) {
  const detail = job as unknown as Record<string, unknown>;
  const requestSummary = job.request_summary;
  const title = detail.title;
  const requestedType = requestSummary.diagram_type;
  const completedType = detail.diagram_type;
  const aiAssist = requestSummary.ai_assist;

  return {
    title: typeof title === 'string' && title.length <= 200 ? title : '',
    diagramType: isDiagramType(requestedType)
      ? requestedType
      : isDiagramType(completedType)
        ? completedType
        : 'flowchart',
    aiAssist: typeof aiAssist === 'boolean' ? aiAssist : true,
  };
}

function manifestArtifactLinks(artifacts: DiagramGenerateResponse['artifacts']) {
  return artifacts.flatMap((artifact) => {
    if (!MANIFEST_ARTIFACT_PATH.test(artifact.download_url)) return [];

    try {
      return [{ filename: artifact.filename, href: getOfficeArtifactProxyPath(artifact.download_url) }];
    } catch {
      return [];
    }
  });
}

function bundleProxyPath(bundleUrl: string) {
  if (!BUNDLE_PATH.test(bundleUrl)) return null;

  try {
    return getOfficeArtifactProxyPath(bundleUrl);
  } catch {
    return null;
  }
}

export function DiagramForm() {
  const workspaceSelection = useOfficeWorkspaceSelection();
  const [description, setDescription] = React.useState('');
  const [diagramType, setDiagramType] = React.useState<DiagramType>('flowchart');
  const [title, setTitle] = React.useState('');
  const [aiAssist, setAiAssist] = React.useState(true);
  const [result, setResult] = React.useState<DiagramGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [workspaceNotice, setWorkspaceNotice] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const requestController = React.useRef<AbortController | null>(null);
  const requestToken = React.useRef(0);
  const appliedWorkspaceSequence = React.useRef<number | null>(null);

  const abortCurrentRequest = React.useCallback(() => {
    requestToken.current += 1;
    requestController.current?.abort();
    requestController.current = null;
  }, []);

  const clearStaleOutput = React.useCallback(() => {
    abortCurrentRequest();
    setBusy(false);
    setResult(null);
    setError('');
    setWorkspaceNotice('');
  }, [abortCurrentRequest]);

  React.useEffect(() => {
    return () => {
      abortCurrentRequest();
    };
  }, [abortCurrentRequest]);

  React.useEffect(() => {
    if (!workspaceSelection || appliedWorkspaceSequence.current === workspaceSelection.sequence) return;

    appliedWorkspaceSequence.current = workspaceSelection.sequence;
    clearStaleOutput();
    setDescription('');

    if (workspaceSelection.job.service !== 'diagram') {
      setWorkspaceNotice('선택한 작업은 다이어그램 작업이 아닙니다.');
      return;
    }

    const configuration = workspaceDiagramConfiguration(workspaceSelection.job);
    setTitle(configuration.title);
    setDiagramType(configuration.diagramType);
    setAiAssist(configuration.aiAssist);

    if (workspaceSelection.mode === 'duplicate') {
      setWorkspaceNotice('설정만 복제했습니다. 설명을 다시 입력하세요.');
      return;
    }

    const storedResult = workspaceDiagramResult(workspaceSelection.job);
    if (!storedResult) {
      setWorkspaceNotice('완료된 다이어그램 결과를 열 수 없습니다.');
      return;
    }

    setResult(storedResult);
  }, [clearStaleOutput, workspaceSelection]);

  const activeHint = DIAGRAM_TYPES.find((item) => item.value === diagramType)?.hint ?? '';
  const engineNote = result ? (result.llm_used ? 'AI 제안 사용' : '규칙 기반') : undefined;

  // 실제 생성 — 상태가 아니라 명시 인자를 받아, 예제 클릭 직후(상태 반영 전)에도 그 값으로
  // 바로 실행할 수 있게 한다.
  async function runGenerate(input: { description: string; diagramType: DiagramType; title: string; aiAssist: boolean }) {
    if (!input.description.trim()) return;

    abortCurrentRequest();
    const token = requestToken.current + 1;
    requestToken.current = token;
    const controller = new AbortController();
    requestController.current = controller;
    setBusy(true);
    setResult(null);
    setError('');
    setWorkspaceNotice('');

    try {
      const response = await generateDiagram(
        { description: input.description, diagram_type: input.diagramType, title: input.title.trim(), ai_assist: input.aiAssist },
        getCsrfCookie(),
        controller.signal,
      );
      if (token !== requestToken.current) return;

      setResult(response);
    } catch (cause) {
      if (token !== requestToken.current || isAbortError(cause)) return;

      setResult(null);
      setError(cause instanceof Error ? cause.message : '다이어그램 생성에 실패했습니다.');
    } finally {
      if (token !== requestToken.current) return;

      if (requestController.current === controller) {
        requestController.current = null;
      }
      setBusy(false);
    }
  }

  function updateDescription(nextDescription: string) {
    clearStaleOutput();
    setDescription(nextDescription);
  }

  function updateDiagramType(nextDiagramType: DiagramType) {
    clearStaleOutput();
    setDiagramType(nextDiagramType);
  }

  function updateTitle(nextTitle: string) {
    clearStaleOutput();
    setTitle(nextTitle);
  }

  function updateAiAssist(nextAiAssist: boolean) {
    clearStaleOutput();
    setAiAssist(nextAiAssist);
  }

  function applySample(sample: OfficeSample) {
    const nextDescription = sample.content.trim();
    const nextType = isDiagramType(sample.hints.diagram_type) ? sample.hints.diagram_type : diagramType;
    const nextTitle = typeof sample.hints.title === 'string' ? sample.hints.title : title;
    clearStaleOutput();
    setDescription(nextDescription);
    setDiagramType(nextType);
    setTitle(nextTitle);
    // 예제는 채우기만 하지 않고 곧바로 생성까지 한다(원클릭 체험).
    void runGenerate({ description: nextDescription, diagramType: nextType, title: nextTitle, aiAssist });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runGenerate({ description, diagramType, title, aiAssist });
  }

  return (
    <div className="flex flex-col gap-6">
      <UsageGuide
        intro="설명을 입력하면 Mermaid 다이어그램으로 그려 줍니다. 세 가지 방법 중 하나로 시작하세요."
        ways={USAGE_WAYS}
        output="결과는 브라우저에서 렌더되고 .mmd·SVG·PNG 로 내려받을 수 있습니다."
      />
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="다이어그램 생성 폼">
        <StepSection n={1} title="무엇을 그릴지" hint="예제(클릭 시 바로 생성)를 고르거나 유형을 정합니다" done={!!result}>
          <SamplePicker tool="diagram" onPick={applySample} disabled={busy} />
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">유형</span>
            <select
              value={diagramType}
              onChange={(event) => {
                const nextDiagramType = event.target.value;
                if (isDiagramType(nextDiagramType)) updateDiagramType(nextDiagramType);
              }}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            >
              {DIAGRAM_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">제목 (선택)</span>
            <input
              type="text"
              value={title}
              onChange={(event) => updateTitle(event.target.value)}
              maxLength={200}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
              placeholder="업무 다이어그램"
            />
          </label>
        </StepSection>

        <StepSection n={2} title="설명 입력" hint="단계·관계를 자연어로" done={!!result}>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">설명</span>
            <textarea
              value={description}
              onChange={(event) => updateDescription(event.target.value)}
              required
              maxLength={30000}
              rows={8}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 font-mono text-ink-1"
              placeholder="수집 -> 정제 -> 발행"
            />
            <span className="text-xs text-ink-3">{activeHint}</span>
            <span className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-xs text-ink-3">예시</span>
              {DESCRIPTION_EXAMPLES[diagramType].map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => updateDescription(example)}
                  title={example}
                  className="rounded-full border border-ink-3/30 px-2.5 py-0.5 text-xs text-ink-2 transition hover:border-accent/50 hover:bg-accent-soft"
                >
                  {example.split('\n')[0]}
                  {example.includes('\n') ? ' …' : ''}
                </button>
              ))}
            </span>
          </label>

          <label className="flex items-center gap-2 text-sm text-ink-1">
            <input type="checkbox" checked={aiAssist} onChange={(event) => updateAiAssist(event.target.checked)} />
            <span>AI 보조 (활성 LLM 연결이 없으면 규칙 기반으로 생성)</span>
          </label>
        </StepSection>

        <StepSection n={3} title="생성" hint="다이어그램을 만들고 내려받습니다" done={!!result}>
          <button
            type="submit"
            disabled={busy || !description.trim()}
            className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? '생성 중…' : '다이어그램 생성'}
          </button>
        </StepSection>
      </form>

      <ProcessSteps steps={DIAGRAM_STEPS} done={!!result} engineNote={engineNote} />

      {workspaceNotice ? (
        <p className="rounded-md border border-ink-3/25 bg-ink-3/5 px-4 py-3 text-sm text-ink-2" role="status">
          {workspaceNotice}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
          {error}
        </p>
      ) : null}

      {result ? <DiagramResult result={result} /> : null}
    </div>
  );
}

function DiagramResult({ result }: { result: DiagramGenerateResponse }) {
  const artifacts = manifestArtifactLinks(result.artifacts);
  const bundleHref = bundleProxyPath(result.bundle_url);

  return (
    <section className="flex flex-col gap-3" data-testid="diagram-result">
      {result.warnings.length > 0 ? (
        <ul className="rounded-md border border-amber-400/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <DiagramPreview source={result.mermaid} title={result.title} />
      {artifacts.length > 0 || bundleHref ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-3">
          <span className="font-medium text-ink-2">manifest 산출물</span>
          {artifacts.map((artifact) => (
            <a key={artifact.href} href={artifact.href} className="text-accent underline-offset-2 hover:underline">
              {artifact.filename}
            </a>
          ))}
          {bundleHref ? (
            <a href={bundleHref} className="text-accent underline-offset-2 hover:underline">
              번들 다운로드
            </a>
          ) : null}
        </div>
      ) : null}
      <details className="text-sm">
        <summary className="cursor-pointer text-ink-3">Mermaid 소스 보기</summary>
        <pre className="mt-2 overflow-x-auto rounded-md border border-ink-3/30 bg-ink-3/5 p-3 text-xs text-ink-1">
          {result.mermaid}
        </pre>
      </details>
    </section>
  );
}
