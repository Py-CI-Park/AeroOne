type GuideExample = {
  prompt: string;
  result: string;
};

type GuideFeature = {
  title: string;
  what: string;
  how: string;
  examples?: readonly GuideExample[];
};

type GuideSection = {
  id: string;
  title: string;
  description?: string;
  adminOnly?: boolean;
  setupSteps?: readonly string[];
  features?: readonly GuideFeature[];
  tips?: readonly string[];
};

const GUIDE_SECTIONS: readonly GuideSection[] = [
  {
    id: 'introduction',
    title: '소개',
    description: 'Aero Work는 대화 한 줄로 일정·문서·지식·할 일을 잇는 폐쇄망 로컬 AI 업무 공간입니다. 외부 인터넷 없이 동작합니다.',
  },
  {
    id: 'setup',
    title: '처음 세팅(설정)',
    adminOnly: true,
    setupSteps: [
      '로컬 AI(Ollama): 대화 gemma4:12b, 임베딩 nomic-embed-text(768차원)를 사용합니다. Ollama가 다른 PC에 있으면 backend/.env의 OLLAMA_BASE_URL을 http://<ip>:11434로 설정합니다. 연결 상태는 환경설정 탭에서 확인합니다.',
      'OpenAI 호환 연결(선택, 폐쇄망 게이트웨이): ① 관리자 콘솔 LLM 연결에 base_url+API key를 등록·선택합니다. ② Aero Work 환경설정 프로필을 default로 설정합니다. ③ .env에 AI_COMPATIBLE_ALLOWED_CIDRS(기본 127.0.0.1/32,::1/128)·AI_COMPATIBLE_ALLOWED_HOSTNAMES·AI_COMPATIBLE_EMBED_MODEL(예: text-embedding-3-small)을 설정합니다. ④ provider 전환 시 지식폴더를 재색인해야 하며 임베딩 차원 768↔1536 혼합은 금지합니다.',
      '지식폴더 허용 루트(선택): .env의 AERO_WORK_KNOWLEDGE_ROOTS에 콤마로 구분한 절대경로를 설정합니다. 비어 있으면 하위호환을 위해 임의 절대경로를 허용합니다.',
    ],
  },
  {
    id: 'features',
    title: '기능별 활용법',
    features: [
      {
        title: '업무대화(핵심)',
        what: '대화 한 줄을 인텐트로 라우팅해 일정·지식 검색·문서·할 일·도움말을 연결합니다.',
        how: '파일 첨부(.pdf/.docx/.hwpx 등, 최대 5개) 후 내용 근거를 질문할 수 있으며 첨부 원문은 저장하지 않습니다. 자유 대화 모드에서는 로컬 AI와 이어서 대화합니다.',
        examples: [
          { prompt: '내일 오전 10시 주간회의 일정 등록해줘', result: '일정 생성' },
          { prompt: '예산 편성 근거 찾아줘', result: '지식 검색·근거 답변' },
          { prompt: '청사 에너지 절감 방안을 1페이지 보고서로 작성해줘', result: '문서 생성' },
          { prompt: '내일까지 예산보고서 초안 할 일 추가해줘', result: '할 일' },
          { prompt: '문서작성 어떻게 하는지 알려줘', result: '도움말' },
          { prompt: '내일 오후 2시 부서 워크숍 등록하고 그 내용으로 보고서 작성해줘', result: '일정+문서' },
        ],
      },
      {
        title: '일정',
        what: '일정을 추가·수정·삭제하고 주/월 보기와 알림(remind_before_minutes)을 관리합니다.',
        how: '같은 제목의 일정이 여러 건이면 즉시 삭제하지 않고 후보를 돌려 재확인하여 오삭제를 방지합니다.',
      },
      {
        title: '문서작성',
        what: '제목·본문에서 문서를 작성해 HWPX(한글 OWPML)로 다운로드합니다.',
        how: '5개 양식(시행문·1페이지·풀버전·이메일·임의형식)을 종이 미리보기로 확인합니다. 수정 지시로 이전 초안을 반영해 재생성하고 승인형으로 최종 저장합니다.',
      },
      {
        title: '내 지식폴더',
        what: '등록한 절대경로 폴더를 배경 색인하고 의미(벡터)·키워드(FTS5 부분일치) 검색과 SSE 스트리밍 근거 답변을 제공합니다.',
        how: '색인 진행률을 확인하며 추가·수정·이동·삭제를 증분 동기화합니다. 각 사용자는 자기 계정 소유 폴더만 조회·검색하는 멀티유저 격리를 적용합니다.',
      },
      {
        title: '분류체계 마법사',
        what: '업무 니즈를 바탕으로 LLM 분류 후보를 제안합니다.',
        how: '후보를 검토한 뒤 적용하면 지식위키 업무 허브에서 대표 공식본과 관련 판본을 함께 봅니다.',
      },
      {
        title: '할 일(To-do)',
        what: '마감·상태(할일/진행/완료)를 중심으로 관리하는 경량 태스크입니다.',
        how: '업무대화에서 할 일 추가/목록/완료를 요청하거나 "할 일" 탭에서 직접 관리합니다. 이번 버전(1.19.0)에 새로 추가된 기능입니다.',
      },
      {
        title: '실행기록',
        what: '색인·검색·일정·문서 작업을 최신순 타임라인으로 보여 줍니다.',
        how: '작업 흐름을 투명하게 확인합니다.',
      },
      {
        title: '환경설정',
        what: '로컬 AI 연결 상태와 LLM 프로필(default/local)을 확인합니다.',
        how: '전체 사용법을 다시 볼 수 있습니다.',
      },
    ],
  },
  {
    id: 'offline-deployment',
    title: '폐쇄망 배포 요약',
    adminOnly: true,
    setupSteps: [
      '온라인 PC에서 offline_package.bat을 실행해 ZIP을 만듭니다.',
      '폐쇄망 PC에서 setup_offline.bat을 실행한 뒤 start_offline.bat으로 시작합니다.',
      'Ollama 모델 blob(gemma4:12b, nomic-embed-text)을 %USERPROFILE%\\.ollama\\models로 복사합니다.',
    ],
  },
  {
    id: 'tips',
    title: '팁·주의',
    tips: [
      '지식폴더는 본인 계정 소유로 격리됩니다.',
      'provider 전환 시 지식폴더를 재색인합니다.',
      '첨부 원문은 저장하지 않습니다.',
      '삭제 대상이 모호하면 후보를 재확인합니다.',
    ],
  },
] as const;

function AdminBadge() {
  return <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">관리자/운영자</span>;
}

export function AeroWorkGuidePanel() {
  return (
    <section className="rounded-xl border border-line-subtle bg-surface-raised p-5 text-ink-1" data-testid="aero-work-guide">
      <header className="border-b border-line-subtle pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ink-3">Aero Work Guide</p>
        <h2 className="mt-1 text-2xl font-semibold">Aero Work 사용법</h2>
        <nav className="mt-3 flex flex-wrap gap-2" aria-label="사용법 목차">
          {GUIDE_SECTIONS.map((section) => (
            <a key={section.id} href={`#aero-work-guide-${section.id}`} className="rounded-full border border-line-subtle px-3 py-1 text-xs text-ink-2 hover:bg-surface-sunken">
              {section.title}
            </a>
          ))}
        </nav>
      </header>

      <div className="mt-5 space-y-8">
        {GUIDE_SECTIONS.map((section) => (
          <article key={section.id} id={`aero-work-guide-${section.id}`} className="scroll-mt-4">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-semibold">{section.title}</h3>
              {section.adminOnly ? <AdminBadge /> : null}
            </div>
            {section.description ? <p className="mt-2 text-sm leading-6 text-ink-2">{section.description}</p> : null}
            {section.setupSteps ? (
              <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-ink-2">
                {section.setupSteps.map((step) => <li key={step}>{step}</li>)}
              </ol>
            ) : null}
            {section.features ? (
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {section.features.map((feature) => (
                  <section key={feature.title} className="rounded-lg border border-line-subtle bg-surface-base p-4">
                    <h4 className="font-semibold text-ink-1">{feature.title}</h4>
                    <p className="mt-2 text-sm leading-6 text-ink-2"><strong className="text-ink-1">무엇:</strong> {feature.what}</p>
                    <p className="mt-1 text-sm leading-6 text-ink-2"><strong className="text-ink-1">어떻게:</strong> {feature.how}</p>
                    {feature.examples ? (
                      <div className="mt-3 space-y-2" aria-label={`${feature.title} 예시`}>
                        {feature.examples.map((example) => (
                          <div key={example.prompt} className="rounded-md bg-surface-sunken px-3 py-2 font-mono text-xs leading-5 text-ink-2">
                            <span>{example.prompt}</span><span className="px-1 text-ink-3">→</span><span>{example.result}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ))}
              </div>
            ) : null}
            {section.tips ? (
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-ink-2">
                {section.tips.map((tip) => <li key={tip}>{tip}</li>)}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
