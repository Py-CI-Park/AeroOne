'use client';

import { AdminOverviewSection } from '../admin-overview-section';
import type { TabKey } from '../../admin-console-tabs';

const deepLinks: { tab: Exclude<TabKey, 'overview'>; label: string }[] = [
  { tab: 'accounts', label: '계정 관리로 이동' },
  { tab: 'content', label: '콘텐츠 관리로 이동' },
  { tab: 'system', label: '시스템 상태로 이동' },
  { tab: 'ai', label: 'AI 설정으로 이동' },
  { tab: 'audit', label: '감사 로그로 이동' },
];

export function OverviewGroup({ onNavigate }: { onNavigate: (tab: TabKey) => void }) {
  return (
    <div className="space-y-6">
      <AdminOverviewSection />
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">그룹 바로가기</h2>
        <div className="flex flex-wrap gap-2">
          {deepLinks.map((link) => (
            <button
              key={link.tab}
              type="button"
              onClick={() => onNavigate(link.tab)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
            >
              {link.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
