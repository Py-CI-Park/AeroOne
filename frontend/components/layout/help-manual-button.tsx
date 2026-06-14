'use client';

import React, { useMemo, useState } from 'react';

const MANUAL_SECTIONS = [
  {
    id: 'dashboard',
    label: '대시보드',
    title: '대시보드와 공통 조작',
    rows: [
      ['모듈 열기', '카드나 상단 메뉴를 클릭해 뉴스레터, 문서, AI, 보고서, 게임으로 이동합니다.'],
      ['테마 변경', '우측 상단 DARK/LIGHT 버튼으로 라이트·다크 테마를 전환합니다.'],
      ['사용법 보기', '현재 버튼을 눌러 기능별 사용법을 팝업으로 확인합니다.'],
    ],
  },
  {
    id: 'newsletter',
    label: '뉴스레터',
    title: '뉴스레터 열람',
    rows: [
      ['최신 글 보기', 'Newsletter 메뉴에서 최신 뉴스레터가 자동으로 열립니다.'],
      ['날짜 이동', '달력/목록에서 원하는 날짜의 이슈를 선택합니다.'],
      ['HTML/PDF/Markdown', '제공된 형식 버튼을 눌러 미리보기 또는 다운로드를 사용합니다. 원본 파일이 없으면 안내 메시지가 표시됩니다.'],
    ],
  },
  {
    id: 'documents',
    label: '문서',
    title: '문서·보고서 HTML 보관소',
    rows: [
      ['문서 보관소', 'Document 메뉴에서 _database/document 의 HTML 문서를 폴더 트리로 엽니다.'],
      ['민간항공기 보고서', 'Civil Aircraft 카드에서 _database/civil_aircraft 문서를 봅니다.'],
      ['NSA 문서', 'NSA 카드는 비밀번호 입력 후 _database/nsa 목록을 불러옵니다. 민감자료 보관용 인증 기능은 아닙니다.'],
    ],
  },
  {
    id: 'ai',
    label: 'AeroAI',
    title: 'AeroAI 채팅과 문서 근거',
    rows: [
      ['AeroAI 채팅', '대시보드 AeroAI 카드에서 사내 폐쇄망 AI 와 대화합니다. 대화는 저장되어 좌측 목록에서 다시 열 수 있고, 응답 생성 중에는 대기 표시가 나옵니다.'],
      ['문서 근거 답변', '검색 결과를 체크해 그 문서만 답변 근거로 보내거나, 근거 범위(Document/Civil/NSA)를 토글할 수 있습니다. 답변 근거는 우측 패널에서 새 탭/미리보기로 확인합니다.'],
      ['HTML 본문 검색', 'AeroAI 화면 오른쪽 검색창에서 _database/document, _database/civil_aircraft 본문을 검색하고 결과 링크로 바로 이동합니다.'],
    ],
  },
  {
    id: 'admin',
    label: '관리자',
    title: '관리자와 가져오기',
    rows: [
      ['로그인', '/login 에서 setup 시 생성된 ADMIN_USERNAME / ADMIN_PASSWORD 로 로그인합니다.'],
      ['뉴스레터 동기화', '관리자 가져오기 화면에서 _database/newsletter 원본을 DB 메타데이터와 동기화합니다.'],
      ['읽음 통계', '관리자 읽음 이벤트 화면에서 뉴스레터 열람 기록을 확인합니다.'],
    ],
  },
  {
    id: 'offline',
    label: '폐쇄망',
    title: '폐쇄망 실행과 운영',
    rows: [
      ['로컬 실행', '개발 PC 는 setup.bat 후 start.bat 으로 실행합니다.'],
      ['폐쇄망 배포', '온라인 PC 에서 offline_package.bat 으로 ZIP 생성 후 폐쇄망 PC 에서 setup_offline.bat → start_offline.bat 순서로 실행합니다.'],
      ['Ollama 설정', 'Ollama 가 다른 PC 에 있으면 backend/.env 의 OLLAMA_BASE_URL 을 http://<ollama-ip>:11434 로 바꿉니다.'],
    ],
  },
];

export function HelpManualButton() {
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(MANUAL_SECTIONS[0].id);
  const selected = useMemo(
    () => MANUAL_SECTIONS.find((section) => section.id === selectedId) ?? MANUAL_SECTIONS[0],
    [selectedId],
  );

  return (
    <>
      <button
        type="button"
        className="rounded border border-line-subtle bg-surface-base px-3 py-1.5 text-xs font-semibold text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
        onClick={() => setOpen(true)}
      >
        사용법
      </button>
      {open ? (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 px-4" role="presentation">
          <section
            aria-modal="true"
            role="dialog"
            aria-labelledby="aeroone-manual-title"
            className="max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-line-subtle bg-surface-raised shadow-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-line-subtle px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-3">AeroOne Manual</p>
                <h2 id="aeroone-manual-title" className="mt-1 text-2xl font-semibold text-ink-1">
                  전체 기능 사용법
                </h2>
              </div>
              <button
                type="button"
                className="rounded border border-line-subtle px-3 py-1.5 text-sm text-ink-2 hover:bg-surface-sunken hover:text-ink-1"
                onClick={() => setOpen(false)}
              >
                닫기
              </button>
            </div>

            <div className="grid max-h-[70vh] grid-cols-1 overflow-y-auto md:grid-cols-[180px_1fr]">
              <nav className="border-b border-line-subtle p-4 md:border-b-0 md:border-r" aria-label="사용법 항목">
                <div className="flex flex-wrap gap-2 md:flex-col">
                  {MANUAL_SECTIONS.map((section) => (
                    <button
                      key={section.id}
                      type="button"
                      className={`rounded px-3 py-2 text-left text-sm transition-colors ${
                        selected.id === section.id
                          ? 'bg-accent text-white'
                          : 'bg-surface-base text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
                      }`}
                      aria-pressed={selected.id === section.id}
                      onClick={() => setSelectedId(section.id)}
                    >
                      {section.label}
                    </button>
                  ))}
                </div>
              </nav>

              <div className="p-6">
                <h3 className="text-xl font-semibold text-ink-1">{selected.title}</h3>
                <div className="mt-4 overflow-hidden rounded-xl border border-line-subtle">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-surface-sunken text-ink-2">
                      <tr>
                        <th className="w-40 px-4 py-3 font-semibold">기능</th>
                        <th className="px-4 py-3 font-semibold">사용법</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.rows.map(([feature, usage]) => (
                        <tr key={feature} className="border-t border-line-subtle">
                          <td className="px-4 py-3 font-medium text-ink-1">{feature}</td>
                          <td className="px-4 py-3 leading-6 text-ink-2">{usage}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-4 text-xs leading-5 text-ink-3">
                  폐쇄망 운영 상세 절차는 docs/CLOSED_NETWORK_GUIDE.md 와 docs/runbook/windows-offline.md 를 기준으로 합니다.
                </p>
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
