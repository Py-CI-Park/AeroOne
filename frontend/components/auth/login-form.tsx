'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

import { login } from '@/lib/api';

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('change-me');
  const [message, setMessage] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(username, password);
      router.push('/admin/newsletters');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '로그인 실패');
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <input
        className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2"
        placeholder="아이디"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />
      <input
        type="password"
        className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2"
        placeholder="비밀번호"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" className="rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white">
        로그인
      </button>
      {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
    </form>
  );
}
