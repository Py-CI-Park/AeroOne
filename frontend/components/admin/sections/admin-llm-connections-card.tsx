'use client';

import React, { useState } from 'react';

import type { LlmConnection } from '@/lib/types';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';

const inputClass = 'rounded-md border border-slate-300 px-2 py-1 text-sm';

// AI 탭 안의 "AI 연결" 카드. OpenAI 호환 엔드포인트(base_url + api_key)를 등록하고
// 검증(verify)으로 모델 목록을 불러와 기본 모델을 저장한다. 키는 password 입력·목록 마스킹만 노출한다.
export function AdminLlmConnectionsCard() {
  const { state, llmForm, setLlmForm, addLlmConnection } = useAdminConsoleData();
  const connections = state.llmConnections;
  const creating = state.busy === 'llm-create';
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI 연결</h2>
        <Badge tone="blue">llm-registry</Badge>
      </div>
      <p className="mb-3 text-sm text-slate-500">
        OpenAI 호환 엔드포인트를 등록하면 검증 시 모델 목록을 불러와 기본 모델을 지정할 수 있습니다. 키는 서버에만 저장되고 화면에는 마스킹 값만 표시됩니다.
      </p>
      <form
        className="mb-4 grid gap-2 md:grid-cols-2"
        onSubmit={(event) => { event.preventDefault(); void addLlmConnection(); }}
      >
        <input value={llmForm.name} onChange={(event) => setLlmForm((current) => ({ ...current, name: event.target.value }))} placeholder="표시명 (예: 로컬 Ollama)" aria-label="llm connection name" className={inputClass} />
        <input value={llmForm.base_url} onChange={(event) => setLlmForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="base_url (예: http://127.0.0.1:11434/v1)" aria-label="llm connection base_url" className={inputClass} />
        <input type="password" value={llmForm.api_key} onChange={(event) => setLlmForm((current) => ({ ...current, api_key: event.target.value }))} placeholder="API 키 (무키면 비움)" aria-label="llm connection api_key" className={inputClass} autoComplete="off" />
        <div className="flex items-center gap-4 text-sm text-slate-600">
          <label className="flex items-center gap-1"><input type="checkbox" checked={llmForm.verify_tls} onChange={(event) => setLlmForm((current) => ({ ...current, verify_tls: event.target.checked }))} aria-label="llm connection verify_tls" />TLS 검증</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={llmForm.is_default} onChange={(event) => setLlmForm((current) => ({ ...current, is_default: event.target.checked }))} aria-label="llm connection is_default" />기본 연결</label>
        </div>
        <div className="md:col-span-2">
          <button type="submit" disabled={creating} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">연결 추가</button>
        </div>
      </form>
      {connections.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">등록된 LLM 연결이 없습니다. 위 폼으로 첫 연결을 추가하세요.</p>
      ) : (
        <ul className="space-y-3">{connections.map((connection) => <LlmConnectionRow key={connection.id} connection={connection} />)}</ul>
      )}
    </div>
  );
}

function LlmConnectionRow({ connection }: { connection: LlmConnection }) {
  const { state, testLlmConnection, saveLlmConnectionModel, promoteLlmConnection, toggleLlmConnection, removeLlmConnection, rotateLlmConnectionKey } = useAdminConsoleData();
  const loadedModels = state.llmModels[connection.id];
  const modelOptions = loadedModels ?? (connection.default_model ? [connection.default_model] : []);
  const [selectedModel, setSelectedModel] = useState(connection.default_model ?? '');
  const [newKey, setNewKey] = useState('');
  const rowBusy = state.busy === `llm-${connection.id}`;
  const verifying = state.busy === `llm-verify-${connection.id}`;
  return (
    <li className="rounded-lg border border-slate-100 p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <strong>{connection.name}</strong>
          {connection.is_default ? <Badge tone="green">기본</Badge> : null}
          <Badge tone={connection.is_enabled ? 'blue' : 'slate'}>{connection.is_enabled ? '사용' : '중지'}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={verifying} onClick={() => void testLlmConnection(connection)} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40">검증</button>
          <button type="button" disabled={rowBusy || connection.is_default} onClick={() => void promoteLlmConnection(connection)} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40">기본 지정</button>
          <button type="button" disabled={rowBusy} onClick={() => void toggleLlmConnection(connection)} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40">{connection.is_enabled ? '사용 중지' : '사용'}</button>
          <button type="button" disabled={rowBusy} onClick={() => void removeLlmConnection(connection)} className="rounded-md border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 disabled:opacity-40">삭제</button>
        </div>
      </div>
      <p className="break-all font-mono text-xs text-slate-500">{connection.base_url}</p>
      <p className="mt-1 text-xs text-slate-500">키 <span className="font-mono">{connection.api_key_masked || '(무키)'}</span> · TLS {String(connection.verify_tls)}</p>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        <div className="flex items-center gap-2">
          <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)} aria-label={`${connection.name} model`} className={`${inputClass} min-w-0 flex-1`}>
            <option value="">모델 선택</option>
            {modelOptions.map((model) => <option key={model} value={model}>{model}</option>)}
          </select>
          <button type="button" disabled={rowBusy} onClick={() => void saveLlmConnectionModel(connection, selectedModel)} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40">모델 저장</button>
        </div>
        <div className="flex items-center gap-2">
          <input type="password" value={newKey} onChange={(event) => setNewKey(event.target.value)} placeholder="새 API 키로 교체" aria-label={`${connection.name} new api_key`} className={`${inputClass} min-w-0 flex-1`} autoComplete="off" />
          <button type="button" disabled={rowBusy} onClick={() => { void rotateLlmConnectionKey(connection, newKey); setNewKey(''); }} className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40">키 교체</button>
        </div>
      </div>
    </li>
  );
}
