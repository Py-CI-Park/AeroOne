'use client';

import React from 'react';
import dynamic from 'next/dynamic';

import { generateDiagram } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { DiagramGenerateResponse, DiagramType, OfficeSample } from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';

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

export function DiagramForm() {
  const [description, setDescription] = React.useState('');
  const [diagramType, setDiagramType] = React.useState<DiagramType>('flowchart');
  const [title, setTitle] = React.useState('');
  const [aiAssist, setAiAssist] = React.useState(true);
  const [result, setResult] = React.useState<DiagramGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const activeHint = DIAGRAM_TYPES.find((item) => item.value === diagramType)?.hint ?? '';
  const engineNote = result
    ? result.warnings.some((warning) => warning.includes('규칙'))
      ? '규칙 기반 폴백'
      : aiAssist
        ? 'AI 제안 사용'
        : '규칙 기반'
    : undefined;

  function applySample(sample: OfficeSample) {
    setDescription(sample.content.trim());
    if (typeof sample.hints.diagram_type === 'string') setDiagramType(sample.hints.diagram_type as DiagramType);
    if (typeof sample.hints.title === 'string') setTitle(sample.hints.title);
    setResult(null);
    setError('');
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !description.trim()) return;
    setBusy(true);
    setError('');
    try {
      const response = await generateDiagram(
        { description, diagram_type: diagramType, title: title.trim(), ai_assist: aiAssist },
        getCsrfCookie(),
      );
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : '다이어그램 생성에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="다이어그램 생성 폼">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">제목 (선택)</span>
          <input
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            placeholder="업무 다이어그램"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">설명</span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            required
            maxLength={30000}
            rows={8}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 font-mono text-ink-1"
            placeholder="수집 -> 정제 -> 발행"
          />
          <span className="text-xs text-ink-3">{activeHint}</span>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">유형</span>
          <select
            value={diagramType}
            onChange={(event) => setDiagramType(event.target.value as DiagramType)}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          >
            {DIAGRAM_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm text-ink-1">
          <input type="checkbox" checked={aiAssist} onChange={(event) => setAiAssist(event.target.checked)} />
          <span>AI 보조 (활성 LLM 연결이 없으면 규칙 기반으로 생성)</span>
        </label>

        <SamplePicker tool="diagram" onPick={applySample} disabled={busy} />

        <button
          type="submit"
          disabled={busy || !description.trim()}
          className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? '생성 중…' : '다이어그램 생성'}
        </button>
      </form>

      <ProcessSteps steps={DIAGRAM_STEPS} done={!!result} engineNote={engineNote} />

      {error ? (
        <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <section className="flex flex-col gap-3" data-testid="diagram-result">
          {result.warnings.length > 0 ? (
            <ul className="rounded-md border border-amber-400/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : null}
          <DiagramPreview source={result.mermaid} title={result.title} />
          <details className="text-sm">
            <summary className="cursor-pointer text-ink-3">Mermaid 소스 보기</summary>
            <pre className="mt-2 overflow-x-auto rounded-md border border-ink-3/30 bg-ink-3/5 p-3 text-xs text-ink-1">
              {result.mermaid}
            </pre>
          </details>
        </section>
      ) : null}
    </div>
  );
}
