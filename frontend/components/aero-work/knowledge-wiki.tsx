'use client';

import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { fetchKnowledgeWiki, summarizeKnowledgeFile, type WikiFamily } from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

// Aero Work F5 지식 위키(버전 가족) — 색인된 문서를 같은 문서의 대표(공식본) + 판본 이력으로
// 묶어 보여준다(gongmuwon 업무 허브 백본, §6.5). 분류체계 마법사·주제 페이지는 후속.
// 키워드 일치 구간을 <mark> 로 감싸 즉시 강조 — 입력 placeholder 의 '목차 강조' 약속을 실제로 이행한다.
export function highlightMatches(text: string, term: string): ReactNode {
  const t = term.trim().toLowerCase();
  if (!t) return text;
  const lower = text.toLowerCase();
  const parts: ReactNode[] = [];
  let from = 0;
  let idx = lower.indexOf(t);
  let key = 0;
  while (idx >= 0) {
    if (idx > from) parts.push(text.slice(from, idx));
    parts.push(
      <mark key={key++} className="rounded bg-amber-300/60 px-0.5 text-inherit">
        {text.slice(idx, idx + t.length)}
      </mark>,
    );
    from = idx + t.length;
    idx = lower.indexOf(t, from);
  }
  if (parts.length === 0) return text;
  parts.push(text.slice(from));
  return parts;
}

export function KnowledgeWiki() {
  const [families, setFamilies] = useState<WikiFamily[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [keyword, setKeyword] = useState('');
  const [summarizing, setSummarizing] = useState<number | null>(null);
  const [summaries, setSummaries] = useState<Record<number, string>>({});

  const summarize = async (fileId: number) => {
    setSummarizing(fileId);
    try {
      const result = await summarizeKnowledgeFile(fileId, getCsrfCookie());
      setSummaries((prev) => ({ ...prev, [fileId]: result.summary }));
    } catch {
      setSummaries((prev) => ({ ...prev, [fileId]: '요약 실패 — 로컬 AI(또는 연결) 상태를 확인할 것.' }));
    } finally {
      setSummarizing(null);
    }
  };

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
        <>
        <input
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="키워드 입력 즉시 목차 강조·필터 (예: 예산)"
          className="mt-2 w-full rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs text-ink-1"
        />
        <ul className="mt-2 space-y-1">
          {families
            .filter((family) => {
              const term = keyword.trim().toLowerCase();
              if (!term) return true;
              return (
                family.representative.rel_path.toLowerCase().includes(term) ||
                (summaries[family.representative.id] ?? family.representative.summary).toLowerCase().includes(term)
              );
            })
            .map((family) => (
            <li key={family.base} className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-mono text-ink-1">{highlightMatches(family.representative.rel_path, keyword)}</span>
                {family.has_versions ? (
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">대표</span>
                ) : null}
                <span className="text-ink-3">{family.representative.folder_name} · 청크 {family.representative.chunk_count}</span>
                <button
                  type="button"
                  disabled={summarizing === family.representative.id}
                  onClick={() => void summarize(family.representative.id)}
                  className="rounded px-2 py-0.5 text-[11px] text-accent hover:bg-accent-soft disabled:opacity-50"
                >
                  {summarizing === family.representative.id ? '요약 중…' : '요약'}
                </button>
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
              {(summaries[family.representative.id] ?? family.representative.summary) ? (
                <p className="mt-1 rounded bg-accent-soft/50 px-2 py-1 text-[11px] leading-relaxed text-ink-2">
                  {highlightMatches(summaries[family.representative.id] ?? family.representative.summary, keyword)}
                </p>
              ) : null}
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
        </>
      )}
    </div>
  );
}
