'use client';

import { FormEvent, useState } from 'react';

import { fetchClientSession, login } from '@/lib/api';
import { resolveSafeNext } from '@/lib/safe-next';

async function waitForAuthenticatedSession() {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const session = await fetchClientSession();
    if (session.authenticated) return;
    if (attempt < 4) {
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
  }
  throw new Error('로그인 상태를 확인하지 못했습니다');
}

export function LoginForm({ next }: { next?: string | null } = {}) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(username, password);
      await waitForAuthenticatedSession();
      window.location.assign(resolveSafeNext(next));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로그인 실패');
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-9rem)] items-center justify-center">
      <form
        onSubmit={handleSubmit}
        aria-label="AeroOne 접속"
        className="w-full max-w-md overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-200/70"
      >
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-blue-800 px-7 py-6 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-100">AeroOne</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">계정 접속</h2>
          <p className="mt-2 text-sm text-blue-100">발급받은 아이디와 비밀번호로 접속합니다.</p>
        </div>
        <div className="space-y-4 p-7">
          <label className="block text-sm font-semibold text-slate-700">
            아이디
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base shadow-inner outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="아이디"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="block text-sm font-semibold text-slate-700">
            비밀번호
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base shadow-inner outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="비밀번호"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button type="submit" className="w-full rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300">
            로그인
          </button>
          {message ? <p role="alert" className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">{message}</p> : null}
        </div>
      </form>
    </div>
  );
}
