'use client';

import { useEffect, useState } from 'react';

import { fetchAiStatus, fetchKnowledgeFolders } from '@/lib/api';
import type { AiStatusResponse } from '@/lib/types';

// Aero Work F7 첫 실행 온보딩 — 3단계(로컬 AI 연결·지식폴더 등록·첫 업무대화)를 상태에서 파생해
// 안내한다(gongmuwon §3.1). AI 연결 + 폴더 등록이 끝났으면 자동으로 사라지고, '나중에'로 숨긴다.

const DISMISS_KEY = 'aero-work-onboarding-dismissed';

export function AeroWorkOnboarding({ onNavigate }: { onNavigate: (view: string) => void }) {
  const [ai, setAi] = useState<AiStatusResponse | null>(null);
  const [folderCount, setFolderCount] = useState(0);
  const [ready, setReady] = useState(false);
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    setDismissed(typeof window !== 'undefined' && window.localStorage.getItem(DISMISS_KEY) === '1');
    let alive = true;
    void (async () => {
      const [statusResult, foldersResult] = await Promise.all([
        fetchAiStatus().catch(() => null),
        fetchKnowledgeFolders().catch(() => ({ folders: [] })),
      ]);
      if (!alive) {
        return;
      }
      setAi(statusResult);
      setFolderCount(foldersResult.folders.length);
      setReady(true);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const step1 = ai?.status === 'ok';
  const step2 = folderCount > 0;

  if (!ready || dismissed || (step1 && step2)) {
    return null;
  }

  const dismiss = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(DISMISS_KEY, '1');
    }
    setDismissed(true);
  };

  const mark = (done: boolean) => (done ? '✅' : '•');

  return (
    <div className="rounded-2xl border border-accent/30 bg-accent-soft p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-ink-1">처음 오셨네요 — 3단계로 시작해 보세요</p>
        <button type="button" onClick={dismiss} className="rounded px-2 py-0.5 text-xs text-ink-2 hover:bg-surface-sunken">나중에</button>
      </div>
      <ol className="mt-2 space-y-1 text-sm text-ink-2">
        <li>{mark(step1)} 로컬 AI 연결 {step1 ? '완료' : '— 환경설정에서 상태 확인'}</li>
        <li>{mark(step2)} 지식폴더 등록 {step2 ? '완료' : '— 업무 폴더를 색인'}</li>
        <li>• 첫 업무대화 — 대화 한 줄로 일정·문서·검색을 이어가기</li>
      </ol>
      <div className="mt-3 flex flex-wrap gap-2">
        {!step2 ? (
          <button type="button" onClick={() => onNavigate('knowledge')} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-on">지식폴더 등록</button>
        ) : null}
        <button type="button" onClick={() => onNavigate('chat')} className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1">업무대화 시작</button>
        {!step1 ? (
          <button type="button" onClick={() => onNavigate('settings')} className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-1.5 text-xs font-medium text-ink-1">AI 상태 보기</button>
        ) : null}
      </div>
    </div>
  );
}
