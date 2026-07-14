# AeroOne Tool — 두 MVP 통합 분석: 역사적 분석 기록 (2026-07-11)

> **문서 상태:** §0~§9는 구현 전의 비교·권고를 보존한 역사적 분석이다. §10도 2026-07-12의
> 완료 스냅샷으로 보존하며 현재 배포·운영 계약이 아니다. 현재 Office Studio와 Leantime의
> 운영 사실은 [`docs/runbook/office-tools.md`](../docs/runbook/office-tools.md) 및
> [`docs/runbook/leantime-codeploy.md`](../docs/runbook/leantime-codeploy.md)를 우선한다.
>
> **2026-07-13 현재 기준:** Office는 `office.use` 권한의 단일 `Office Studio` 허브
> (`/office-tools`)이며 AI 미구성·실패 시 규칙 기반 폴백을 쓴다. Office 카드와 Leantime 내부
> 안내 카드(`/leantime`)의 최종 마이그레이션 head는 `20260712_0014`이고 frontend fallback ID는
> 각각 `11`, `12`다. owner 격리·quota·보존·관리자 purge/recovery lifecycle 계약과 413/422
> 업로드 계약은 `office-tools.md` 및 `backend/app/modules/office_tools/`가 진실 원천이다.
>
> 원본 MVP 보존 위치: `AeroOne Tool/_originals/*.zip`, 추출본: `tool-mvp-v0.1.0/`,
> `saas-kit-v2.0.0/`.

---

## 0. [역사 기록] 결론 먼저

두 MVP는 성격이 정반대라 통합 경로도 다르다.

- **Tool MVP (`aeroone_tool` v0.1.0)** = 보고서·차트·다이어그램 3종 오피스 도구. 백엔드가 **표준 FastAPI 라우터**라 AeroOne 백엔드에 `include_router`로 **흡수 가능**. 대시보드 카드 3개(또는 1개 묶음)로 "로그인 후" 노출이 현실적. 4대 과제 = ① 인증 전무 → AeroOne 세션으로 감싸기, ② LLM 백엔드 불일치(OpenAI 호환 vs Ollama), ③ CairoSVG/Matplotlib/CJK 폰트 네이티브 의존성(폐쇄망 Windows 마찰), ④ 별도 Vite SPA를 iframe 임베드 vs Next.js 이관.
- **SaaS Kit (`AeroOne_Offline_SaaS_Kit` v2.0.0)** = 파이썬 stdlib `http.server` + SQLite + vanilla HTML로 만든 **서비스 포털 + Leantime(업무관리) 오프라인 설치기**. 스택이 AeroOne(Next.js+FastAPI+Postgres)과 근본적으로 달라 **코드 흡수가 아니라 "개념 이식 + 재해석"** 이 맞다. 그런데 이 포털이 하는 일(서비스 카드 목록 + 상태표시)은 **AeroOne이 이미 `service_modules`로 하고 있는 일과 겹친다.** 그래서 이 MVP의 실질 가치는 (a) **서비스 헬스체크(상태 점등) 도메인 모델**, (b) **Leantime을 외부 링크 도구 카드로 추가**하는 아이디어, (c) AGPL 라이선스·오프라인 번들 절차이며, EXPERIMENTAL_PLANE는 지금 배포 대상이 아니다.

한 줄 권고: **Tool MVP → 실제 코드 이식(카드형 도구 3종). SaaS Kit → 포털은 재구현하지 말고 헬스체크 개념만 흡수 + Leantime을 외부 도구 카드로.**

---

## 1. 두 패키지 한눈에 비교

| 항목 | Tool MVP (`aeroone_tool` v0.1.0) | SaaS Kit (`AeroOne_Offline_SaaS_Kit` v2.0.0) |
|---|---|---|
| 정체 | 오피스 도구 3종(보고서/차트/다이어그램) | 서비스 포털 + Leantime 오프라인 배포기 (+실험적 Plane) |
| 백엔드 | **FastAPI 0.115** + Uvicorn (포트 8088) | 파이썬 **표준 라이브러리 `http.server`** (포트 8765) |
| 프런트 | React 18 + **Vite** SPA (dist 사전빌드, 해시 라우팅) | **vanilla HTML/CSS/JS** 정적 파일 |
| DB | **없음** (파일시스템 JobStore) | **SQLite** (WAL, 5테이블) |
| LLM | OpenAI 호환 `gpt-oss-120b`, **선택적**+Fallback | vLLM `/v1/models` 헬스체크만(도구가 아니라 링크) |
| 인증 | **없음**(네트워크 경계 전제) | PBKDF2 로컬 관리자 + 세션 + CSRF |
| AeroOne 스택 정합성 | **높음**(FastAPI 동종, 라우터 이식 가능) | **낮음**(스택 전면 상이 → 재구현) |
| AeroOne 기능 중복 | `render`(md→html), `reports`, `ai` 일부 | **대시보드 자체(`service_modules`)와 정면 중복** |
| 페이로드 무게 | 중(네이티브 의존성 있음) | 대(포털 + IIS/PHP/MariaDB Leantime) |
| 지금 취할 것 | **코드 이식(3 도구)** | **개념(헬스체크) + Leantime 링크 카드** |

---

## 2. AeroOne에 "로그인 후 보이는 도구"를 붙이는 공통 패턴

AeroOne은 이미 도구를 카드로 붙이는 정형 패턴이 있다(예: `/ai`, `/games/ladder`, `/viewer`). 새 도구는 아래 5자리를 채우면 대시보드에 등장한다.

| # | 자리 | 파일/위치 | 역할 |
|---|---|---|---|
| 1 | 대시보드 카드(DB) | `backend/alembic/versions/*_.py` 새 마이그레이션에서 `service_modules` **bulk_insert** | 카드가 대시보드에 뜨게 함 (key/title/href/section/status/visibility/sort_order) |
| 2 | 대시보드 카드(Fallback) | `frontend/app/page.tsx`의 `FALLBACK_MODULES` 배열 | DB 장애 시에도 카드 유지(회귀 계약 `frontend/tests/app/home-page.test.tsx`) |
| 3 | 프런트 페이지 | `frontend/app/<tool>/page.tsx` (App Router, `AppShell` 사용) | 카드가 여는 실제 화면 |
| 4 | 백엔드 모듈 | `backend/app/modules/<tool>/` + `backend/app/main.py`에 `include_router`(prefix `/api/v1/<tool>`) | 서버 로직 |
| 5 | 동일 오리진 프록시 | `frontend/app/api/frontend/<tool>/[...segments]/route.ts` | Next → FastAPI same-origin 프록시(쿠키 전달, degraded fallback) |

부가:
- **인증**: 백엔드 라우터에 AeroOne `auth.dependencies`(세션 쿠키 필요)를 걸면 자동으로 "로그인해야 동작". 카드 노출은 `visibility`(`public`=로그인 전원 / `admin`=운영자)로 제어. → 사용자가 원한 "로그인하면 보이는"은 `visibility='public'`(개발 중엔 `'admin'`으로 시작 권장), "추후 로그인 없이"는 이후 별도 공개 라우트 작업.
- **LLM**: 신규 도구는 AeroOne 기존 LLM 게이트웨이(현재 `core/config.py`의 Ollama `gemma4:12b` @11434)를 재사용해야 한다. Tool MVP의 자체 `llm_client.py`(OpenAI 호환 gpt-oss-120b)와 불일치 → §4 결정 필요.
- **오프라인**: 백엔드 uvicorn **18437**, 프런트 Next.js **29501**, SQLite + alembic, `wheelhouse`로 의존성 설치. 신규 도구의 포트(8088/8765/8081)는 **도입 금지** — 전부 기존 두 프로세스 안으로 흡수.
- **변경 트라이앵글(CLAUDE.md §2.3)**: 코드 / 테스트 / 문서 / batch·offline 4자리를 한 커밋에 함께.

---

## 3. Tool MVP — 목적·구조·적용성

### 3.1 왜 이 MVP인가 (목적)
폐쇄망에서 보고서 양식화·데이터 시각화·업무 도식화를 반복하는데, 일반 생성형 AI를 직접 쓰면 (a) 임의 HTML/JS 생성 위험, (b) 수치 환각, (c) 외부 CDN/폰트 차단 문제가 있다. 그래서 **"LLM은 제한된 명세(ChartSpec/Mermaid/편집 Markdown)만 제안 → 앱이 재검증 → 고정 렌더러가 최종 산출물 생성"** 구조를 아키텍처로 고정하고, **모델이 꺼져도 3서비스가 규칙 기반 Fallback으로 동작**하게 했다. 스스로를 "AeroOne 반영 전 PoC/MVP"로 규정.

### 3.2 서비스별 구조

| 서비스 | 입력 | 산출물 | 렌더 방식 | AeroOne 기존 중복 |
|---|---|---|---|---|
| SVC-01 보고서 | .md/.txt + 이미지/ZIP + 메타 | 정제·이미지내장·(AI편집) 단일 오프라인 HTML + ZIP | bleach 정제 → vendor `build_report.py` **subprocess** | `render`(md→html sanitize)와 부분 중복(단, 보고서 포맷팅·이미지 임베드는 상위) |
| SVC-02 차트 | CSV/XLSX/JSON + 목적문장 | ChartSpec/ECharts option/SVG/PNG/집계CSV + ZIP | pandas 집계 + Matplotlib(SVG/PNG) + 브라우저 ECharts | 신규 |
| SVC-03 다이어그램 | 자연어 + 유형(flow/seq/state/gantt) | Mermaid .mmd/spec + 브라우저 SVG/PNG + (서버 PNG) | 브라우저 Mermaid(strict) + 서버 CairoSVG PNG | 신규 |

### 3.3 적용성 판정: **높음 (코드 이식 가능)**
- 백엔드 `backend/app/api/routes/*`가 표준 `APIRouter` → `include_router`로 흡수. `tools/svc0*`는 순수 파이썬 파이프라인이라 모듈로 이동 가능(임포트 경로만 조정).
- LLM 선택적 + Fallback → 폐쇄망에서 LLM 미가용이어도 동작.
- 경로 traversal 방어·콘텐츠 새니타이저 이미 구비.

---

## 4. Tool MVP — AeroOne 배포 순서 (단계별)

| 순서 | 단계 | 구체 작업 | 산출/검증 |
|---|---|---|---|
| T0 | 범위·결정 확정 | (a) 3서비스 전부 vs 우선 1개, (b) LLM: Ollama로 통일 vs OpenAI호환 게이트웨이 유지, (c) 차트/다이어그램 서버 PNG(CairoSVG) 포함 vs 브라우저 렌더만, (d) 프런트: iframe vs Next 이관 | 결정 표 |
| T1 | 백엔드 모듈 이식 | `tools/svc0*` + `core/{job_store,security,llm_client}`를 `backend/app/modules/office_tools/`로 이동, 절대임포트(`backend.app.core.*`) → AeroOne 경로로 수정, `settings` 싱글턴을 AeroOne `core/config` 주입 방식에 맞춤 | 백엔드 import 성공 |
| T2 | LLM 게이트웨이 접속 | `llm_client.py`를 AeroOne 기존 LLM 설정(Ollama 또는 사내 OpenAI호환)로 배선. base_url/모델/타임아웃을 `core/config.py`로 통일. API Key는 서버 env only | `/health`의 `llm_configured` 확인 |
| T3 | 라우터 등록 + 인증 | `main.py`에 `include_router(prefix='/api/v1/office-tools')`, 각 라우트에 AeroOne 세션 의존성 부여(로그인 필수), CORS/보안헤더는 AeroOne 것으로 통일 | 미로그인 401 확인 |
| T4 | JobStore 경로 정리 | `data/jobs/`를 AeroOne 런타임 데이터 경로(gitignore된 `backend/data/`)로, 산출물 정리 스케줄(`scripts/cleanup_jobs.py`) 편입 | 산출물 생성/다운로드 확인 |
| T5 | 프런트 노출 | **(A안 빠름)** 프런트 프록시로 SPA를 same-origin 임베드 / **(B안 정합)** `frontend/app/office-tools/{report,chart,diagram}/page.tsx`로 이관(ECharts/Mermaid 클라이언트 컴포넌트, `/api/frontend/office-tools` 프록시 사용) | 화면에서 산출물 생성 |
| T6 | 대시보드 카드 등록 | 새 alembic 마이그레이션 `service_modules` bulk_insert(예: `office-report`/`office-chart`/`office-diagram` 또는 묶음 `office-tools`), `FALLBACK_MODULES` 추가, 섹션='개발중'·status='development'·visibility(초기 'admin') | 카드 노출/정렬 |
| T7 | 폐쇄망 의존성 | `requirements.txt`에 pandas/matplotlib/openpyxl/bleach/Markdown 추가 → wheelhouse 재생성. **CairoSVG 포함 시 Cairo/Pango DLL + CJK 폰트(Noto/Nanum) 설치 절차**를 `setup_offline.bat`/문서에 추가. 미포함 시 서버 PNG 비활성 | 오프라인 설치 재현 |
| T8 | 테스트·문서 | MVP의 `tests/test_svc0*`를 AeroOne pytest로 편입 + 홈페이지 카드 회귀(vitest). 문서: `docs/runbook/office-tools.md` + `docs/INDEX.md` 색인 | backend pytest / frontend vitest 동시 green |
| T9 | 검증 게이트 | backend `pytest tests -q`, frontend `npm test --run`, `npm run build`, 오프라인 `start_offline.bat` 실측 | merge 전 카운트 기록 |

---

## 5. SaaS Kit — 목적·구조·적용성

### 5.1 왜 이 MVP인가 (목적)
폐쇄망에 도입되는 오픈소스 도구들이 제각각 IP/포트/로그인을 가져 "무엇이 있고 지금 정상인지"를 알기 어렵다. Docker 금지 + 워크스테이션이 서버 역할 + 비전문 운영자 + AGPL 경계 관리라는 제약에서, **AeroOne 포털은 "통합 계층"으로 서비스 레지스트리·상태·대시보드만 담당하고, 실제 업무 도구(Leantime)는 독립 프로세스·독립 DB·독립 라이선스로 배포**한다는 원칙(Portal-first/Offline-first/No-Docker/License boundary).

### 5.2 세 구성요소

| 구성 | 정체 | AeroOne 관점 |
|---|---|---|
| (A) 오프라인 스위트 | `.bat`+PowerShell로 두 페이로드를 반입·설치·기동·백업 | AeroOne이 **이미 `setup_offline.bat`/`start_offline.bat` 보유** → 중복. 흡수하지 말 것 |
| (B) aeroone-tool 앱 | stdlib http.server + SQLite + vanilla HTML **서비스 포털 + 헬스모니터 + 로컬 뉴스레터 뷰어** | **대시보드/뉴스레터가 AeroOne에 이미 존재** → 재구현 금지. **헬스체크 개념만** 흡수 |
| (C) EXPERIMENTAL_PLANE | Plane(멀티서비스 AGPL) **소스 캐시만**, 설치 경로 없음 | 지금 배포 대상 아님. 보류 |

### 5.3 적용성 판정: **낮음 (코드 흡수 부적합) → 개념·자산만 취함**
- stdlib http.server/SQLite/vanilla HTML은 FastAPI/Postgres/Next.js로 **재작성 수준**이라 코드 이식 이득이 적다.
- 포털·뉴스레터는 AeroOne이 더 성숙하게 이미 구현 → 중복.
- **취할 가치**: ① 서비스 **헬스체크(online/degraded/offline)** 도메인 모델과 `services` 스키마(health_type=http/tcp/openai, api_key_env, last_status/latency), ② Leantime을 **외부 링크 도구 카드**로 추가, ③ AGPL corresponding-source·오프라인 번들-락 절차.

---

## 6. SaaS Kit — AeroOne 배포 순서 (단계별, "재해석" 경로)

| 순서 | 단계 | 구체 작업 | 비고 |
|---|---|---|---|
| S0 | 스코프 결정 | 무엇을 원하는가: (a) **헬스체크만** 대시보드에 / (b) **Leantime 실제 배포**까지 / (c) 포털 자체 이식(**비권장**) | (a)+(b) 권장 |
| S1 | 헬스체크 스키마 | `service_modules`에 상태 컬럼(`health_type`, `health_url`, `last_status`, `last_latency_ms`, `last_checked_at`) 추가 alembic, SaaS Kit `services` 스키마를 참고 | Postgres로 |
| S2 | 헬스체크 서비스 | 백엔드 백그라운드 점검(http 2xx/tcp/openai-models)을 AeroOne `admin` 또는 신규 `service_health` 모듈로. 응답 4KB 제한·타임아웃·실패 격리 등 MVP 규칙 계승 | 관리자 게이트 |
| S3 | 카드 상태 표시 | 대시보드 `ServiceCard`에 상태 점(초/황/적) 표시, 15초 scoped refresh(계획 Task 23 방식) | UI |
| S4 | Leantime 링크 카드 | `service_modules`에 `leantime`(is_external=true, href=`http://<host>:8081`) 카드 추가 | 링크만 |
| S5 | (선택) Leantime 배포 | IIS+PHP+MariaDB 네이티브 설치는 **AeroOne 오프라인 체계와 별도 트랙**으로 유지하되, 포트(8081/3307)·백업·ACL·방화벽을 AeroOne 설치 문서에 합류 | 무거움, 운영자 승인 |
| S6 | 라이선스 | Leantime/Plane는 AGPL → `/source-code` 소스오퍼·`docs/LICENSE_COMPLIANCE_CHECKLIST.md` 계승. AeroOne(MIT) 코드에 복사 금지, 링크/API 연동만 | 필수 |
| S7 | Plane | 보류. 필요 시 별도 연구 트랙 | — |

---

## 7. 기존 AeroOne 모듈과의 중복·충돌 지도

| AeroOne 기존 | 겹치는 MVP 요소 | 처리 방침 |
|---|---|---|
| `service_modules` 대시보드 | SaaS Kit 포털 전체 | AeroOne 것 유지, 포털 재구현 금지. 헬스체크만 이식 |
| `modules/render`(md→html sanitize) | Tool MVP SVC-01 일부 | 재사용 가능하나 보고서 포맷팅·이미지임베드·subprocess 렌더는 SVC-01이 상위 → SVC-01 채택, render는 경량 경로로 존치 |
| `modules/reports`(파일 기반 civil-aircraft) | Tool MVP "reports" 이름 | 이름만 겹침. 기능 다름 → 네임스페이스 분리(`office-tools`) |
| `modules/newsletter` | SaaS Kit newsletters 뷰어 | AeroOne 것이 성숙 → SaaS Kit 뉴스레터 버림 |
| `modules/ai`(Ollama gemma4:12b) | Tool MVP LLM(OpenAI호환 gpt-oss-120b) | **LLM 게이트웨이 단일화 결정 필요**(§8) |
| `setup_offline.bat`/`start_offline.bat` | SaaS Kit `10_INSTALL_*`/`20_START_*` | AeroOne 것 유지, SaaS Kit 설치기 흡수 금지(Leantime 트랙만 별도) |
| 포트 18437/29501 | MVP 8088/8765/8081/3307 | MVP 포트 폐기·흡수. Leantime만 8081/3307 별도 유지 |

---

## 8. 폐쇄망(Windows) 배포 위험 & 대응

| 위험 | 원인 | 대응 |
|---|---|---|
| 🔴 CairoSVG 네이티브 의존성 | 서버 PNG 변환에 Cairo/Pango DLL 필요 | MVP-온-AeroOne 초기엔 **서버 PNG 비활성(브라우저 ECharts/Mermaid 렌더만)** → CairoSVG 제거. 필요 시 GTK 런타임 설치 절차 문서화 |
| 🟠 Matplotlib/pandas wheel 플랫폼 종속 | wheelhouse는 빌드 PC OS/Python에 종속 | 오프라인 번들을 **운영과 동일 Windows/Python**에서 생성(기존 규칙과 동일) |
| 🟠 CJK 폰트 미포함 | PNG 한글 깨짐 | Noto Sans CJK/NanumGothic 설치를 `setup_offline` 체크리스트에 추가(브라우저 렌더만 쓰면 불필요) |
| 🟠 Tool MVP 인증 전무 | 네트워크 경계 전제 설계 | 라우터에 AeroOne 세션 의존성 강제(로그인 필수) |
| 🟠 동기 처리 + subprocess | SVC-01 요청당 subprocess(180s) | 초기엔 허용, 대용량 시 큐 전환(문서 Phase 2). 타임아웃·동시성 상한 설정 |
| 🟠 이중 설치 체계 | SaaS Kit 자체 설치기 | 흡수 금지. AeroOne `setup_offline`만 사용, Leantime만 별도 트랙 |
| 🟠 iframe 교차 오리진 | SPA(FastAPI:18437) vs Next(29501) 다른 오리진 + `X-Frame-Options:SAMEORIGIN` | same-origin 프록시로 서빙하거나 Next 페이지로 이관(권장) |

---

## 9. 지금 결정해야 할 사항 (권장안 포함)

| # | 결정 | 선택지 | 권장 |
|---|---|---|---|
| D1 | Tool MVP 범위 | 3서비스 전부 / 우선 1개 | **다이어그램 또는 차트 1개로 파일럿** 후 확장 |
| D2 | LLM 백엔드 | Ollama(gemma4)로 통일 / 사내 OpenAI호환(gpt-oss-120b) 게이트웨이 신설 | 사내 실 LLM이 무엇인지에 따름 → **사용자 확인 필요** |
| D3 | 차트/다이어그램 렌더 | 브라우저 렌더만 / 서버 PNG(CairoSVG)까지 | **브라우저 렌더만**(폐쇄망 마찰 최소) |
| D4 | 프런트 방식 | iframe 임베드(빠름) / Next.js 이관(정합) | **Next.js 이관**(로그인·테마·nav 일관) |
| D5 | SaaS Kit 취급 | 헬스체크만 / +Leantime 링크 / +Leantime 배포 / 포털 이식 | **헬스체크 + Leantime 링크 카드**, 배포는 추후 |
| D6 | 폴더/깃 전략 | `AeroOne Tool/` 원본 커밋 / gitignore 참조로만 유지 | 원본 zip·dist는 **비추적(gitignore) 참조**, 이식하는 소스만 정식 편입 |
| D7 | 카드 노출 | `visibility='admin'`(운영자만) / `'public'`(로그인 전원) | 개발 중 **admin → 안정화 후 public** |

---

## 부록. 핵심 파일 좌표

- Tool MVP: `tool-mvp-v0.1.0/backend/app/main.py`, `backend/app/api/routes/*`, `tools/svc0*/service.py`, `backend/app/core/{llm_client,job_store,security,settings}.py`, `frontend/src/{App.tsx,lib/api.ts}`, `requirements.txt`, `Dockerfile`
- SaaS Kit: `saas-kit-v2.0.0/aeroone-tool/mvp/aeroone/{web,database,services,security}.py`, `aeroone-tool/docs/{PRD,ARCHITECTURE,database_schema.sql,openapi.yaml}`, `aeroone-tool/mvp/config/services.seed.json`, `EXPERIMENTAL_PLANE/README.md`
- AeroOne 부착점: `frontend/app/page.tsx`(FALLBACK_MODULES), `backend/alembic/versions/20260703_0004_admin_rbac_operations.py`(service_modules seed 패턴), `backend/app/modules/admin/models.py`(ServiceModule), `backend/app/main.py`(라우터 등록), `frontend/app/api/frontend/*/route.ts`(프록시), `backend/app/core/config.py`(Ollama LLM 설정), `start_offline.bat`

---

## 10. 2026-07-12 완료 스냅샷 (역사 기록, 현재 계약 아님)

> 이 절은 당시 구현 상태와 검증 기록을 보존한다. 당시의 개별 Office 카드, 외부 Leantime 링크,
> `0010~0011`을 head로 보는 마이그레이션 상태, 권한·lifecycle 이전 설명 및 pass 수는 현재
> 운영 사실이 아니다. 이 절의 수치를 다시 실행하거나 현재 gate 결과로 인용하지 않는다.

### 10.1 당시 확정 사항의 보존

| 당시 결정 | 2026-07-12 기록 |
|---|---|
| Tool MVP 범위 | 보고서·차트·다이어그램 3종을 AeroOne에 흡수 |
| LLM 배선 | 관리자가 OpenAI 호환 연결을 등록하고 Office AI 보조가 소비 |
| 렌더 | 차트 ECharts·다이어그램 Mermaid의 브라우저 렌더, 서버 PNG 미도입 |
| 프런트 | Next.js 페이지와 same-origin 프록시 |
| Leantime | 별도 스택의 링크·기동 훅·런북 통합면 |

당시 기록의 `pytest`/Vitest/typecheck/build 통계는 **2026-07-12 시점의 관측값**일 뿐이며, 현재
회귀 결과·릴리즈 gate를 뜻하지 않는다.

### 10.2 2026-07-13 현재 참조 지도

| 영역 | 현재 진실 원천 |
|---|---|
| Office 접근·API·입력·lifecycle·테스트 계약 | [`docs/runbook/office-tools.md`](../docs/runbook/office-tools.md), `backend/app/modules/office_tools/`, `backend/tests/unit/test_office_tools_*.py`, `frontend/tests/app/office-tools-*.test.tsx` |
| Office 대시보드 진입점 | 단일 `office-tools` 카드 → `/office-tools`; 허브의 보고서·차트·다이어그램 탭. 코드 시드는 `backend/app/modules/admin/api.py`, fallback은 `frontend/app/page.tsx` ID `11` |
| Leantime 대시보드 진입점 | 내부 `/leantime` 안내 페이지; fallback ID `12`. 상세 동거 계약은 [`docs/runbook/leantime-codeploy.md`](../docs/runbook/leantime-codeploy.md) |
| 카드 마이그레이션 최종 상태 | 초기 `20260711_0010/0011` 뒤 `20260712_0012`(단일 Office 허브), `0013`(Office Studio 제목), `0014`(Leantime 내부 안내). 현재 Alembic head `20260712_0014` |
| AI 미구성·실패 동작 | 활성 연결을 사용하되 모든 Office 도구는 `rule-based` 폴백과 warning을 반환 |
| 구현 시점 평가 | [`docs/runbook/office-leantime-architecture-review-2026-07-13.md`](../docs/runbook/office-leantime-architecture-review-2026-07-13.md) — 해결된 Office 항목과 별도 Leantime readiness/launcher 조건을 구분 |

실제 운영 배포 전 IIS/PHP/MariaDB, 대응 소스오퍼, 백업·복구, LAN 방화벽과 Leantime HTTP readiness는
`leantime-codeploy.md`의 운영자 검증 항목으로 남는다. 이는 Office Studio의 구현 완료 여부와 별개의
Leantime co-deploy 준비도 조건이다.