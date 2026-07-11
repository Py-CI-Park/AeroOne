'use client';

import React from 'react';
import dynamic from 'next/dynamic';

import { generateChart, inspectChartData } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type { ChartGenerateResponse, ChartInspectResponse, ChartType } from '@/lib/types';

// echarts 렌더는 SSR 비호환이라 미리보기를 클라이언트 전용 dynamic import 로 로드한다.
const ChartPreview = dynamic(
  () => import('@/components/office-tools/chart-preview').then((mod) => mod.ChartPreview),
  { ssr: false, loading: () => <p className="text-sm text-ink-3">미리보기 로딩 중…</p> },
);

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
  const [dataFile, setDataFile] = React.useState<File | null>(null);
  const [prompt, setPrompt] = React.useState('');
  const [chartType, setChartType] = React.useState<ChartType | ''>('');
  const [aiAssist, setAiAssist] = React.useState(true);
  const [profile, setProfile] = React.useState<ChartInspectResponse | null>(null);
  const [result, setResult] = React.useState<ChartGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  async function handleInspect() {
    if (!dataFile || busy) return;
    setBusy(true);
    setError('');
    try {
      setProfile(await inspectChartData(dataFile, getCsrfCookie()));
    } catch (err) {
      setProfile(null);
      setError(err instanceof Error ? err.message : '데이터 미리보기에 실패했습니다.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !dataFile) return;
    setBusy(true);
    setError('');
    try {
      const response = await generateChart(
        { dataFile, prompt: prompt.trim(), aiAssist, chartType },
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

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-label="차트 생성 폼">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-ink-1">데이터 파일 (.csv / .xlsx / .json)</span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,.json,text/csv,application/json"
            onChange={(event) => {
              setDataFile(event.target.files?.[0] ?? null);
              setProfile(null);
            }}
            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
          />
        </label>

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

        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleInspect}
            disabled={busy || !dataFile}
            className="rounded-md border border-ink-3/40 px-4 py-2 text-sm font-medium text-ink-1 hover:bg-ink-3/10 disabled:opacity-50"
          >
            데이터 미리보기
          </button>
          <button
            type="submit"
            disabled={busy || !dataFile}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-on hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? '처리 중…' : '차트 생성'}
          </button>
        </div>
      </form>

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
