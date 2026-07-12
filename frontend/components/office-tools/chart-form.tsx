'use client';

import React from 'react';
import dynamic from 'next/dynamic';

import { generateChart, inspectChartData } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { ChartGenerateResponse, ChartInspectResponse, ChartType, OfficeSample } from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';
import { StepSection } from '@/components/office-tools/step-section';
import { DataInput, type DataInputMode } from '@/components/office-tools/data-input';
import { UsageGuide } from '@/components/office-tools/usage-guide';

const USAGE_WAYS = [
  { badge: '① 예제', title: '예제로 시작', detail: '아래 예제를 누르면 데이터가 채워지고 바로 차트가 생성됩니다.' },
  { badge: '② 데이터', title: '파일 또는 정형 텍스트', detail: 'CSV·엑셀 파일을 올리거나, 표 형식(CSV) 텍스트를 직접 붙여넣습니다.' },
  { badge: '③ 목적', title: '목적 문장(서술형)', detail: '"지역별 매출을 크기순으로 비교"처럼 원하는 바를 적으면 유형을 추천합니다.' },
];

const PROMPT_EXAMPLES = [
  '지역별 매출을 크기순으로 비교',
  '월별 추세를 선으로 보여줘',
  '채널별 구성비를 파이로',
  '광고비와 매출의 상관',
];

const CSV_PLACEHOLDER = 'region,sales\n서울,1240\n부산,860\n대구,540';

// echarts 렌더는 SSR 비호환이라 미리보기를 클라이언트 전용 dynamic import 로 로드한다.
const ChartPreview = dynamic(
  () => import('@/components/office-tools/chart-preview').then((mod) => mod.ChartPreview),
  { ssr: false, loading: () => <p className="text-sm text-ink-3">미리보기 로딩 중…</p> },
);

const CHART_STEPS: ProcessStep[] = [
  { label: '데이터 업로드', detail: '.csv·.xlsx·.json' },
  { label: '프로파일 점검', detail: '행·열·유형·결측 확인' },
  { label: 'AI / 규칙 스펙', detail: '허용된 ChartSpec 만 제안' },
  { label: 'pandas 집계', detail: '서버에서 실제 계산' },
  { label: 'ECharts 렌더', detail: '브라우저에서 그리기' },
  { label: '산출물', detail: 'option·집계 CSV·zip' },
];

const CHART_TYPES: { value: ChartType | ''; label: string }[] = [
  { value: '', label: '자동 (목적 문장/데이터로 추천)' },
  { value: 'bar', label: '막대' },
  { value: 'line', label: '선형' },
  { value: 'area', label: '영역' },
  { value: 'scatter', label: '산점도' },
  { value: 'pie', label: '파이' },
  { value: 'histogram', label: '히스토그램' },
];

export function ChartForm() {
  const [inputMode, setInputMode] = React.useState<DataInputMode>('file');
  const [dataFile, setDataFile] = React.useState<File | null>(null);
  const [dataText, setDataText] = React.useState('');
  const [prompt, setPrompt] = React.useState('');
  const [chartType, setChartType] = React.useState<ChartType | ''>('');
  const [aiAssist, setAiAssist] = React.useState(true);
  const [profile, setProfile] = React.useState<ChartInspectResponse | null>(null);
  const [result, setResult] = React.useState<ChartGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const hasData = inputMode === 'text' ? !!dataText.trim() : !!dataFile;

  function effectiveFile(): File | null {
    if (inputMode === 'text') {
      return dataText.trim() ? new File([dataText], 'data.csv', { type: 'text/csv' }) : null;
    }
    return dataFile;
  }

  const engineNote = result
    ? result.warnings.some((warning) => warning.includes('규칙'))
      ? '규칙 기반 폴백'
      : aiAssist
        ? 'AI 제안 사용'
        : '규칙 기반'
    : undefined;

  function applySample(sample: OfficeSample) {
    // 예제는 텍스트 모드로 채워, 사용자가 데이터 형식을 눈으로 확인하게 한다.
    setInputMode('text');
    setDataText(sample.content);
    setDataFile(null);
    setProfile(null);
    setResult(null);
    const nextPrompt = typeof sample.hints.prompt === 'string' ? sample.hints.prompt : prompt;
    const nextType = (typeof sample.hints.chart_type === 'string' ? sample.hints.chart_type : chartType) as ChartType | '';
    setPrompt(nextPrompt);
    setChartType(nextType);
    setError('');
    // 예제는 채우기만 하지 않고 곧바로 생성까지 한다(원클릭 체험).
    const file = new File([sample.content], 'data.csv', { type: 'text/csv' });
    runGenerate({ file, prompt: nextPrompt, aiAssist, chartType: nextType });
  }

  async function handleInspect() {
    const file = effectiveFile();
    if (!file || busy) return;
    setBusy(true);
    setError('');
    try {
      setProfile(await inspectChartData(file, getCsrfCookie()));
    } catch (err) {
      setProfile(null);
      setError(err instanceof Error ? err.message : '데이터 미리보기에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  }

  // 실제 생성 — 상태가 아니라 명시 인자를 받아, 예제 클릭 직후에도 그 값으로 바로 실행한다.
  async function runGenerate(input: { file: File | null; prompt: string; aiAssist: boolean; chartType: ChartType | '' }) {
    if (busy || !input.file) return;
    setBusy(true);
    setError('');
    try {
      const response = await generateChart(
        { dataFile: input.file, prompt: input.prompt.trim(), aiAssist: input.aiAssist, chartType: input.chartType },
        getCsrfCookie(),
      );
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : '차트 생성에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    runGenerate({ file: effectiveFile(), prompt, aiAssist, chartType });
  }

  return (
    <div className="flex flex-col gap-6">
      <UsageGuide
        intro="데이터를 올리면 목적에 맞는 차트로 시각화합니다. 세 가지 방법 중 하나로 시작하세요."
        ways={USAGE_WAYS}
        output="결과는 실서비스급 ECharts 로 그려지고 option·집계 CSV·zip 으로 내려받을 수 있습니다."
      />
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="차트 생성 폼">
        <StepSection n={1} title="데이터 입력" hint="예제(클릭 시 바로 생성)·파일·직접 입력" done={!!result}>
          <SamplePicker tool="chart" onPick={applySample} disabled={busy} />
          <DataInput
            mode={inputMode}
            onModeChange={setInputMode}
            fileLabel="데이터 파일 (.csv / .xlsx / .json)"
            accept=".csv,.xlsx,.xlsm,.json,text/csv,application/json"
            file={dataFile}
            onFileChange={(next) => {
              setDataFile(next);
              setProfile(null);
            }}
            text={dataText}
            onTextChange={(next) => {
              setDataText(next);
              setProfile(null);
            }}
            textPlaceholder={CSV_PLACEHOLDER}
            textHint="CSV·표 형식으로 직접 붙여넣습니다(첫 줄은 열 이름)."
          />
        </StepSection>

        <StepSection n={2} title="목적과 유형" hint="어떻게 보여줄지 정합니다" done={!!result}>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">목적 문장 (선택)</span>
            <input
              type="text"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={300}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
              placeholder="예: 지역별 매출을 크기순으로 비교"
            />
            <span className="flex flex-wrap gap-1.5 pt-1">
              <span className="text-xs text-ink-3">예시</span>
              {PROMPT_EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setPrompt(example)}
                  className="rounded-full border border-ink-3/30 px-2.5 py-0.5 text-xs text-ink-2 transition hover:border-accent/50 hover:bg-accent-soft"
                >
                  {example}
                </button>
              ))}
            </span>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-ink-1">차트 유형</span>
            <select
              value={chartType}
              onChange={(event) => setChartType(event.target.value as ChartType | '')}
              className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
            >
              {CHART_TYPES.map((item) => (
                <option key={item.value || 'auto'} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-sm text-ink-1">
            <input type="checkbox" checked={aiAssist} onChange={(event) => setAiAssist(event.target.checked)} />
            <span>AI 보조 (활성 LLM 연결이 없으면 규칙 기반으로 추천)</span>
          </label>
        </StepSection>

        <StepSection n={3} title="생성" hint="차트를 만들고 산출물을 내려받습니다" done={!!result}>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleInspect}
              disabled={busy || !hasData}
              className="rounded-md border border-ink-3/40 px-4 py-2 text-sm font-medium text-ink-1 hover:bg-ink-3/10 disabled:opacity-50"
            >
              데이터 미리보기
            </button>
            <button
              type="submit"
              disabled={busy || !hasData}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
            >
              {busy ? '처리 중…' : '차트 생성'}
            </button>
          </div>
        </StepSection>
      </form>

      <ProcessSteps steps={CHART_STEPS} done={!!result} engineNote={engineNote} />

      {error ? (
        <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
          {error}
        </p>
      ) : null}

      {profile ? <DataProfile profile={profile} /> : null}
      {result ? <ChartResult result={result} /> : null}
    </div>
  );
}

function DataProfile({ profile }: { profile: ChartInspectResponse }) {
  return (
    <section className="flex flex-col gap-2 text-sm" data-testid="chart-profile">
      <p className="text-ink-1">
        행 {profile.row_count.toLocaleString()}개 · 열 {profile.column_count}개
      </p>
      <div className="overflow-x-auto rounded-md border border-ink-3/30">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-ink-3/5 text-ink-3">
            <tr>
              <th className="px-3 py-2">열</th>
              <th className="px-3 py-2">유형</th>
              <th className="px-3 py-2">결측</th>
              <th className="px-3 py-2">고유값</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map((column) => (
              <tr key={column.name} className="border-t border-ink-3/20 text-ink-1">
                <td className="px-3 py-1.5 font-medium">{column.name}</td>
                <td className="px-3 py-1.5">{column.numeric ? '숫자' : column.datetime ? '날짜' : '범주'}</td>
                <td className="px-3 py-1.5">{column.null}</td>
                <td className="px-3 py-1.5">{column.unique}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ChartResult({ result }: { result: ChartGenerateResponse }) {
  return (
    <section className="flex flex-col gap-3" data-testid="chart-result">
      {result.warnings.length > 0 ? (
        <ul className="rounded-md border border-amber-400/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      <ChartPreview option={result.echarts_option} title={result.title} />
      <div className="flex flex-wrap gap-3 text-sm">
        <a
          href={`/api/frontend/office-tools/jobs/${result.job_id}/artifacts/echarts_option.json`}
          download
          className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
        >
          ECharts option(JSON)
        </a>
        <a
          href={`/api/frontend/office-tools/jobs/${result.job_id}/artifacts/chart_data.csv`}
          download
          className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
        >
          집계 데이터(CSV)
        </a>
        <a
          href={`/api/frontend/office-tools/jobs/${result.job_id}/bundle`}
          download
          className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
        >
          전체 번들(zip)
        </a>
      </div>
    </section>
  );
}
