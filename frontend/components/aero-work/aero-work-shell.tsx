'use client';

import { useState } from 'react';
import { AiChatWorkspace } from '@/components/ai/ai-chat-workspace';
import { KnowledgePanel } from '@/components/aero-work/knowledge-panel';
import { SchedulePanel } from '@/components/aero-work/schedule-panel';
import { HomeBriefing } from '@/components/aero-work/home-briefing';

// Aero Work — gongmuwon(공무원) 워크스페이스의 AeroOne 네이티브 재구현 (P0 스캐폴딩).
// gongmuwon 과 동일한 6메뉴 IA(업무대화·일정·문서작성·내 지식폴더·실행기록·환경설정) + 홈
// '오늘의 브리핑' 을 세션 중심 워크스페이스로 배치한다. 각 메뉴 본문은 P1~P5 에서 채운다.
// AI 는 폐쇄망 Ollama + OpenAI provider(기존 AeroOne 자산)를 재사용하며 별도 AI 팩을 쓰지 않는다.

type ViewKey = 'home' | 'chat' | 'schedule' | 'document' | 'knowledge' | 'log' | 'settings';

type NavItem = {
  key: ViewKey;
  icon: string;
  label: string;
  summary: string;
  reuse: string;
  phase: string;
};

const NAV: NavItem[] = [
  { key: 'home', icon: '🏠', label: '홈 · 오늘의 브리핑', summary: '오늘 일정·이어서 하기·지식 요약·이용 팁을 한 화면에.', reuse: '대시보드·최근 열람 스트립', phase: 'P4' },
  { key: 'chat', icon: '💬', label: '업무대화', summary: '로컬·외부 LLM 과 대화하고, 내 지식폴더에서 근거를 출처와 함께 붙여 답한다. 파일·이미지 첨부, 일정·문서작성으로 이어가기.', reuse: 'AeroAI(SSE 스트리밍·첨부·근거·provider)', phase: '구현됨(P1)' },
  { key: 'schedule', icon: '📅', label: '일정', summary: '개인 캘린더 — 일정 추가·수정·삭제, 다가오는 일정 아젠다. 알림·세션 연결은 후속.', reuse: '신규(대시보드 Schedule 자리 승격)', phase: '구현됨(P4)' },
  { key: 'document', icon: '📝', label: '문서작성', summary: '지시 → 구조 검토 → 미리보기 그대로 HWPX(한글) 생성. 시행문·1p·풀버전·이메일·임의형식.', reuse: 'Office Studio 파이프라인 + HWPX(OWPML) 생성기', phase: 'P3' },
  { key: 'knowledge', icon: '📚', label: '내 지식폴더', summary: '지정 폴더를 그 자리에서 색인 → 키워드·근거 벡터 검색, 증분 동기화(추가·수정·이동·삭제).', reuse: 'Ollama nomic-embed 임베딩 + 코사인 벡터 검색', phase: '구현됨(P2)' },
  { key: 'log', icon: '🧾', label: '실행기록', summary: '언제 무엇이 실행됐는지 입력·출력과 함께 쉬운 우리말로 투명하게.', reuse: '관리자 감사 로그 + AI 운영 로그', phase: 'P4' },
  { key: 'settings', icon: '⚙️', label: '환경설정', summary: 'LLM 프로필(로컬·외부) 전환, 튜토리얼 다시 보기, 시작 시 변경 감지.', reuse: '관리자 AI provider·테마·매뉴얼', phase: 'P4' },
];

export function AeroWorkShell() {
  const [view, setView] = useState<ViewKey>('home');
  const active = NAV.find((item) => item.key === view) ?? NAV[0];

  return (
    <div className="flex min-h-[calc(100vh-9rem)] gap-4">
      <nav aria-label="Aero Work 메뉴" className="flex w-56 shrink-0 flex-col gap-1 rounded-2xl border border-line-subtle bg-surface-raised p-3">
        <div className="mb-2 px-2">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-accent">Aero Work</p>
          <p className="mt-1 text-xs leading-snug text-ink-3">폐쇄망 로컬 AI 업무 워크스페이스</p>
        </div>
        {NAV.map((item) => (
          <button
            key={item.key}
            type="button"
            aria-current={view === item.key}
            onClick={() => setView(item.key)}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
              view === item.key ? 'bg-accent text-accent-on' : 'text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
            }`}
          >
            <span aria-hidden className="text-base">{item.icon}</span>
            <span className="flex-1 truncate">{item.label.split(' · ')[0]}</span>
          </button>
        ))}
      </nav>

      <section className="flex-1 rounded-2xl border border-line-subtle bg-surface-raised p-6">
        <div className="flex items-center gap-3">
          <span aria-hidden className="text-2xl">{active.icon}</span>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-ink-1">{active.label}</h2>
            <p className="mt-0.5 text-sm text-ink-2">{active.summary}</p>
          </div>
        </div>

        {view === 'home' ? (
          <div className="mt-6 space-y-6">
            <HomeBriefing onOpenSchedule={() => setView('schedule')} onOpenKnowledge={() => setView('knowledge')} />
            <div className="grid gap-4 md:grid-cols-2">
            {NAV.filter((item) => item.key !== 'home').map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setView(item.key)}
                className="flex flex-col gap-2 rounded-xl border border-line-subtle bg-surface-base p-4 text-left transition-shadow hover:shadow-md"
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-ink-1"><span aria-hidden>{item.icon}</span>{item.label.split(' · ')[0]}</span>
                <span className="text-xs leading-snug text-ink-2">{item.summary}</span>
                <span className="mt-1 inline-flex w-fit items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">{item.phase} · {item.reuse}</span>
              </button>
            ))}
            </div>
          </div>
        ) : view === 'chat' ? (
          <div className="mt-4">
            <AiChatWorkspace />
          </div>
        ) : view === 'knowledge' ? (
          <KnowledgePanel />
        ) : view === 'schedule' ? (
          <SchedulePanel />
        ) : (
          <div className="mt-6 rounded-xl border border-dashed border-line-subtle bg-surface-base p-6">
            <p className="text-sm font-semibold text-ink-1">준비 중 ({active.phase})</p>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{active.summary}</p>
            <p className="mt-3 text-xs text-ink-3">재사용 자산: <span className="font-medium text-ink-2">{active.reuse}</span></p>
            <p className="mt-1 text-xs text-ink-3">상세 계획: <code className="rounded bg-ink-3/10 px-1">docs/dev_plan/aero-work-plan.md</code></p>
          </div>
        )}
      </section>
    </div>
  );
}
