import React from 'react';
import Link from 'next/link';

export function ServiceCard({
  title,
  description,
  href,
  badge,
  icon,
}: {
  title: string;
  description: string;
  href: string;
  badge: string;
  icon?: string;
}) {
  return (
    <Link
      href={href}
      className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-8 shadow-sm transition hover:-translate-y-1 hover:shadow-xl"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-slate-50 opacity-80" />
      <div className="relative">
        <div className={`mb-6 flex items-center ${icon ? 'justify-between' : 'justify-end'}`}>
          {icon ? (
            <div data-testid="service-card-icon" className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-900 text-3xl text-white shadow-md">
              {icon}
            </div>
          ) : null}
          <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">{badge}</span>
        </div>
        <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
        <div className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-slate-900">
          서비스 열기
          <span className="transition group-hover:translate-x-1">→</span>
        </div>
      </div>
    </Link>
  );
}
