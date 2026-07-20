# Aero Work 최종 점검 보고서 — gongmuwon 대비 + 실 AI 테스트 + 폐쇄망 릴리스/Leantime 검토

- 작성일: 2026-07-20
- 대상: `aero-work-dev` HEAD `e873aec`
- 비교 원본: [Kminer2053/gongmuwon](https://github.com/Kminer2053/gongmuwon) (v0.1.12) + [사용설명서 11장](https://kminer2053.github.io/gongmuwon/manual/gongmu-user-manual.html)
- AI 테스트: **이 PC의 로컬 Ollama `gemma4:12b` 실호출** (16 케이스, 자체 생성 공무원 대화셋)
- 방식: 실측 — 라이브 서버 API 실행 + 브라우저 렌더 + 소스 대조

---

## 0. 한 줄 결론

| 질문 | 답 |
|---|---|
| gongmuwon 기능을 다 재현했나 | **핵심 100%**. 세부 3~4개 항목만 얕거나 미구현(§3) |
| 실 AI(gemma4:12b) 동작하나 | **예 — 16/16 케이스 실동작**, 근거 인용·개조식·정확한 값 추출 확인(§2) |
| 폐쇄망 릴리스해도 되나 | **소프트웨어는 준비 완료**. 한컴 실기 HWPX 확인 1건만 운영자 선결(§4) |
| Leantime 끄고 패키지에서 빼고 릴리스 가능한가 | **가능**. 폐쇄망 시작 경로엔 이미 Leantime 결합 0. 남은 건 admin 카드 1개 비활성 + 소스 4묶음 제외 — **소규모 작업**(§5) |

---

## 1. gongmuwon 대비 — 기능·UX·UI·사이즈·테마

### 1.1 아키텍처 (근본 차이)

| 항목 | gongmuwon | AeroOne Aero Work |
|---|---|---|
| 형태 | **독립 Tauri 2 데스크톱 앱**(작업표시줄 아이콘, WebView2) | AeroOne modular monolith 안의 **웹 모듈**(`/aero-work`, Development 카드) |
| 스택 | Tauri + React 19 + FastAPI(Py 3.11) | Next.js(App Router) + FastAPI + SQLite |
| AI 모델 | 로컬 Ollama **gemma-4 E2B**(멀티모달, 경량) — **설치팩에 모델 동봉** | 로컬 Ollama **gemma4:12b**(이 PC) — **모델 미동봉**, Ollama 별도 co-located |
| 설치 사이즈 | AI팩 **6.3GB**(4분할) + 앱, 실사용 12~20GB | 오프라인 ZIP **230MB**(python-wheels+installers, 모델 제외) |
| 진입 | 바탕화면/시작메뉴 네이티브 아이콘 | 브라우저 대시보드 → Aero Work 카드(admin) |

> **핵심**: gongmuwon은 "앱+모델을 한 번에 까는 단독 제품", AeroOne은 "이미 깔린 AeroOne+Ollama 위에 얹히는 업무 모듈". 폐쇄망 반입 단위가 다르다(gongmuwon=6.3GB 단일 제품 / AeroOne=230MB + 기존 Ollama 재사용).

### 1.2 기능 대조 (사용설명서 11장 기준)

| gongmuwon 기능 | AeroOne 구현 | 판정 |
|---|---|---|
| 업무대화 멀티인텐트 라우팅(§4.7 발화표) | `orchestrator_service`+`intent_router` | ✅ **동등**(실테스트 검증) |
| 근거 출처 답변 + 최신본 판별(§4.2) | `knowledge_service`+`version_ranker` | ✅ **동등**([근거 N]·최신본 실검증) |
| 실시간 스트리밍(§4.1) | `streaming.py` SSE | ✅ **동등**(hits→delta→done) |
| 문서 5양식: 시행문/1p/풀버전/이메일/임의형식(§5.2) | `document_formats` | ✅ **동등** |
| 종이(양식) 미리보기(§5.3) | `document_preview` | ✅ **동등** |
| 수정 지시 재생성(§5.1) | compose revise 루프 | ✅ **동등** |
| 승인형 최종 저장(§5.1, §11) | 문서 승인 상태기계 | ✅ **동등**(save→approve→download 실검증) |
| 지식폴더 색인·증분 동기화(§6.2) | `knowledge_service` reindex(백그라운드) | ✅ **동등**(202/진행률까지) |
| 분류체계 마법사 3단계(§6.6) | `taxonomy-wizard` | ✅ **동등**(실 LLM 3후보 검증) |
| 업무 허브 + 버전 이력(§6.5③) | `knowledge-wiki` 버전 가족 | ✅ **동등** |
| 키워드 즉시 강조(§6.4 왼쪽) | wiki `<mark>` 강조 | ✅ **동등**(레이아웃은 단일뷰) |
| 상세검색 근거 답변(§6.4 오른쪽) | 의미검색+합성 | ✅ **동등** |
| 일정 월/주/일 + 사전 알림(§7) | `schedule-month/week`+`reminder-banner` | ✅ **동등** |
| 실행기록(§8.1) | `activity_service` | ✅ **동등** |
| 환경설정 LLM 프로필(§8.2) | `prefs_service`(default/local) | ✅ **거의 동등**(외부 API는 provider 시스템) |
| 홈 오늘의 브리핑 | `home-briefing` | ✅ **동등** |
| 최초 실행 튜토리얼(§3.1) | `aero-work-onboarding` | ✅ **동등** |
| 파일·이미지 첨부(§4, 멀티모달) | `attachments`(텍스트+pdf/docx/hwpx) | ⚠️ **부분**(이미지 미지원 — §3) |
| 지식위키 **주제 페이지**(§6.5②) | — | ❌ **미구현**(§3) |
| 색인 **구조 보기**(섹션/표, §6.3) | 파일/청크 수 표시 | ⚠️ **얕음**(§3) |
| HWP(구버전 바이너리) 색인(§6.2) | `.hwpx`만 | ⚠️ **구버전 .hwp 미지원**(§3) |
| 화면 배율 −/100/＋(§3.2) | 브라우저 줌 + 다크 테마 | ⚠️ **대체**(§3) |

### 1.3 UX / UI / 테마

| 항목 | gongmuwon | AeroOne |
|---|---|---|
| 좌측 메뉴 | 6개(업무대화·일정·문서작성·지식폴더·실행기록·환경설정) | **7개**(+홈) |
| 우측 패널 | 컨텍스트·대기승인·최근작업·가까운일정·색인로그 | 업무엔진·가까운일정·지식색인·최근실행기록 |
| 아이콘 | 커스텀 SVG 세트(action + inverse 다크) | 이모지(🏠💬📅📝📚🧾⚙️) + 디자인 토큰 |
| 테마 | 라이트(종이 화이트) | 라이트 + **다크 토글** |
| 폭 | 데스크톱 고정 | 전폭(`max-w-none`) |
| 헤더 | 배율·새로고침·패널접기·엔진상태 | 버전배지(v2.0.0-dev)·다크·사용법·계정 |

**총평**: 기능 오케스트레이션(대화→일정→문서→지식)의 **정체성은 동등하게 재현**. UI는 gongmuwon이 전용 아이콘·네이티브 앱으로 더 다듬어져 있고, AeroOne은 디자인 시스템·다크테마·전폭으로 웹 통합에 최적화. 이모지 탭 vs 커스텀 SVG는 **취향/브랜딩 차이**(기능 손실 아님).

---

## 2. 실 AI 기능 테스트 (로컬 gemma4:12b, 16 케이스)

자체 생성한 공무원 실무 대화셋을 라이브 서버로 실행. 전량 `artifacts/qa/ai-test/ai-test-results.json`.

### 2.1 인텐트 라우팅 (규칙, 9/9 정확)
| 발화 | 라우팅 결과 |
|---|---|
| "내일 오전 10시 주간회의 일정 등록해줘" | `schedule.create` ✅ |
| "이번 주 일정 알려줘" | `schedule.list` ✅ |
| "내일 주간회의 일정 삭제해줘" | `schedule.delete` ✅ |
| "문서작성 어떻게 하는지 알려줘" | `help` ✅ |
| "…1페이지 보고서로 작성해줘" | `document` ✅ |
| "…시행문으로 작성해줘" | `document` ✅ |
| "…풀버전 보고서로…" | `document` ✅ |
| "…이메일 작성해줘" | `document` ✅ |
| "…등록하고 그 내용으로 보고서 작성해줘" | `[schedule.create, document]` ✅ 멀티인텐트 |

### 2.2 실 LLM 생성 (7/7, 실제 한국어 출력 발췌)
| 기능 | 소요 | 실제 gemma4:12b 응답(발췌) |
|---|---|---|
| 지식 근거(예산) | 12.4s | "2026년도 예산편성 원칙은 부서별 경상경비의 전년 대비 3% 절감이며, 신규 사업은 사전 타당성 검토서를 첨부해야 합니다 **[근거 1]**." |
| 지식 근거(민원) | 5.6s | "민원 처리는 법정 처리기한(통상 14일) 내에 처리하는 것을 원칙으로 합니다 [근거 1]." |
| SSE 스트리밍 | 4.4s | `hits→delta→done` · "워크숍 예산은 **3,450,000원**입니다 [근거 3]." (v2 최신본 정확 인용) |
| 문서 생성(1p) | 4.5s | 7문단 개조식 — "…적정 냉난방 온도 준수 및 소등 캠페인 추진 계획**임**" / "하절기 실내 냉방 온도를 28도 이상으로 유지하여…" |
| 문서 생성(시행문) | 2.5s | 4문단 공문체 — "정보보호 강화 및 보안 의식 고취를 위한 전 직원 대상 정보보안 교육을 실시**함**." |
| 파일 요약 | 2.9s | "- 부서별 경상경비의 전년 대비 3% 절감 원칙과 신규 사업 시 타당성 검토서 첨부 의무를 명시함. - 예산요구서 제출 기한(2026-08-14)…" |
| 분류체계 제안 | 4.8s | 3후보 — "예산편성 및 심의(1) / 민원 처리 관리(1) / 부서 워크숍 운영(2)" |

**판정**: 로컬 gemma4:12b로 **근거 인용·최신본 판별·개조식 공문체·정확한 수치 추출·분류 제안**이 전부 실동작. 폐쇄망 로컬 AI의 실무 품질이 확인됨. (참고: gongmuwon 기본 모델은 더 작은 gemma-4 E2B로, 이 PC의 12B는 그보다 큰 모델이라 품질이 더 안정적일 수 있음)

---

## 3. 부족한 부분 (정직한 갭)

| # | 갭 | gongmuwon | AeroOne 현재 | 영향 | 권고 |
|---|---|---|---|---|---|
| G-1 | **구버전 HWP(.hwp) 색인** | HWP/HWPX 지원 | `.hwpx`만(zip+xml) | 구형 한글 바이너리 문서 색인 불가 | 폐쇄망에 .hwp 자료 많으면 후속 추출기 필요. 아니면 제약 명시 |
| G-2 | **이미지 첨부(멀티모달)** | gemma-4 E2B 멀티모달, 클립보드 이미지 | 텍스트/pdf/docx/hwpx만, 이미지 필터됨 | 스크린샷 첨부 질의 불가 | gemma4:12b는 비멀티모달. 멀티모달 모델 채택 시 확장 |
| G-3 | **지식위키 주제 페이지** | 주제로 묶인 문서 카드(§6.5②) | 미구현(코드 주석에 후속 명시) | 주제 단위 탐색 부재(업무 허브로 일부 대체) | minor 후속 |
| G-4 | **색인 구조 보기** | 추출상태/파서/품질/섹션·표 구조(§6.3) | 파일/청크 수 | 색인 품질 디버깅 UI 얕음 | minor 후속 |
| G-5 | 화면 배율 컨트롤 | 헤더 −/100/＋ | 브라우저 줌 + 다크테마 | 기능 대체됨 | 불필요(웹 특성) |

**G-1, G-2가 유일한 실질 기능 갭**이며, 둘 다 "폐쇄망에 해당 자료(구 .hwp / 이미지)가 있느냐"에 따라 필요 여부가 갈립니다. 나머지(G-3~5)는 탐색 편의로 핵심 업무 흐름과 무관합니다.

---

## 4. 폐쇄망 릴리스 판정

**소프트웨어 준비 = 완료.** 근거:
- backend aero_work **286 passed**(재실행) · backend 전량 1,568 · frontend 652 · E2E 1 · 레드팀 92케이스
- 라이브 16기능 200 + 실 AI 16케이스 실동작
- 아키텍트 게이트 7회 APPROVE, 마이그레이션 단일 head 무결
- 오프라인 ZIP Task5 pre/post ok(entry 21,442·installer 2), 신규 wheel(pypdf·python-docx·lxml) 포함

**릴리스 선결(운영자 액션 — 코드 아님):**
1. **한컴 실기 HWPX 서식 확인** — 이 PC에 한컴 없음. 생성 HWPX의 zip/XML 구조는 자동 검증됐고 라이브에서 유효 PK 시그니처 확인(4,008B). 한컴에서 실제 열어 서식만 육안 확인하면 됨.
2. main 병합 · 2.0.0 태그 · Release(ZIP 동시 첨부) — AGENTS §9 승인 절차.

---

## 5. Leantime 비활성화 + 패키지 제외 릴리스 — 가능성 검토

### 5.1 현재 결합도 (실측)

| 위치 | Leantime 결합 | 폐쇄망 영향 |
|---|---|---|
| `start_offline.bat` / `setup_offline.bat` | **참조 0** | 폐쇄망 시작 경로엔 Leantime 없음 ✅ |
| `build_offline_package.ps1` / `offline_package_policy.py` / `installer-policy.json` | **참조 0**(정책상 명시 배제 아님, 단지 tracked 소스면 포함) | — |
| `scripts/run_all.bat` | **옵션 co-deploy 훅**(런처 파일 없으면 스킵, "Leantime 없어도 AeroOne 계속") | 무해(옵트인) |
| `scripts/leantime/` (11개 bat/ps1) | tracked → **ZIP에 포함됨** | 제외 대상 |
| `frontend/app/leantime/page.tsx` + BFF route | 안내 라우트 → **ZIP에 포함됨** | 제외 대상 |
| `frontend/components/office-tools/leantime-{dashboard,status,launch}.tsx` | 컴포넌트 → 포함됨 | 제외 대상 |
| `frontend/app/page.tsx` 카드 id=13 `leantime` | **admin 전용** Development 카드(`/leantime` 링크) | 비활성 대상 |
| backend `launchers` 모듈 · admin permissions | Leantime 런처 엔트리 | 비활성 대상 |
| `AeroOne-Leantime-Stack/` | **0바이트(빈 디렉터리)** | 실체 없음 |

### 5.2 판정: **가능 — 소규모 작업**

핵심 사실: **폐쇄망 실제 사용 경로(`start_offline.bat` + `/aero-work`)는 이미 Leantime과 무관**하고, Leantime 카드는 **admin에게만** 보이는 Development 실험 카드입니다. 따라서:

**"완전 제외" 릴리스에 필요한 작업(추정 소규모):**
1. **카드 비활성** — `frontend/app/page.tsx` FALLBACK의 `leantime` 카드(id 13) 제거 또는 `is_enabled:false` + service_modules 시드/마이그레이션에서 leantime 비활성. (진실 원천 3자리 정합: 마이그레이션·page.tsx FALLBACK·테스트)
2. **소스 제외** — `scripts/leantime/`, `frontend/app/leantime/`, `frontend/app/api/frontend/leantime/`, `frontend/components/office-tools/leantime-*.tsx` 를 offline allow-list 정책(`offline_package_policy.py`)의 **denylist**에 추가(제거 아님 — 소스는 dev에 유지, 패키지에서만 제외).
3. **런처 엔트리 정리** — backend `launchers` 에서 leantime 항목 제외(또는 service_modules 비활성만으로 UI 미노출이면 백엔드 유지 가능).
4. `run_all.bat` co-deploy 훅은 옵트인이라 **그대로 둬도 무해**(폐쇄망 setup/start와 무관). 원하면 훅 제거.
5. changelog·문서에 "Leantime 동거 기능은 이번 폐쇄망 릴리스에서 제외" 명시.

**리스크**: 낮음. Leantime은 흡수 UI가 아니라 링크+상태확인만 하는 동거 앱이라, 제거해도 Aero Work·뉴스레터·문서 등 핵심 기능에 의존성이 없음. 단, 진실 원천 3자리 정합과 관련 vitest(`leantime-dashboard.test.tsx`, `external-launcher-card.test.tsx`, `service-card.test.tsx`) 갱신은 필수.

**권고**: 별도 feature 브랜치 `feature/release-exclude-leantime`에서 (1) service_module 비활성 마이그레이션 + page.tsx FALLBACK 정합 + 관련 테스트 갱신 → (2) `offline_package_policy` denylist 확장 → (3) ZIP 재빌드로 leantime 부재 확인 → 게이트. **이 작업은 승인 시 즉시 착수 가능한 소규모 단위**입니다.

---

## 6. 최종 권고

1. **Aero Work 자체는 폐쇄망 릴리스 준비 완료** — 지금 `setup_offline.bat`→`start_offline.bat`로 쓸 수 있고, 실 AI가 로컬 gemma로 정상 동작.
2. **운영자 선결 2건**: 한컴 실기 HWPX 육안 확인 → 배포 승인(main 병합·2.0.0 태그·Release).
3. **Leantime 완전 제외 릴리스는 가능하며 소규모** — 승인해 주시면 위 §5.2 계획으로 별도 브랜치에서 진행하겠습니다.
4. 선택적 후속(폐쇄망 자료 성격에 따라): 구 .hwp 추출(G-1), 이미지 멀티모달(G-2).

---

## 부록: 증거
- 실 AI 테스트: `artifacts/qa/ai-test/ai-test-results.json`(16 케이스) + `run.log`
- UI 스크린샷: `artifacts/qa/ai-test/ui-{schedule,document,knowledge,settings}.png` + `artifacts/qa/final-audit-aerowork-home.png`
- 회귀: `artifacts/qa/final-audit-aerowork-pytest.log`(286 passed)
- gongmuwon 대조: README v0.1.12 + 사용설명서 11장
