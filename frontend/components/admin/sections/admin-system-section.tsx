'use client';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';

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
        <div className="grid gap-3 md:grid-cols-3 text-sm"><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">status</p><p className="mt-1 font-semibold">{String(state.summary?.ai_status?.status ?? state.ai?.status ?? '-')}</p></div><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">logs</p><p className="mt-1 font-semibold">{state.ai?.request_logs_total ?? 0}</p></div><div className="rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold uppercase text-slate-500">failures</p><p className="mt-1 font-semibold">{state.ai?.request_failures ?? 0}</p></div></div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">관리자 계정 / 비밀번호</h2><Badge tone="amber">self-service</Badge></div>
        <p className="mb-3 text-sm text-slate-500">현재 비밀번호를 확인한 뒤 새 비밀번호로 교체합니다. 변경 즉시 다른 세션은 로그아웃됩니다.</p>
        <div className="grid gap-2 md:grid-cols-3"><input type="password" value={passwordForm.current} onChange={(event) => setPasswordForm((current) => ({ ...current, current: event.target.value }))} placeholder="현재 비밀번호" className="rounded-md border border-slate-300 px-2 py-1" aria-label="current password" /><input type="password" value={passwordForm.next} onChange={(event) => setPasswordForm((current) => ({ ...current, next: event.target.value }))} placeholder="새 비밀번호 (8자 이상)" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new password" /><input type="password" value={passwordForm.confirm} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm: event.target.value }))} placeholder="새 비밀번호 확인" className="rounded-md border border-slate-300 px-2 py-1" aria-label="confirm password" /></div>
        <button type="button" disabled={state.busy === 'password-change'} onClick={() => void changePassword()} className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">비밀번호 변경</button>
      </div>
    </section>
  );
}
