'use client';

import React, { useMemo, useState } from 'react';

const MANUAL_SECTIONS = [
  {
    id: 'dashboard',
    label: '대시보드',
    title: '대시보드와 서비스 상태',
    rows: [
      ['현재 서비스 중', 'Newsletter, Document, Civil Aircraft 는 모든 사용자에게 보이는 운영 중 열람 서비스입니다. NSA 는 권한 있는 계정에만 노출·열람됩니다. 카드나 상단 메뉴를 클릭해 이동합니다.'],
      ['Development(개발중)', 'Viewer, AeroAI, Notebook, Ladder 는 Development 섹션의 Active 카드이고, Announcement 와 Schedule 은 Coming soon 비활성 카드입니다. 이 섹션과 Coming soon 카드는 관리자(서버 실행자)에게만 노출됩니다.'],
      ['Admin·테마·사용법', '헤더 오른쪽은 다크(DARK/LIGHT) · 사용법 · (로그인 또는 Admin) 순서입니다. 로그인 전에는 로그인 링크가, 관리자로 로그인하면 Admin 링크가 보입니다. 일반 사용자에게는 둘 다 표시되지 않습니다.'],
    ],
  },
  {
    id: 'newsletter',
    label: '뉴스레터',
    title: '뉴스레터 열람',
    rows: [
      ['최신 글 보기', 'Newsletter 메뉴에서 최신 뉴스레터가 자동으로 열립니다.'],
      ['달력 접기', '달력 접기를 누르면 날짜 영역이 세로뿐 아니라 가로 폭도 줄어 본문을 더 넓게 볼 수 있습니다. 다시 달력 펼치기로 날짜 선택 영역을 복원합니다.'],
      ['HTML 다운로드', '강조된 HTML 다운로드 버튼으로 현재 뉴스레터 원본 HTML 을 바로 내려받습니다. PDF/Markdown 자산이 있으면 형식 버튼으로 전환해 미리보기 또는 다운로드를 사용합니다.'],
    ],
  },
  {
    id: 'documents',
    label: '문서',
    title: '문서·보고서 HTML 보관소',
    rows: [
      ['Document', '현재 서비스 중입니다. Document 메뉴에서 _database/document 의 HTML 문서를 폴더 트리로 엽니다.'],
      ['Civil Aircraft', '현재 서비스 중입니다. Civil Aircraft 카드에서 _database/civil_aircraft 문서를 봅니다.'],
      ['NSA', '권한 있는 계정만 이용할 수 있는 HTML 보관소입니다. 기존 0000 비밀번호 가림막은 제거되었고, 접근 권한이 없으면 관리자에게 권한 요청 안내가 표시됩니다.'],
    ],
  },
  {
    id: 'ai',
    label: 'AeroAI',
    title: 'AeroAI 채팅과 문서 근거 (개발중)',
    rows: [
      ['AeroAI 채팅', '개발중 섹션의 Active 카드입니다. 사내 폐쇄망 AI 와 대화하고, 답변은 Markdown 으로 렌더링되며 복사 버튼은 원본 Markdown 을 복사합니다.'],
      ['문서 근거 답변', '검색 결과를 체크해 그 문서만 답변 근거로 보내거나, 근거 범위(Document/Civil/NSA)를 토글할 수 있습니다. 답변 근거는 우측 패널에서 새 탭/확대 미리보기/전체 보기로 확인합니다.'],
      ['HTML 본문 검색', 'AeroAI 화면 오른쪽 검색창에서 _database/document, _database/civil_aircraft 본문을 검색하고 결과 링크를 새 탭으로 엽니다.'],
    ],
  },
  {
    id: 'viewer',
    label: 'Viewer',
    title: '로컬 Viewer (개발중)',
    rows: [
      ['파일 열기', '개발중 섹션의 Active 카드입니다. 로컬 Markdown·HTML 파일을 끌어다 놓거나 선택한 뒤 미리보기 렌더를 누릅니다. 파일은 서버에 저장되지 않습니다.'],
      ['보기 전환', '편집+미리보기 / 미리보기 집중 / 전체화면 미리보기로 화면 폭과 모니터 높이에 맞춰 봅니다.'],
      ['보안 경계', '로컬 파일 미리보기는 빈 sandbox iframe 으로 표시되어 문서 안의 스크립트와 동일출처 권한이 차단됩니다.'],
    ],
  },
  {
    id: 'notebook-ladder',
    label: '기타 개발중',
    title: 'Notebook·Ladder (개발중)',
    rows: [
      ['Notebook', '개발중 섹션의 Active 카드입니다. 같은 호스트의 Open Notebook 앱(:8502)을 새 탭으로 열며 AeroOne 과 DB·세션·포트를 공유하지 않습니다.'],
      ['Ladder', '개발중 섹션의 Active 카드입니다. 참가자와 당첨 항목을 입력해 브라우저 안에서 사다리 결과를 계산합니다.'],
      ['Coming soon', 'Announcement 와 Schedule 은 아직 이동하지 않는 비활성 카드입니다. 활성화 전까지 클릭 경로가 없습니다.'],
    ],
  },
  {
    id: 'admin',
    label: '관리자',
    title: '관리자 콘솔과 운영 관리',
    rows: [
      ['관리자 홈', '/admin 에서 버전/운영 모드, DB 상태, 최신 뉴스레터, 자산·읽음·AI 상태, 최근 감사 로그를 한 번에 확인합니다.'],
      ['권한/RBAC', 'admin/user/pending 역할, 직접 권한, 그룹 권한을 관리자 콘솔에서 관리합니다. pending 사용자는 대기 상태 UI, 본인 확인, 로그아웃만 허용됩니다.'],
      ['대시보드 모듈 관리', '대시보드 카드는 service_modules DB 에서 읽습니다. 관리자 콘솔에서 카드를 추가·삭제하고 Active/Development/Coming soon, 설명, 순서, 링크와 노출 대상(public: 모든 사용자 / admin: 관리자 전용)을 조정합니다.'],
      ['비밀번호 변경', '관리자 계정 / 비밀번호 섹션에서 현재 비밀번호를 확인한 뒤 새 비밀번호(8자 이상)로 교체합니다. 변경 즉시 다른 세션은 로그아웃됩니다. 초기 비밀번호는 27882788 이며 로그인 후 반드시 변경하세요.'],
      ['뉴스레터 운영', '목록에서 상태 필터, 검색, 일괄 게시/보관, 자산 상태 점검을 사용합니다. 카테고리/태그는 /admin 의 카테고리/태그 관리 섹션에서 생성·정렬·비활성화합니다.'],
      ['백업·검색·감사', '백업은 storage/admin_backups 아래 manifest+sha256 ZIP 으로 생성·검증합니다. 통합 검색은 Newsletter/Document/Civil/권한 있는 NSA 를 한 번에 찾고, 감사 로그는 관리자 변경·Sync·백업·읽음 purge 를 추적합니다.'],
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
] as const;

export function HelpManualButton() {
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>(MANUAL_SECTIONS[0].id);
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
