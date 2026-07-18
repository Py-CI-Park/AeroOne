'use client';

import React from 'react';
import dynamic from 'next/dynamic';

import { generateChart, getOfficeArtifactProxyPath, inspectChartData } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';
import type {
  ChartAggregation,
  ChartGenerateResponse,
  ChartInspectResponse,
  ChartManualSpecInput,
  ChartOrientation,
  ChartSortMode,
  ChartType,
  OfficeArtifact,
  OfficeJobDetail,
  OfficeSample,
} from '@/lib/types';
import { ProcessSteps, type ProcessStep } from '@/components/office-tools/process-steps';
import { SamplePicker } from '@/components/office-tools/sample-picker';
import { StepSection } from '@/components/office-tools/step-section';
import { UsageGuide } from '@/components/office-tools/usage-guide';
import { ChartComposer, ChartFollowUp } from '@/components/office-tools/chart-composer';
import { useOfficeWorkspaceSelection } from '@/components/office-tools/workspace-context';

const USAGE_WAYS = [
  { badge: '① 예제', title: '예제로 시작', detail: '아래 예제를 누르면 데이터가 채워지고 바로 차트가 생성됩니다.' },
  { badge: '② 컴포저', title: '목적 문장 또는 데이터', detail: '위 입력창에 목적을 적거나 표 형식 데이터를 붙여넣고, 파일을 첨부해도 됩니다.' },
  { badge: '③ 후속 명령', title: '결과 다듬기', detail: '결과가 나오면 "상위 5개만"처럼 한 줄로 이어서 다듬을 수 있습니다.' },
];

const INSPECT_DEBOUNCE_MS = 400;

// echarts 렌더는 SSR 비호환이라 미리보기를 클라이언트 전용 dynamic import 로 로드한다.
const ChartPreview = dynamic(
  () => import('@/components/office-tools/chart-preview').then((mod) => mod.ChartPreview),
  { ssr: false, loading: () => <p className="text-sm text-ink-3">미리보기 로딩 중…</p> },
);

const CHART_STEPS: ProcessStep[] = [
  { label: '데이터 입력', detail: '문장·붙여넣기·파일·드래그' },
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
const CHART_AGGREGATIONS: { value: ChartAggregation; label: string }[] = [
  { value: 'none', label: '집계하지 않음' },
  { value: 'sum', label: '합계' },
  { value: 'mean', label: '평균' },
  { value: 'count', label: '개수' },
  { value: 'min', label: '최솟값' },
  { value: 'max', label: '최댓값' },
];

const CHART_SORT_MODES: { value: ChartSortMode; label: string }[] = [
  { value: 'none', label: '정렬 안 함' },
  { value: 'x_asc', label: 'X 오름차순' },
  { value: 'x_desc', label: 'X 내림차순' },
  { value: 'value_asc', label: '값 오름차순' },
  { value: 'value_desc', label: '값 내림차순' },
];

const CHART_ORIENTATIONS: { value: ChartOrientation; label: string }[] = [
  { value: 'vertical', label: '세로' },
  { value: 'horizontal', label: '가로' },
];

const MANIFEST_ARTIFACT_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/artifacts\/[A-Za-z0-9-][A-Za-z0-9._-]*$/;
const BUNDLE_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/bundle$/;
type ChartGenerationInput = {
  file: File | null;
  prompt: string;
  aiAssist: boolean;
  chartType: ChartType | '';
  manualSpec?: ChartManualSpecInput;
  manualSpecJson?: string;
  // 후속 명령 전용: 직전 성공 결과의 chart_spec. manualSpec 과 동시에 채우지 않는다(계약).
  previousSpec?: Record<string, unknown>;
};

type SafeChartConfig = Pick<ChartManualSpecInput, 'type' | 'aggregation' | 'stacked' | 'sort' | 'limit' | 'orientation'>;

export function ChartForm() {
  const workspaceSelection = useOfficeWorkspaceSelection();
  const [dataFile, setDataFile] = React.useState<File | null>(null);
  const [prompt, setPrompt] = React.useState('');
  const [chartType, setChartType] = React.useState<ChartType | ''>('');
  const [aiAssist, setAiAssist] = React.useState(true);
  const [profile, setProfile] = React.useState<ChartInspectResponse | null>(null);
  const [result, setResult] = React.useState<ChartGenerateResponse | null>(null);
  const [error, setError] = React.useState('');
  const [workspaceNotice, setWorkspaceNotice] = React.useState('');
  const [inspectBusy, setInspectBusy] = React.useState(false);
  const [generateBusy, setGenerateBusy] = React.useState(false);
  const [optionsOpen, setOptionsOpen] = React.useState(false);
  const [advancedEnabled, setAdvancedEnabled] = React.useState(false);
  const [manualX, setManualX] = React.useState('');
  const [manualY, setManualY] = React.useState<string[]>([]);
  const [manualGroup, setManualGroup] = React.useState('');
  const [manualAggregation, setManualAggregation] = React.useState<ChartAggregation>('none');
  const [manualStacked, setManualStacked] = React.useState(false);
  const [manualSort, setManualSort] = React.useState<ChartSortMode>('none');
  const [manualLimit, setManualLimit] = React.useState('30');
  const [manualOrientation, setManualOrientation] = React.useState<ChartOrientation>('vertical');
  const [pendingDuplicateConfig, setPendingDuplicateConfig] = React.useState<SafeChartConfig | null>(null);
  const inspectControllerRef = React.useRef<AbortController | null>(null);
  const generateControllerRef = React.useRef<AbortController | null>(null);
  const inspectTokenRef = React.useRef(0);
  const generateTokenRef = React.useRef(0);

  const hasData = !!dataFile;
  const busy = inspectBusy || generateBusy;
  const profiledColumns = profile ? uniqueProfileColumns(profile) : [];

  function resetManualSelections() {
    setAdvancedEnabled(false);
    setManualX('');
    setManualY([]);
    setManualGroup('');
    setManualAggregation('none');
    setManualStacked(false);
    setManualSort('none');
    setManualLimit('30');
    setManualOrientation('vertical');
  }

  function abortInspect() {
    inspectTokenRef.current += 1;
    inspectControllerRef.current?.abort();
    inspectControllerRef.current = null;
    setInspectBusy(false);
  }

  function abortGenerate() {
    generateTokenRef.current += 1;
    generateControllerRef.current?.abort();
    generateControllerRef.current = null;
    setGenerateBusy(false);
  }

  function clearForDataChange(keepPendingDuplicateConfig = false) {
    abortInspect();
    abortGenerate();
    setProfile(null);
    setResult(null);
    setError('');
    setWorkspaceNotice('');
    if (!keepPendingDuplicateConfig) setPendingDuplicateConfig(null);
    resetManualSelections();
  }

  function clearForOptionChange() {
    abortGenerate();
    setResult(null);
    setError('');
    setWorkspaceNotice('');
    setPendingDuplicateConfig(null);
  }

  React.useEffect(() => {
    return () => {
      inspectTokenRef.current += 1;
      generateTokenRef.current += 1;
      inspectControllerRef.current?.abort();
      generateControllerRef.current?.abort();
      inspectControllerRef.current = null;
      generateControllerRef.current = null;
    };
  }, []);

  React.useEffect(() => {
    if (!workspaceSelection) return;

    abortInspect();
    abortGenerate();
    setDataFile(null);
    setPrompt('');
    setProfile(null);
    setResult(null);
    setError('');
    setWorkspaceNotice('');
    setPendingDuplicateConfig(null);
    resetManualSelections();

    const job = workspaceSelection.job;
    if (!isRecord(job) || job.service !== 'chart') return;

    const config = chartConfigFromSpec(job.chart_spec);
    if (workspaceSelection.mode === 'reopen') {
      const restored = chartResultFromJob(job);
      if (!restored) {
        setError('완료된 차트 결과를 검증하지 못해 다시 열 수 없습니다.');
        return;
      }
      setChartType(config?.type ?? '');
      setResult(restored);
      return;
    }

    if (workspaceSelection.mode === 'duplicate') {
      if (!config) {
        setError('차트 설정을 검증하지 못해 복제할 수 없습니다.');
        return;
      }
      setChartType(config.type ?? '');
      setPendingDuplicateConfig(config);
      setOptionsOpen(true);
      setWorkspaceNotice('원본 데이터는 복제되지 않습니다. 차트를 만들려면 원본 데이터를 다시 첨부하세요.');
    }
  }, [workspaceSelection?.sequence]);

  // 데이터가 확정(첨부)되면 디바운스 후 자동으로 프로파일을 점검한다(기존 abort/token 패턴 재사용).
  React.useEffect(() => {
    if (!dataFile || generateControllerRef.current) return;
    const timer = setTimeout(() => {
      void handleInspect();
    }, INSPECT_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataFile]);

  const engineNote = result ? (result.llm_used ? 'AI 제안 사용' : '규칙 기반') : undefined;

  function applySample(sample: OfficeSample) {
    clearForDataChange();
    const file = new File([sample.content], 'data.csv', { type: 'text/csv' });
    setDataFile(file);
    const nextPrompt = typeof sample.hints.prompt === 'string' ? sample.hints.prompt : prompt;
    const nextType = isChartType(sample.hints.chart_type) ? sample.hints.chart_type : chartType;
    // 다계열(누적/그룹/다계열선) 예제는 완성된 ChartSpec 을 그대로 넘겨 결정적으로 렌더한다.
    const manualSpecJson = isRecord(sample.hints.manual_spec) ? JSON.stringify(sample.hints.manual_spec) : '';
    setPrompt(nextPrompt);
    setChartType(nextType);
    // 예제는 채우기만 하지 않고 곧바로 생성까지 한다(원클릭 체험).
    runGenerate({ file, prompt: nextPrompt, aiAssist, chartType: nextType, manualSpecJson });
  }

  async function handleInspect() {
    const file = dataFile;
    if (!file || inspectControllerRef.current) return;

    const controller = new AbortController();
    const token = ++inspectTokenRef.current;
    inspectControllerRef.current = controller;
    setInspectBusy(true);
    setError('');
    try {
      const response = await inspectChartData(file, getCsrfCookie(), controller.signal);
      if (inspectTokenRef.current !== token || inspectControllerRef.current !== controller) return;
      setProfile(response);
      if (pendingDuplicateConfig) {
        setAdvancedEnabled(true);
        setOptionsOpen(true);
        setManualAggregation(pendingDuplicateConfig.aggregation ?? 'none');
        setManualStacked(pendingDuplicateConfig.stacked ?? false);
        setManualSort(pendingDuplicateConfig.sort ?? 'none');
        setManualLimit(String(pendingDuplicateConfig.limit ?? 30));
        setManualOrientation(pendingDuplicateConfig.orientation ?? 'vertical');
        setPendingDuplicateConfig(null);
      }
    } catch (err) {
      if (inspectTokenRef.current !== token || inspectControllerRef.current !== controller || isAbortError(err)) return;
      setProfile(null);
      setError(err instanceof Error ? err.message : '데이터 미리보기에 실패했습니다.');
    } finally {
      if (inspectTokenRef.current === token && inspectControllerRef.current === controller) {
        inspectControllerRef.current = null;
        setInspectBusy(false);
      }
    }
  }

  // 실제 생성 — 상태가 아니라 명시 인자를 받아, 예제 클릭 직후(상태 반영 전)에도 그 값으로 바로 실행한다.
  async function runGenerate(input: ChartGenerationInput) {
    if (!input.file || generateControllerRef.current) return;

    const controller = new AbortController();
    const token = ++generateTokenRef.current;
    generateControllerRef.current = controller;
    setGenerateBusy(true);
    setError('');
    const payload = {
      dataFile: input.file,
      prompt: input.prompt.trim(),
      aiAssist: input.aiAssist,
      chartType: input.chartType,
      ...(input.manualSpec ? { manualSpec: input.manualSpec } : {}),
      ...(input.manualSpecJson ? { manualSpecJson: input.manualSpecJson } : {}),
      ...(input.previousSpec ? { previousSpec: input.previousSpec } : {}),
    };
    try {
      const response = await generateChart(payload, getCsrfCookie(), controller.signal);
      if (generateTokenRef.current !== token || generateControllerRef.current !== controller) return;
      setResult(response);
    } catch (err) {
      if (generateTokenRef.current !== token || generateControllerRef.current !== controller || isAbortError(err)) return;
      // 후속 명령(refine) 실패는 직전 결과를 보존한다 — 실패 1회로 다듬기 루프가 끊기지 않게.
      if (!input.previousSpec) setResult(null);
      setError(err instanceof Error ? err.message : '차트 생성에 실패했습니다.');
    } finally {
      if (generateTokenRef.current === token && generateControllerRef.current === controller) {
        generateControllerRef.current = null;
        setGenerateBusy(false);
      }
    }
  }

  function buildManualSpec(): ChartManualSpecInput | null {
    if (!profile) {
      setError('고급 설정을 사용하려면 먼저 데이터를 첨부해 프로파일을 확보하세요.');
      return null;
    }

    const availableColumns = new Set(profiledColumns.map((column) => column.name));
    const y = Array.from(new Set(manualY));
    const type = chartType || 'bar';
    const limit = Number(manualLimit);
    if ((manualX && !availableColumns.has(manualX)) || y.some((column) => !availableColumns.has(column)) || (manualGroup && !availableColumns.has(manualGroup))) {
      setError('프로파일에 있는 열만 고급 설정에 사용할 수 있습니다.');
      return null;
    }
    if (manualX && (manualY.includes(manualX) || manualGroup === manualX)) {
      setError('X 축 열은 Y 축 또는 그룹 열과 중복될 수 없습니다.');
      return null;
    }
    if (manualGroup && manualY.includes(manualGroup)) {
      setError('그룹 열은 Y 축 열과 중복될 수 없습니다.');
      return null;
    }
    if (type !== 'histogram' && !manualX) {
      setError('선택한 차트 유형에는 X 축 열이 필요합니다.');
      return null;
    }
    if (type === 'scatter' && y.length !== 1) {
      setError('산점도에는 정확히 하나의 Y 축 열이 필요합니다.');
      return null;
    }
    if (type === 'histogram' && y.length !== 1) {
      setError('히스토그램에는 정확히 하나의 Y 축 열이 필요합니다.');
      return null;
    }
    if (manualAggregation !== 'count' && y.length === 0) {
      setError('선택한 집계에는 하나 이상의 Y 축 열이 필요합니다.');
      return null;
    }
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      setError('표시 행 수는 1에서 100 사이의 정수여야 합니다.');
      return null;
    }

    return {
      ...(chartType ? { type: chartType } : {}),
      x: manualX || null,
      y,
      group: manualGroup || null,
      aggregation: manualAggregation,
      stacked: manualStacked,
      sort: manualSort,
      limit,
      orientation: manualOrientation,
    };
  }

  function handleGenerateClick() {
    if (advancedEnabled) {
      const manualSpec = buildManualSpec();
      if (!manualSpec) return;
      runGenerate({ file: dataFile, prompt, aiAssist, chartType, manualSpec });
      return;
    }
    runGenerate({ file: dataFile, prompt, aiAssist, chartType });
  }

  function handleFollowUp(followUpPrompt: string) {
    if (!dataFile) {
      setError('후속 명령을 실행하려면 원본 데이터를 다시 첨부하세요.');
      return;
    }
    if (!result || !isJsonRecord(result.chart_spec)) {
      setError('직전 결과를 확인할 수 없어 후속 명령을 실행할 수 없습니다.');
      return;
    }
    // 우선순위 계약: manualSpec > previousSpec+prompt > 신규 생성. 후속 명령은 manualSpec 을 보내지 않는다.
    runGenerate({ file: dataFile, prompt: followUpPrompt, aiAssist, chartType, previousSpec: result.chart_spec });
  }

  function handleManualX(next: string) {
    clearForOptionChange();
    setManualX(next);
    setManualY((current) => current.filter((column) => column !== next));
    if (manualGroup === next) setManualGroup('');
  }

  function handleManualY(next: string, checked: boolean) {
    clearForOptionChange();
    setManualY((current) => {
      if (!checked) return current.filter((column) => column !== next);
      if (next === manualX || next === manualGroup || current.includes(next)) return current;
      return [...current, next];
    });
  }

  function handleManualGroup(next: string) {
    clearForOptionChange();
    setManualGroup(next);
    setManualY((current) => current.filter((column) => column !== next));
    if (manualX === next) setManualX('');
  }

  return (
    <div className="flex flex-col gap-6">
      <UsageGuide
        intro="목적 문장을 적거나 표 데이터를 붙여넣으면 목적에 맞는 차트로 시각화합니다."
        ways={USAGE_WAYS}
        output="결과는 실서비스급 ECharts 로 그려지고 option·집계 CSV·zip 으로 내려받을 수 있습니다."
      />
      <div className="flex flex-col gap-4" aria-label="차트 생성 폼">
        <StepSection n={1} title="데이터 입력" hint="예제(클릭 시 바로 생성)·컴포저로 시작" done={!!result}>
          <SamplePicker tool="chart" onPick={applySample} disabled={busy} />
          <ChartComposer
            file={dataFile}
            onFileChange={(next) => {
              setDataFile(next);
              clearForDataChange(true);
            }}
            promptText={prompt}
            onPromptChange={(next) => {
              setPrompt(next);
              clearForOptionChange();
            }}
            profile={profile}
            inspectBusy={inspectBusy}
            busy={generateBusy}
            onSubmit={handleGenerateClick}
            submitDisabled={!hasData}
          />
        </StepSection>

        <div className="rounded-lg border border-ink-3/20">
          <button
            type="button"
            onClick={() => setOptionsOpen((open) => !open)}
            className="flex w-full items-center justify-between px-4 py-2 text-sm font-medium text-ink-1"
            aria-expanded={optionsOpen}
            aria-controls="chart-options-panel"
          >
            <span>옵션</span>
            <span className="text-xs text-ink-3">{optionsOpen ? '접기' : '펼치기'}</span>
          </button>
          {optionsOpen ? (
            <div id="chart-options-panel" className="flex flex-col gap-4 border-t border-ink-3/20 px-4 py-4">
              <label className="flex flex-col gap-1 text-sm">
                <span className="font-medium text-ink-1">차트 유형</span>
                <select
                  value={chartType}
                  onChange={(event) => {
                    clearForOptionChange();
                    setChartType(event.target.value as ChartType | '');
                  }}
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
                <input
                  type="checkbox"
                  checked={aiAssist}
                  onChange={(event) => {
                    clearForOptionChange();
                    setAiAssist(event.target.checked);
                  }}
                />
                <span>AI 보조 (활성 LLM 연결이 없으면 규칙 기반으로 추천)</span>
              </label>

              {profile ? (
                <div className="flex flex-col gap-3 rounded-lg border border-ink-3/20 bg-surface-sunken/40 px-4 py-3" data-testid="chart-advanced-controls">
                  <label className="flex items-center gap-2 text-sm font-medium text-ink-1">
                    <input
                      type="checkbox"
                      checked={advancedEnabled}
                      onChange={(event) => {
                        clearForOptionChange();
                        setAdvancedEnabled(event.target.checked);
                      }}
                    />
                    고급 차트 설정 사용
                  </label>
                  {advancedEnabled ? (
                    <>
                      <p className="text-xs text-ink-3">프로파일에서 확인한 열만 선택합니다. 최종 유효성 검사는 서버가 수행합니다.</p>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">X 축 열</span>
                          <select
                            value={manualX}
                            onChange={(event) => handleManualX(event.target.value)}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          >
                            <option value="">선택하세요</option>
                            {profiledColumns.map((column) => (
                              <option key={column.name} value={column.name} disabled={manualY.includes(column.name) || manualGroup === column.name}>
                                {column.name} ({column.numeric ? '숫자' : column.datetime ? '날짜' : '범주'})
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">그룹 열 (선택)</span>
                          <select
                            value={manualGroup}
                            onChange={(event) => handleManualGroup(event.target.value)}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          >
                            <option value="">사용 안 함</option>
                            {profiledColumns.map((column) => (
                              <option key={column.name} value={column.name} disabled={manualX === column.name || manualY.includes(column.name)}>
                                {column.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <fieldset className="flex flex-col gap-1 text-sm">
                        <legend className="text-ink-2">Y 축 열 (하나 이상 선택)</legend>
                        <div className="flex flex-wrap gap-x-4 gap-y-2">
                          {profiledColumns.map((column) => (
                            <label key={column.name} className="flex items-center gap-2 text-ink-1">
                              <input
                                type="checkbox"
                                aria-label={`Y 축 ${column.name}`}
                                checked={manualY.includes(column.name)}
                                disabled={manualX === column.name || manualGroup === column.name}
                                onChange={(event) => handleManualY(column.name, event.target.checked)}
                              />
                              {column.name}
                            </label>
                          ))}
                        </div>
                      </fieldset>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">집계</span>
                          <select
                            value={manualAggregation}
                            onChange={(event) => {
                              clearForOptionChange();
                              setManualAggregation(event.target.value as ChartAggregation);
                            }}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          >
                            {CHART_AGGREGATIONS.map((item) => (
                              <option key={item.value} value={item.value}>{item.label}</option>
                            ))}
                          </select>
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">정렬</span>
                          <select
                            value={manualSort}
                            onChange={(event) => {
                              clearForOptionChange();
                              setManualSort(event.target.value as ChartSortMode);
                            }}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          >
                            {CHART_SORT_MODES.map((item) => (
                              <option key={item.value} value={item.value}>{item.label}</option>
                            ))}
                          </select>
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">표시 행 수</span>
                          <input
                            type="number"
                            min={1}
                            max={100}
                            value={manualLimit}
                            onChange={(event) => {
                              clearForOptionChange();
                              setManualLimit(event.target.value);
                            }}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-sm">
                          <span className="text-ink-2">방향</span>
                          <select
                            value={manualOrientation}
                            onChange={(event) => {
                              clearForOptionChange();
                              setManualOrientation(event.target.value as ChartOrientation);
                            }}
                            className="rounded-md border border-ink-3/40 bg-transparent px-3 py-2 text-ink-1"
                          >
                            {CHART_ORIENTATIONS.map((item) => (
                              <option key={item.value} value={item.value}>{item.label}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <label className="flex items-center gap-2 text-sm text-ink-1">
                        <input
                          type="checkbox"
                          checked={manualStacked}
                          onChange={(event) => {
                            clearForOptionChange();
                            setManualStacked(event.target.checked);
                          }}
                        />
                        누적 표시
                      </label>
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <ProcessSteps steps={CHART_STEPS} done={!!result} engineNote={engineNote} />

      {workspaceNotice ? <p className="rounded-md border border-accent/30 bg-accent-soft px-4 py-3 text-sm text-ink-1" role="status">{workspaceNotice}</p> : null}
      {error ? (
        <p className="rounded-md border border-red-400/50 bg-red-500/10 px-4 py-3 text-sm text-red-500" role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <>
          <ChartResult result={result} />
          <ChartFollowUp
            onSubmit={handleFollowUp}
            busy={generateBusy}
            disabled={!dataFile}
            disabledHint="다시 연 결과입니다 — 원본 데이터를 다시 첨부하면 새로 생성할 수 있습니다."
          />
        </>
      ) : null}
    </div>
  );
}

function ChartResult({ result }: { result: ChartGenerateResponse }) {
  const artifacts = result.artifacts.flatMap((artifact) => {
    const href = getSafeOfficeProxyPath(artifact.download_url, MANIFEST_ARTIFACT_PATH);
    return href ? [{ ...artifact, href }] : [];
  });
  const bundleHref = getSafeOfficeProxyPath(result.bundle_url, BUNDLE_PATH);

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
      {artifacts.length > 0 || bundleHref ? (
        <div className="flex flex-wrap gap-3 text-sm">
          {artifacts.map((artifact) => (
            <a
              key={`${artifact.filename}-${artifact.download_url}`}
              href={artifact.href}
              download
              className="rounded-md border border-ink-3/40 px-3 py-1 text-ink-1 hover:bg-ink-3/10"
            >
              {chartArtifactLabel(artifact.filename)}
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
      ) : null}
    </section>
  );
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isAbortError(error: unknown) {
  return typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError';
}

function isChartType(value: unknown): value is ChartType {
  return typeof value === 'string' && CHART_TYPES.some((item) => item.value === value && item.value !== '');
}

function isChartAggregation(value: unknown): value is ChartAggregation {
  return typeof value === 'string' && CHART_AGGREGATIONS.some((item) => item.value === value);
}

function isChartSortMode(value: unknown): value is ChartSortMode {
  return typeof value === 'string' && CHART_SORT_MODES.some((item) => item.value === value);
}

function isChartOrientation(value: unknown): value is ChartOrientation {
  return typeof value === 'string' && CHART_ORIENTATIONS.some((item) => item.value === value);
}

function isJsonValue(value: unknown, seen = new Set<object>()): boolean {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every((item) => isJsonValue(item, seen));
  if (!isRecord(value) || seen.has(value)) return false;

  seen.add(value);
  const valid = Object.values(value).every((item) => isJsonValue(item, seen));
  seen.delete(value);
  return valid;
}

function isJsonRecord(value: unknown): value is Record<string, unknown> {
  return isRecord(value) && isJsonValue(value);
}

function isOfficeArtifact(value: unknown): value is OfficeArtifact {
  return (
    isRecord(value)
    && typeof value.filename === 'string'
    && typeof value.media_type === 'string'
    && typeof value.size_bytes === 'number'
    && Number.isFinite(value.size_bytes)
    && value.size_bytes >= 0
    && typeof value.sha256 === 'string'
    && typeof value.download_url === 'string'
  );
}

function isOfficeArtifactList(value: unknown): value is OfficeArtifact[] {
  return Array.isArray(value) && value.every(isOfficeArtifact);
}

function chartConfigFromSpec(value: unknown): SafeChartConfig | null {
  if (!isRecord(value)) return null;

  const config: SafeChartConfig = {};
  if ('type' in value) {
    if (!isChartType(value.type)) return null;
    config.type = value.type;
  }
  if ('aggregation' in value) {
    if (!isChartAggregation(value.aggregation)) return null;
    config.aggregation = value.aggregation;
  }
  if ('stacked' in value) {
    if (typeof value.stacked !== 'boolean') return null;
    config.stacked = value.stacked;
  }
  if ('sort' in value) {
    if (!isChartSortMode(value.sort)) return null;
    config.sort = value.sort;
  }
  if ('limit' in value) {
    if (typeof value.limit !== 'number' || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100) return null;
    config.limit = value.limit;
  }
  if ('orientation' in value) {
    if (!isChartOrientation(value.orientation)) return null;
    config.orientation = value.orientation;
  }
  return config;
}

function chartResultFromJob(job: OfficeJobDetail): ChartGenerateResponse | null {
  const value: unknown = job;
  if (!isRecord(value) || value.service !== 'chart' || value.status !== 'completed') return null;
  if (typeof value.job_id !== 'string' || !/^[0-9a-f]{32}$/.test(value.job_id)) return null;
  if (typeof value.title !== 'string' || typeof value.llm_used !== 'boolean') return null;
  if (!isJsonRecord(value.chart_spec) || !isJsonRecord(value.echarts_option)) return null;
  if (!Array.isArray(value.warnings) || value.warnings.some((warning) => typeof warning !== 'string')) return null;
  if (!isOfficeArtifactList(value.artifacts)) return null;
  if (typeof value.preview_url !== 'string' || typeof value.bundle_url !== 'string') return null;

  return {
    job_id: value.job_id,
    status: 'completed',
    title: value.title,
    llm_used: value.llm_used,
    chart_spec: value.chart_spec,
    echarts_option: value.echarts_option,
    warnings: value.warnings,
    artifacts: value.artifacts,
    preview_url: value.preview_url,
    bundle_url: value.bundle_url,
  };
}

function uniqueProfileColumns(profile: ChartInspectResponse) {
  const seen = new Set<string>();
  return profile.columns.filter((column) => {
    if (seen.has(column.name)) return false;
    seen.add(column.name);
    return true;
  });
}

function getSafeOfficeProxyPath(path: string, pathPattern: RegExp) {
  if (!pathPattern.test(path)) return null;
  try {
    return getOfficeArtifactProxyPath(path);
  } catch {
    return null;
  }
}

function chartArtifactLabel(filename: string) {
  if (filename === 'echarts_option.json') return 'ECharts option(JSON)';
  if (filename === 'chart_data.csv') return '집계 데이터(CSV)';
  return filename;
}
