import React from 'react';
import Link from 'next/link';
import { ReactNode } from 'react';

export function AppShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-100" suppressHydrationWarning>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <Link href="/" className="text-lg font-semibold text-slate-900">AeroOne</Link>
            <p className="text-sm text-slate-500">사내 뉴스레터 / 문서 플랫폼</p>
          </div>
          <nav className="flex gap-4 text-sm text-slate-600">
            <Link href="/">대시보드</Link>
            <Link href="/newsletters">뉴스레터</Link>
            <Link href="/admin/newsletters">관리자</Link>
            <Link href="/login">로그인</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="mb-6 text-2xl font-semibold text-slate-900">{title}</h1>
        {children}
      </main>
    </div>
  );
}
