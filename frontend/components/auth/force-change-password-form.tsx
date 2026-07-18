'use client';

import { FormEvent, useState } from 'react';

import { changeOwnPassword } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// 초기 비밀번호(부트스트랩 ADMIN_PASSWORD) 미변경 계정 전용 강제 변경 화면.
// 관리자 콘솔은 이 상태에서 403 이 나므로, 콘솔 밖에서 접근 가능한 이 화면으로만
// 비밀번호를 교체해 데드락(변경하려면 콘솔 진입 필요, 진입하려면 변경 필요)을 푼다.
// change-password 엔드포인트는 _FIRST_CHANGE_ALLOWED_PATHS 에 포함돼 강제 변경 상태에서도 호출된다.
export function ForceChangePasswordForm() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage('');
    if (next.length < 8) {
      setMessage('새 비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (next !== confirm) {
      setMessage('새 비밀번호와 확인이 일치하지 않습니다.');
      return;
    }
    if (next === current) {
      setMessage('새 비밀번호는 현재 비밀번호와 달라야 합니다.');
      return;
    }
    setBusy(true);
    try {
      const csrf = getCsrfCookie();
      await changeOwnPassword(current, next, csrf);
      // 변경 성공 시 세션 쿠키가 갱신되고 강제 변경 상태가 해제되므로 대시보드로 이동한다.
      window.location.assign('/');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '비밀번호 변경에 실패했습니다.');
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-9rem)] items-center justify-center">
      <form
        onSubmit={handleSubmit}
        aria-label="초기 비밀번호 변경"
        className="w-full max-w-md overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-200/70"
      >
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-blue-800 px-7 py-6 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-100">AeroOne</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">초기 비밀번호 변경</h2>
          <p className="mt-2 text-sm text-blue-100">
            보안을 위해 최초 발급 비밀번호를 새 비밀번호로 교체해야 이용을 시작할 수 있습니다.
          </p>
        </div>
        <div className="space-y-4 p-7">
          <label className="block text-sm font-semibold text-slate-700">
            현재 비밀번호
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base shadow-inner outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="현재(발급) 비밀번호"
              autoComplete="current-password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </label>
          <label className="block text-sm font-semibold text-slate-700">
            새 비밀번호
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base shadow-inner outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="새 비밀번호 (8자 이상)"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
          </label>
          <label className="block text-sm font-semibold text-slate-700">
            새 비밀번호 확인
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base shadow-inner outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="새 비밀번호 확인"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 disabled:opacity-40"
          >
            {busy ? '변경 중…' : '비밀번호 변경'}
          </button>
          {message ? (
            <p role="alert" className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
              {message}
            </p>
          ) : null}
        </div>
      </form>
    </div>
  );
}
