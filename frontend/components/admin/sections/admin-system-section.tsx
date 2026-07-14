'use client';

import React, { useRef } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import type { AiProviderKind } from '@/lib/api';

// OpenAI 호환 제공자 패널 — 안전한 5단계 절차만 노출한다.
// (1) 폼에 입력한 canonical_url/display_url/model/generation 은 이 세션 메모리에만
//     머무르며 서버가 영속하는 값이 아니다(새로고침하면 사라진다) — 아래 "이 값은
//     저장되지 않습니다" 문구가 그 사실을 명시한다.
// (2) 설정 저장/회전: 위 값 + API 키를 스테이징한다. API 키는 항상 비제어(uncontrolled)
//     입력이다 — React state 에 절대 저장하지 않고, 제출이 settle 된 직후(성공/실패
//     불문) DOM 값을 즉시 지운다.
// (3) 저장 설정 테스트: compatible_state 가 unverified/verified 일 때만 활성화되며,
//     서버에 영속된 DPAPI 자격 증명을 그대로 사용해 검증한다(원문 키를 다시 보내지 않음).
// (4) 활성화 확인: compatible_state === 'verified' 일 때만 허용된다.
// (5) 선택 적용: 명시적으로 선택한 kind 를 서버에 제출해야만 트래픽이 전환된다.
function AiProviderPanel() {
  const {
    state,
    aiProviderForm,
    setAiProviderForm,
    stageAiProviderConfig,
    testAiProviderCandidate,
    activateAiProviderConfig,
    selectAiProviderConfigKind,
    deleteAiProviderCredentials,
    reconcileAiProviderState,
  } = useAdminConsoleData();
  const apiKeyInputRef = useRef<HTMLInputElement>(null);

  function clearApiKeyInput() {
    if (apiKeyInputRef.current) apiKeyInputRef.current.value = '';
  }

  async function handleStage() {
    const apiKey = apiKeyInputRef.current?.value ?? '';
    try {
      await stageAiProviderConfig(apiKey);
    } finally {
      clearApiKeyInput();
    }
  }

  const config = state.aiProvider;
  const busy = state.busy;
  const compatibleState = config?.compatible_state ?? 'absent';
  const canTest = compatibleState === 'unverified' || compatibleState === 'verified';
  const canActivate = compatibleState === 'verified';

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI 제공자 설정</h2>
        <Badge tone="blue">provider-config</Badge>
      </div>

      {!config ? (
        <p className="text-sm text-slate-500" role="status">제공자 설정을 불러오는 중입니다…</p>
      ) : (
        <>
          <div className="mb-4 grid gap-3 md:grid-cols-3 text-sm">
            <div className="rounded-lg border border-slate-100 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">선택된 제공자</p>
              <p className="mt-1 font-semibold">{config.selected_kind === 'ollama' ? 'Ollama' : 'OpenAI 호환'}</p>
            </div>
            <div className="rounded-lg border border-slate-100 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">호환 설정 상태</p>
              <Badge tone={compatibleState === 'verified' ? 'green' : compatibleState === 'unverified' ? 'amber' : 'slate'}>
                {compatibleState === 'verified' ? '통과(최신)' : compatibleState === 'unverified' ? '미검증' : '없음'}
              </Badge>
            </div>
            <div className="rounded-lg border border-slate-100 p-3">
              <p className="text-xs font-semibold uppercase text-slate-500">설정 버전</p>
              <p className="mt-1 font-semibold">{config.config_version}</p>
            </div>
          </div>

          <div className="mb-4 rounded-lg border border-slate-100 p-3 text-sm">
            <p className="mb-1 text-xs font-semibold uppercase text-slate-500">OpenAI 호환 설정 (마스킹)</p>
            {compatibleState !== 'absent' ? (
              <>
                <p className="break-all font-mono text-xs text-slate-600">{config.compatible_display_url}</p>
                <p className="mt-1 text-xs text-slate-500">
                  모델 {config.compatible_model} · 최근 테스트 증빙 {config.compatible_test_proof_at ?? '없음'}
                </p>
              </>
            ) : (
              <p className="text-xs text-slate-500">등록된 OpenAI 호환 설정이 없습니다.</p>
            )}
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <select
              aria-label="provider kind"
              value={aiProviderForm.kind}
              onChange={(event) => setAiProviderForm((current) => ({ ...current, kind: event.target.value as AiProviderKind }))}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="ollama">Ollama</option>
              <option value="openai_compatible">OpenAI 호환</option>
            </select>
            <button
              type="button"
              disabled={busy === 'ai-provider-selection' || aiProviderForm.kind === config.selected_kind}
              onClick={() => void selectAiProviderConfigKind(aiProviderForm.kind)}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
            >
              선택 적용
            </button>
            <span className="text-xs text-slate-500">현재 활성: {config.selected_kind === 'ollama' ? 'Ollama' : 'OpenAI 호환'}</span>
          </div>

          <p className="mb-1 text-xs text-slate-500">아래 값은 서버에 영속되지 않습니다(이 세션 메모리에만 임시로 유지됩니다).</p>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              type="text"
              value={aiProviderForm.canonical_url}
              onChange={(event) => setAiProviderForm((current) => ({ ...current, canonical_url: event.target.value }))}
              placeholder="Canonical URL (예: https://api.example.com/v1)"
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              aria-label="compatible canonical url"
            />
            <input
              type="text"
              value={aiProviderForm.display_url}
              onChange={(event) => setAiProviderForm((current) => ({ ...current, display_url: event.target.value }))}
              placeholder="Display URL (마스킹 표시용)"
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              aria-label="compatible display url"
            />
            <input
              type="text"
              value={aiProviderForm.model}
              onChange={(event) => setAiProviderForm((current) => ({ ...current, model: event.target.value }))}
              placeholder="모델"
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              aria-label="compatible model"
            />
            <input
              type="text"
              value={aiProviderForm.generation}
              onChange={(event) => setAiProviderForm((current) => ({ ...current, generation: event.target.value }))}
              placeholder="세대(generation) 식별자"
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              aria-label="compatible generation"
            />
            <input
              ref={apiKeyInputRef}
              type="password"
              autoComplete="off"
              placeholder="API 키 (제출 후 즉시 지워집니다)"
              className="rounded-md border border-slate-300 px-2 py-1 text-sm md:col-span-2"
              aria-label="compatible api key"
            />
          </div>

          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy === 'ai-provider-stage'}
              onClick={() => void handleStage()}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40"
            >
              설정 저장/회전
            </button>
            <button
              type="button"
              disabled={busy === 'ai-provider-test' || !canTest}
              onClick={() => void testAiProviderCandidate()}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40"
            >
              저장 설정 테스트
            </button>
            <button
              type="button"
              disabled={busy === 'ai-provider-activate' || !canActivate}
              onClick={() => void activateAiProviderConfig()}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40"
            >
              활성화 확인
            </button>
            <button
              type="button"
              disabled={busy === 'ai-provider-delete' || compatibleState === 'absent'}
              onClick={() => void deleteAiProviderCredentials()}
              className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:opacity-40"
            >
              자격 증명 삭제
            </button>
            <button
              type="button"
              disabled={busy === 'ai-provider-reconcile'}
              onClick={() => void reconcileAiProviderState()}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40"
            >
              정합성 점검
            </button>
          </div>
          {!canActivate && compatibleState !== 'absent' ? (
            <p className="mt-2 text-xs text-amber-700">활성화하려면 저장된 설정으로 테스트를 통과해야 합니다(오래된 증빙은 재시험이 필요합니다).</p>
          ) : null}
        </>
      )}
    </div>
  );
}

export function AdminSystemSection() {
  const { state, passwordForm, setPasswordForm, changePassword } = useAdminConsoleData();
  return (
    <section className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">DB/자산 경로 상태</h2><Badge tone="blue">config-health</Badge></div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{(state.configHealth?.roots ?? []).map((root) => <div key={root.kind} className="rounded-lg border border-slate-100 p-3 text-sm"><div className="mb-1 flex items-center justify-between gap-2"><strong>{root.kind}</strong><Badge tone={root.exists && root.readable ? 'green' : 'red'}>{root.exists && root.readable ? 'OK' : '점검 필요'}</Badge></div><p className="break-all font-mono text-xs text-slate-500">{root.resolved_path}</p><p className="mt-1 text-xs text-slate-500">exists {String(root.exists)} · readable {String(root.readable)}</p></div>)}</div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">AI 운영 상태</h2><Badge tone="blue">ai-status</Badge></div>
        <div className="grid gap-3 md:grid-cols-3 text-sm"><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">상태</p><p className="mt-1 font-semibold">{String(state.ai?.status ?? '-')}</p></div><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">요청 로그</p><p className="mt-1 font-semibold">{state.ai?.request_logs_total ?? 0}</p></div><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">실패</p><p className="mt-1 font-semibold">{state.ai?.request_failures ?? 0}</p></div></div>
      </div>
      <AiProviderPanel />
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">관리자 계정 / 비밀번호</h2><Badge tone="amber">self-service</Badge></div>
        <p className="mb-3 text-sm text-slate-500">현재 비밀번호를 확인한 뒤 새 비밀번호로 교체합니다. 변경 즉시 다른 세션은 로그아웃됩니다.</p>
        <div className="grid gap-2 md:grid-cols-3"><input type="password" value={passwordForm.current} onChange={(event) => setPasswordForm((current) => ({ ...current, current: event.target.value }))} placeholder="현재 비밀번호" className="rounded-md border border-slate-300 px-2 py-1" aria-label="current password" /><input type="password" value={passwordForm.next} onChange={(event) => setPasswordForm((current) => ({ ...current, next: event.target.value }))} placeholder="새 비밀번호 (8자 이상)" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new password" /><input type="password" value={passwordForm.confirm} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm: event.target.value }))} placeholder="새 비밀번호 확인" className="rounded-md border border-slate-300 px-2 py-1" aria-label="confirm password" /></div>
        <button type="button" disabled={state.busy === 'password-change'} onClick={() => void changePassword()} className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">비밀번호 변경</button>
      </div>
    </section>
  );
}
