# Aero Work — gongmuwon 기능의 AeroOne 네이티브 재구현 계획 (다음 버전)

- 상태: **P0~P4 구현 완료 + P3 기본 구현(`aero-work-dev` 브랜치, 1.17.0 태그 기준 분기)** — 7메뉴(홈 브리핑·업무대화·일정·문서작성·지식폴더·실행기록·환경설정) 모두 기능 동작. 잔여: 알림(폐쇄망 in-app 배지)·HWPX 서식 템플릿·P5(통합/성능/phase 보고서/릴리스 스코프 결정). 1.17.x 릴리스는 게시 완료. 상세는 §4.
- 대체 관계: 본 문서는 [`gongmuwon-integration-review.md`](gongmuwon-integration-review.md) 의 "외부 앱 내장" 권고를 **대체**한다. 운영자 결정에 따라 방향이 **"외부 gongmuwon 연동" → "AeroOne 안에 네이티브 재구현(Aero Work)"** 으로 바뀌었다.
- 목표: gongmuwon(공무원)의 전 기능을, **더 개선된 React 시스템**으로 AeroOne 안에 `Aero Work` 라는 이름의 워크스페이스 모듈로 구현한다.
- 전제: AI 는 **폐쇄망 Ollama + OpenAI 호환 API 키가 이미 AeroOne 에 있음** → gongmuwon 의 6.3GB **AI 팩은 반입/번들하지 않는다**. AeroOne 의 기존 AI provider(Ollama·OpenAI 호환, DPAPI 보호 키, egress 정책)를 그대로 재사용한다.
- 라이선스 경계: gongmuwon 저장소 License 는 "Other". **코드 복사 금지**, UX·기능을 참고해 **AeroOne 스택으로 새로 구현**한다. 착수 전 라이선스 실검토 필수.

---

## 1. gongmuwon 6대 기능 → AeroOne 자산 매핑

| gongmuwon 기능 | AeroOne 기존 자산(재사용) | 신규 구현 필요분 | 난이도 |
|---|---|---|---|
| **업무대화**(근거·출처 인용 챗, 파일·이미지 첨부) | **AeroAI**(`/ai`): SSE 스트리밍, 파일 첨부, 문서 근거 답변, Ollama+OpenAI provider, egress 정책, AI 대화 저장 | 세션 중심 워크플로(대화 → 일정/문서작성으로 이어가기) 링크 | 낮음(대부분 재사용) |
| **내 지식폴더**(폴더 in-place 색인·업무 위키·키워드/근거 검색·증분 동기화) | Document/NSA/Civil(HTML 열람·본문 검색), Open Notebook(임베딩 모델 `nomic-embed-text` 이미 운영) | 지정 폴더 **in-place 색인기** + **임베딩 벡터 검색** + **증분 동기화** + 업무 위키 자동 구성 | **높음(핵심 신규)** |
| **문서작성**(지시→구조검토→**HWPX 생성**, 임의형식 빈칸 채움) | Office Studio(Markdown→HTML 보고서·차트·다이어그램), 서버 sanitize 렌더 | **HWPX(한글) 생성기**(OWPML), 미리보기→HWPX 왕복, 양식 슬롯 채움 | **높음(핵심 신규)** |
| **일정**(월/주/일 캘린더·사전 알림·세션 연결) | (없음 — 대시보드 "Schedule" 이 coming_soon 자리표시자) | 캘린더 모델·UI + 알림 + 세션 연결 | 중 |
| **실행기록**(입출력과 함께 투명 기록) | admin **감사 로그**(record_admin_audit), AI 운영 로그(metadata-only) | 사용자 관점 실행기록 뷰(쉬운 우리말) | 낮음(확장) |
| **환경설정**(LLM 프로필 전환·튜토리얼) | admin AI provider 설정, 테마, 사용법 매뉴얼 | 사용자 프로필 전환 UI(관리자 provider 위에) | 낮음 |
| 홈 '오늘의 브리핑' | 대시보드, 최근 열람 스트립 | 브리핑 위젯(일정·이어서 하기·지식 요약) | 낮음 |

요약: **업무대화·실행기록·환경설정·브리핑은 AeroOne 자산 재사용으로 저비용**. 핵심 신규는 **① 지식폴더 벡터 색인, ② HWPX 문서 생성, ③ 일정/알림** 세 가지다.

## 2. 핵심 신규 3종의 타당성

### 2.1 지식폴더 in-place 벡터 색인 (feasible)
- 임베딩: AeroOne 이 이미 폐쇄망에서 Ollama `nomic-embed-text`(Open Notebook 용)를 운영 → **모델 신규 반입 불필요**. `/api/embeddings` 로 폴더 파일 청크를 임베딩.
- 벡터 저장/검색: SQLite 단일 파일 정책과 정합하는 **`sqlite-vec` 확장** 또는 순수 Python 코사인(수천~수만 청크 규모면 충분). AeroOne DB 가 이미 `_database/db/` 로 이관돼 백업/이관 일관.
- in-place·증분: 지정 폴더를 **복사 없이** 스캔(경로·mtime·hash 시그니처는 뉴스레터 auto-sync 패턴 재사용), 추가·수정·이동·삭제를 증분 반영.
- 위험: 대용량 폴더 초기 색인 시간, 파일 형식 파서(PDF/HWPX/DOCX 텍스트 추출) 범위. 폐쇄망 순도(외부 임베딩 금지)는 loopback Ollama 로 충족.

### 2.2 HWPX(한글) 문서 생성 (feasible, 최대 난관)
- HWPX 는 **OWPML(=ZIP + XML)** 포맷. python `docx`/`pptx` 처럼 **ZIP+XML 직접 생성**으로 구현 가능(외부 SaaS·인터넷 불필요 → 폐쇄망 적합).
- 접근: (a) 최소 OWPML 템플릿(빈 .hwpx)을 골격으로 두고 본문 문단·표·붙임을 XML 로 주입, (b) 시행문·1p·풀버전·이메일·임의형식(양식 슬롯 채움) 템플릿 세트. Office Studio 의 "Markdown→구조→렌더" 파이프라인과 미리보기 계약을 재사용하되 **산출물만 HWPX**로 확장.
- 위험: OWPML 스펙 준수·한컴 호환성 검증 공수. 1차는 시행문/1p 등 **고빈도 서식 소수**부터, 임의형식은 2차.
- 라이선스: HWPX 생성은 표준 포맷 구현이라 gongmuwon 코드 없이 독립 구현 가능(단, 참고 라이브러리 라이선스 확인).

### 2.3 일정/알림 (feasible)
- 캘린더 모델(이벤트·기간·알림 리드타임) + 월/주/일 뷰(React). 알림은 브라우저 알림/앱 내 배지(폐쇄망이라 이메일/푸시 없음). 업무대화 세션 ↔ 일정 링크.
- 대시보드 "Schedule" coming_soon 자리를 Aero Work 일정으로 승격.

## 3. 아키텍처 (AeroOne 기존 스택 준수)

- 프런트: **Next.js App Router(React)** — `/aero-work` 워크스페이스(좌측 메뉴 6종, 세션 중심). 기존 AppShell·테마·권한(ClientSession) 계약 재사용. "더 개선된 리액트"는 SSR+스트리밍, 세션 중심 IA, 컴포넌트 분해로 달성.
- 백엔드: **FastAPI** `app/modules/aero_work/`(chat/knowledge/document/schedule/log 하위). AeroAI egress·provider·AI 저장, 문서 스토리지(StorageService), 감사 로그 재사용.
- 데이터: 전부 로컬 `_database/`(DB `_database/db/`, 지식폴더는 in-place 색인 → 원본 미복사). 폐쇄망 순도·오프라인 ZIP 정책(대용량 제외) 유지.
- 권한: 신규 permission key(`aerowork.*`) + service_modules 카드(Development 또는 신규 "Work" 섹션). 드래그 순서변경/관리자 콘솔과 정합.

## 4. 단계 계획 (1.17.0 게시 이후 새 브랜치)

- **선행 게이트**: 1.17.0 을 main 병합·tag·GitHub Release·ZIP 게시로 **먼저 마감**(AGENTS §9). 그 후 `<차기버전>-dev` 브랜치 분기. 범위상 신모듈 다수라 **minor 이상(1.18.0) 또는 major(2.0.0)** 로 판단.
- **P0** ✅ 구현됨(`e68e3b7`, aero-work-dev): 스캐폴딩 — `/aero-work` 셸 + 6메뉴 IA + 홈 브리핑.
- **P1** ✅ 구현됨(`818aef0`): 업무대화 — AeroAI(`AiChatWorkspace`) 재사용. 세션 중심 이어가기 링크는 후속.
- **P2** ✅ 구현됨(`59939a4`): 지식폴더 — 신규 `app/modules/aero_work`(폴더/파일/청크 3층 + 마이그레이션 `20260719_0020`), in-place 스캔 + Ollama `nomic-embed-text` 임베딩(urllib, AeroAI 경로 재사용) + 순수 Python 코사인 검색 + 시그니처(mtime+size) 증분 동기화. `KnowledgePanel`(등록·재색인·삭제·검색) + BFF 프록시. 검증: 단위 6건 + 마이그레이션 up/down + **실 Ollama 한국어 의미검색 E2E 3/3 정답**. 업무 위키 자동 구성, PDF/DOCX/HWPX 본문 추출, 백그라운드 색인, 세분 `aerowork.*` 권한·카드는 후속.
- **P3** ✅ (기본 구현): 문서작성 — 제목·본문(한 줄=한 문단)을 미리보고 **HWPX(한글, OWPML)로 생성·다운로드**. `hwpx_generator`(mimetype stored 선두 + version/settings/header/section0/content.hpf + META-INF 를 ZIP+XML 로 직접 조립, 외부 의존 0) + REST(CSRF, `document.generate` 기록) + `DocumentPanel`(미리보기 + 다운로드). 검증: 구조 유효성 단위 6(유효 ZIP·mimetype·필수 파트·XML well-formed·본문 주입·이스케이프) + 통합 3(익명 401·CSRF 403·다운로드+기록). **한컴 실기 렌더 호환은 한컴 설치 PC에서 확인 필요(실험적)** — 본 환경엔 한컴 없음. 시행문/1p 서식 템플릿·양식 슬롯 채움·임의형식은 후속.
- **P4**: (완료, 알림 제외) **일정 ✅** — 이벤트 CRUD + 기간 겹침(`20260719_0021` + `ScheduleService` + `SchedulePanel`). **홈 브리핑 ✅** — 일정+지식 요약(`HomeBriefing`). **실행기록 ✅** — 워크스페이스 행위를 각 라우트가 자동 기록(`20260719_0022` + `AeroWorkActivity` + `record_activity` 훅 + `ActivityLogPanel`, 소유자 스코프). **환경설정 ✅** — 로컬 AI 연결 상태 라이브 확인(`fetchAiStatus` 재사용) + 전체 사용법(`HelpManualButton` 재사용), 프런트 전용. 검증: 일정 단위 5+통합 5, 실행기록 단위 4+통합 3, tsc 0. **알림(폐쇄망 in-app 배지)만 후속**.
- **P5**: 통합 UX·성능 예산·문서·회귀 테스트 + 각 단계 phase 보고서(minor/major 는 phase 보고서 필수, AGENTS §9.6).

## 5. 위험과 선결 조건

| 위험/조건 | 대응 |
|---|---|
| **라이선스(Other)** | 착수 전 gongmuwon 라이선스 실검토. 코드 복사 없이 기능만 참고해 독립 구현 |
| **HWPX 스펙 공수** | 고빈도 서식 소수부터(시행문/1p), 한컴 호환 실검증. 임의형식 2차 |
| **범위(사실상 앱 하나)** | 단일 릴리스 금지 — 다중 phase·다중 릴리스 트랙. major(2.0.0) 가능성 |
| **폐쇄망 순도** | 임베딩=loopback Ollama, 문서생성=로컬 XML, 인터넷 의존 0 유지 |
| **번들 정책** | AI 팩 미반입(전제 충족). 신규 대용량 자산은 오프라인 ZIP 제외 정책 준수 |
| **기능 중복** | AeroAI/Office Studio/Document 와 역할 경계 확정 후 착수(Aero Work 는 세션 중심 워크스페이스로 통합) |

## 6. 결론

gongmuwon 의 강점(HWPX·지식폴더·세션 중심 업무 흐름)은 AeroOne 의 폐쇄망 로컬 AI 방향과 정확히 일치한다. **업무대화·실행기록·환경설정·브리핑은 AeroOne 자산 재사용으로 빠르게**, **지식폴더 벡터 색인·HWPX 생성·일정** 3종만 신규 구현하면 `Aero Work` 로 전 기능을 더 개선된 React 시스템으로 완성할 수 있다. AI 팩 없이(기존 Ollama/OpenAI 재사용) 폐쇄망 순도를 지키며, **1.17.0 게시 후 새 브랜치에서 P0→P5 단계**로 진행하는 것을 권고한다. 착수 전 **라이선스·HWPX 공수·기능 중복·범위(major 여부)** 4가지를 확정한다.
