'use client';

import { useState } from 'react';

import {
  applyTaxonomy,
  proposeTaxonomy,
  type TaxonomyCandidate,
  type TaxonomyProposeInput,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work 분류체계 마법사(gongmuwon §6.6) — ① 니즈 파악(기관/부서/담당업무) →
// ② LLM 분류 검토(색인 파일명·요약 기반 업무 후보 생성, 사용자가 선택·이름 수정) →
// ③ 적용(지식위키에 업무 분류 트리로 반영). 단계는 로컬 state 로만 관리하며
// 적용 성공 시 onApplied 콜백으로 상위(지식위키)가 목록을 새로고침한다.

type Step = 1 | 2 | 3;

// 후보 카드 편집용 로컬 상태 — 사용자가 이름을 고치거나 선택 해제할 수 있어야 하므로
// TaxonomyCandidate 에 selected 플래그를 얹은 파생 타입을 쓴다.
type EditableCandidate = TaxonomyCandidate & { selected: boolean };

interface TaxonomyWizardProps {
  onApplied?: () => void;
  onCancel?: () => void;
}

export function TaxonomyWizard({ onApplied, onCancel }: TaxonomyWizardProps) {
  const [step, setStep] = useState<Step>(1);
  const [input, setInput] = useState<TaxonomyProposeInput>({ organization: '', department: '', duties: '' });
  const [candidates, setCandidates] = useState<EditableCandidate[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canPropose = input.organization.trim() && input.department.trim() && input.duties.trim();

  const handlePropose = async () => {
    if (!canPropose) {
      setError('기관·부서·담당업무를 모두 입력할 것.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await proposeTaxonomy(input, getCsrfCookie());
      setCandidates(result.candidates.map((candidate) => ({ ...candidate, selected: true })));
      setModel(result.model);
      setStep(2);
    } catch {
      setError('분류 후보 생성에 실패함 — 로컬 AI(또는 연결) 상태를 확인할 것.');
    } finally {
      setLoading(false);
    }
  };

  const toggleSelected = (index: number) => {
    setCandidates((prev) => prev.map((candidate, i) => (i === index ? { ...candidate, selected: !candidate.selected } : candidate)));
  };

  const renameCandidate = (index: number, name: string) => {
    setCandidates((prev) => prev.map((candidate, i) => (i === index ? { ...candidate, name } : candidate)));
  };

  const describeCandidate = (index: number, description: string) => {
    setCandidates((prev) => prev.map((candidate, i) => (i === index ? { ...candidate, description } : candidate)));
  };

  const selectedCandidates = candidates.filter((candidate) => candidate.selected);

  const handleApply = async () => {
    if (selectedCandidates.length === 0) {
      setError('적용할 분류를 최소 1개 선택할 것.');
      return;
    }
    setApplying(true);
    setError(null);
    try {
      await applyTaxonomy(
        selectedCandidates.map(({ name, description, file_ids }) => ({ name, description, file_ids })),
        getCsrfCookie(),
      );
      setStep(3);
      onApplied?.();
    } catch {
      setError('분류 적용에 실패함 — 다시 시도할 것.');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-ink-1">분류체계 마법사</p>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken"
          >
            닫기
          </button>
        ) : null}
      </div>

      <ol className="mt-2 flex items-center gap-2 text-xs text-ink-3">
        <li className={step === 1 ? 'font-semibold text-accent' : ''}>① 니즈 파악</li>
        <li>›</li>
        <li className={step === 2 ? 'font-semibold text-accent' : ''}>② 분류 검토</li>
        <li>›</li>
        <li className={step === 3 ? 'font-semibold text-accent' : ''}>③ 적용</li>
      </ol>

      {error ? <p className="mt-2 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs text-red-500">{error}</p> : null}

      {step === 1 ? (
        <div className="mt-3 space-y-2">
          <input
            value={input.organization}
            onChange={(event) => setInput((prev) => ({ ...prev, organization: event.target.value }))}
            placeholder="기관 (예: OO시청)"
            className="w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs text-ink-1"
          />
          <input
            value={input.department}
            onChange={(event) => setInput((prev) => ({ ...prev, department: event.target.value }))}
            placeholder="부서 (예: 총무과)"
            className="w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs text-ink-1"
          />
          <textarea
            value={input.duties}
            onChange={(event) => setInput((prev) => ({ ...prev, duties: event.target.value }))}
            placeholder="담당업무 (예: 예산 편성, 물품 구매, 출장 정산)"
            rows={3}
            className="w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs text-ink-1"
          />
          <button
            type="button"
            disabled={loading}
            onClick={() => void handlePropose()}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-on hover:bg-accent/90 disabled:opacity-50"
          >
            {loading ? '분류 생성 중…' : 'LLM 분류 생성'}
          </button>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="mt-3 space-y-2">
          {model ? <p className="text-[11px] text-ink-3">모델: {model}</p> : null}
          {candidates.length === 0 ? (
            <p className="text-sm text-ink-3">생성된 분류 후보가 없음.</p>
          ) : (
            <ul className="space-y-2">
              {candidates.map((candidate, index) => (
                <li key={index} className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2">
                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={candidate.selected}
                      onChange={() => toggleSelected(index)}
                      className="mt-1"
                    />
                    <div className="flex-1 space-y-1">
                      <input
                        value={candidate.name}
                        onChange={(event) => renameCandidate(index, event.target.value)}
                        className="w-full rounded border border-line-subtle bg-surface-base px-2 py-1 text-xs font-semibold text-ink-1"
                      />
                      <textarea
                        value={candidate.description}
                        onChange={(event) => describeCandidate(index, event.target.value)}
                        rows={2}
                        className="w-full rounded border border-line-subtle bg-surface-base px-2 py-1 text-[11px] text-ink-2"
                      />
                      <p className="text-[11px] text-ink-3">매칭 파일 {candidate.file_ids.length}건</p>
                    </div>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken"
            >
              이전
            </button>
            <button
              type="button"
              disabled={applying}
              onClick={() => void handleApply()}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-on hover:bg-accent/90 disabled:opacity-50"
            >
              {applying ? '적용 중…' : '적용'}
            </button>
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-ink-1">분류가 적용됨. 업무 허브 지식위키에서 확인할 것.</p>
        </div>
      ) : null}
    </div>
  );
}
