'use client';

import { useCallback, useEffect, useState } from 'react';

import { fetchKnowledgeWiki, type WikiFamily } from '@/lib/api';

// Aero Work F5 지식 위키(버전 가족) — 색인된 문서를 같은 문서의 대표(공식본) + 판본 이력으로
// 묶어 보여준다(gongmuwon 업무 허브 백본, §6.5). 분류체계 마법사·주제 페이지는 후속.

export function KnowledgeWiki() {
  const [families, setFamilies] = useState<WikiFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchKnowledgeWiki();
      setFamilies(data.families);
    } catch {
      setFamilies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = (base: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(base)) {
        next.delete(base);
      } else {
        next.add(base);
      }
      return next;
    });
  };

  return (
    <div className="rounded-xl border border-line-subtle bg-surface-base p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-ink-1">지식 위키 (버전 가족)</p>
          <p className="mt-0.5 text-xs text-ink-3">같은 문서의 대표(공식본)를 앞세우고 옛 판본은 이력으로 접어 보여줌.</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1 hover:bg-surface-sunken"
        >
          새로고침
        </button>
      </div>

      {loading ? (
        <p className="mt-2 text-sm text-ink-3">불러오는 중…</p>
      ) : families.length === 0 ? (
        <p className="mt-2 text-sm text-ink-3">색인된 문서가 없음. 폴더를 등록·색인하면 여기에 정리됨.</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {families.map((family) => (
            <li key={family.base} className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono text-ink-1">{family.representative.rel_path}</span>
                {family.has_versions ? (
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">대표</span>
                ) : null}
                <span className="text-ink-3">{family.representative.folder_name} · 청크 {family.representative.chunk_count}</span>
                {family.has_versions ? (
                  <button
                    type="button"
                    onClick={() => toggle(family.base)}
                    className="ml-auto rounded px-2 py-0.5 text-[11px] text-accent hover:bg-accent-soft"
                  >
                    판본 {family.items.length} {expanded.has(family.base) ? '▲' : '▼'}
                  </button>
                ) : null}
              </div>
              {family.has_versions && expanded.has(family.base) ? (
                <ul className="mt-1 space-y-0.5 border-t border-line-subtle pt-1">
                  {family.items.slice(1).map((item) => (
                    <li key={item.rel_path} className="flex gap-2 pl-2 text-[11px] text-ink-2">
                      <span className="font-mono">{item.rel_path}</span>
                      <span className="text-ink-3">청크 {item.chunk_count}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
