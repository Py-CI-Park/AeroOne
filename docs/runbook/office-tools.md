# 오피스 도구(보고서·차트·다이어그램) 운영 런북

> 폐쇄망에서 반복하는 보고서 양식화·데이터 시각화·업무 도식화를 **AeroOne 로그인·테마·nav 안**
> 으로 흡수한 3종 도구다. 별도 포트·별도 배치·별도 로그인을 만들지 않고, 기존 백엔드
> (uvicorn 18437)와 프런트(Next 29501) **두 프로세스 안에서만** 동작한다.
>
> 원본은 `AeroOne Tool/tool-mvp-v0.1.0/`(FastAPI + Vite MVP, 포트 8088)이며, 이 빌드에서
> 라우터를 `backend/app/modules/office_tools/` 로 흡수하고 화면을 Next.js 페이지로 이관했다.
> 통합 판단 근거는 [`../../AeroOne Tool/INTEGRATION_ANALYSIS.md`](../../AeroOne%20Tool/INTEGRATION_ANALYSIS.md) 참조.

---

## 0. 결론 먼저

- 3종 도구는 대시보드 **개발중(Development) 섹션의 관리자 전용 카드**(`visibility='admin'`)로
  노출된다: 보고서 스튜디오(`/office-tools/report`), 차트 스튜디오(`/office-tools/chart`),
  다이어그램 스튜디오(`/office-tools/diagram`).
- 백엔드는 `/api/v1/office-tools/*` 한 prefix 로 등록되고 **라우터 레벨에서 세션 로그인을
  강제**한다(미로그인 401). 브라우저는 same-origin 프록시
  `/api/frontend/office-tools/[...segments]` 만 호출한다.
- **렌더링 결정**: 차트는 브라우저 ECharts, 다이어그램은 브라우저 Mermaid 로 렌더한다. 서버
  PNG(CairoSVG/Matplotlib)는 폐쇄망 마찰이라 이번 빌드에서 **비활성**이다. 서버는 소스/스펙만
  만든다(차트 집계는 pandas 서버 처리).
- **AI 는 선택적**이다. 활성 LLM 연결(관리자 등록, [`llm-connections.md`](llm-connections.md))이
  있으면 AI 보조를 쓰고, 없거나 실패하면 **규칙 기반 폴백**으로 내려가 도구는 계속 동작한다.

---

## 1. 통합 구조 (5자리)

새 도구가 대시보드에 등장하는 AeroOne 정형 패턴 5자리를 모두 채웠다.

| # | 자리 | 파일 |
|---|---|---|
| 1 | 대시보드 카드(DB 시드) | `backend/alembic/versions/20260711_0010_office_tools_service_modules.py` (office 3종, `WHERE NOT EXISTS` 멱등), `20260711_0011_leantime_service_module.py` |
| 2 | 대시보드 카드(코드 시드) | `backend/app/modules/admin/api.py` `DEFAULT_SERVICE_MODULES` |
| 3 | 대시보드 카드(Fallback) | `frontend/app/page.tsx` `FALLBACK_MODULES` (id 11~14) |
| 4 | 프런트 페이지 | `frontend/app/office-tools/{report,chart,diagram}/page.tsx` + `frontend/components/office-tools/*` (`AppShell` 사용) |
| 5 | 백엔드 모듈 + 라우터 등록 | `backend/app/modules/office_tools/` + `backend/app/main.py` (`include_router(prefix='/api/v1/office-tools')`) |
| — | same-origin 프록시 | `frontend/app/api/frontend/office-tools/[...segments]/route.ts` (쿠키 전달) |

진실 원천 **3자리(마이그레이션 · `DEFAULT_SERVICE_MODULES` · `FALLBACK_MODULES`)의 카드 값은
반드시 일치**한다. 회귀 계약은 `frontend/tests/app/home-page.test.tsx` 가 지킨다.

### 1.1 백엔드 모듈 배치

```
backend/app/modules/office_tools/
├─ api/
│  ├─ router.py        상위 라우터. dependencies=[Depends(get_current_user)] 로 전 하위 로그인 강제
│  ├─ system.py        GET /health, GET /capabilities
│  ├─ jobs.py          GET /jobs/{job_id}, 산출물 다운로드/번들 — 소유자(owner_id) 스코프
│  ├─ reports.py       POST /reports/generate
│  ├─ charts.py        POST /charts/inspect, POST /charts/generate
│  └─ diagrams.py      POST /diagrams/generate
├─ core/
│  ├─ job_store.py     파일 기반 JobStore(사용자 스코프 산출물 저장)
│  └─ llm_bridge.py    활성 LLM 연결 해석(resolve_active_client / describe_capabilities)
├─ services/
│  ├─ report/          sanitize HTML 보고서(renderer/enhancer/assets)
│  ├─ chart/           pandas 집계 + ECharts option 빌더(data_loader/processor/spec_builder)
│  └─ diagram_service.py  Mermaid 소스 생성
├─ schemas.py          요청/응답 DTO + 상한 상수
└─ security.py         validate_mermaid / sanitize_svg / validate_offline_html
```

---

## 2. 서비스별 구조

| 서비스 | 입력 | 산출물 | 렌더 | 서버측 검증 상한 |
|---|---|---|---|---|
| 보고서 스튜디오(svc01) | `.md`/`.markdown`/`.txt` + 이미지/ZIP + 메타 + `ai_mode` | 인라인 CSS 자립형 sanitize HTML + Markdown 원본 + `manifest.json` | 서버가 오프라인 HTML 생성(외부 CDN 0) | 업로드 20MB(`MAX_REPORT_UPLOAD_BYTES`), Markdown 200,000자(`MAX_REPORT_MARKDOWN_CHARS`), 확장자 화이트리스트 |
| 차트 스튜디오(svc02) | `.csv`/`.xlsx`/`.json` + 목적 문장 + 옵션 | ChartSpec + **ECharts option(JSON)** + 집계 CSV + `manifest.json` | **브라우저 ECharts** (서버 PNG 없음) | 업로드 20MB(`MAX_CHART_UPLOAD_BYTES`), 100,000행(`MAX_CHART_DATA_ROWS`) |
| 다이어그램 스튜디오(svc03) | 자연어 설명 + 유형(flowchart/sequence/state/gantt) | **Mermaid 소스(.mmd)** + `manifest.json` | **브라우저 Mermaid(strict)** (서버 PNG 없음) | `validate_mermaid` 로 `click`/`javascript:`/`<script>`/`<iframe>`/`%%{init` 차단, 유형별 허용 접두 강제 |

세 도구 공통 규칙:

- **AI 는 명세만 제안, 앱이 재검증, 고정 렌더러가 최종 산출**. 모델이 꺼져 있어도 규칙 기반
  폴백으로 동작한다(보고서=원문 유지, 차트=규칙 기반 스펙, 다이어그램=규칙 기반 소스). 폴백
  사용 시 응답 `warnings` 에 사유를 붙인다.
- 잘못된 확장자·크기 초과·문자수/행수 초과·금지 Mermaid 지시어는 모두 **422** 로 거부한다.
- 산출물은 `OfficeJobStore` 에 `owner_id` 로 저장하고, 조회/다운로드 시 세션 사용자와
  `owner_id` 가 다르면 **403**, 없는 job/경로 탈출은 **404** 다.

---

## 3. API 요약

모든 경로는 `/api/v1/office-tools` prefix 아래이며 **로그인 필수**(미로그인 401). 브라우저는
직접 호출하지 않고 same-origin 프록시 `/api/frontend/office-tools/...` 를 통한다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 상태(`{status, service}`) |
| GET | `/capabilities` | 서비스 플래그 + 활성 LLM 여부/모델명 + 상한. **base_url/api_key 미노출** |
| POST | `/reports/generate` | multipart(Markdown + 이미지/ZIP + 메타 + `ai_mode`) → sanitize HTML 보고서 |
| POST | `/charts/inspect` | 데이터 프로필(행/열/샘플)만. job 미생성 |
| POST | `/charts/generate` | multipart(데이터 + `prompt` + `ai_assist` + `chart_type`/`manual_spec_json`) → ECharts option |
| POST | `/diagrams/generate` | JSON(설명 + 유형) → Mermaid 소스 |
| GET | `/jobs/{job_id}` | 산출물 메타/다운로드/번들. 소유자 스코프(403/404) |

`ai_mode`(보고서) = `none`/`polish`/`executive`. `ai_assist`(차트/다이어그램) = bool.
`capabilities.llm.fallback` 은 항상 `rule-based`.

---

## 4. LLM 연결 (AI 보조 배선)

- 각 도구의 AI 보조는 `core/llm_bridge.resolve_active_client(db, settings)` 로 **활성 LLM
  연결**을 얻어 `OpenAiCompatibleClient` 로 호출한다. 활성 연결이 없으면 `None` → 규칙 기반 폴백.
- 활성 연결은 관리자가 **LLM 연결 레지스트리**에 등록한다. 등록·검증·기본 지정 절차는
  [`llm-connections.md`](llm-connections.md) 를 따른다.
- Ollama(`http://127.0.0.1:11434/v1`)와 외부 gpt-oss 계열 모두 이 OpenAI 호환 경로로 커버한다.
- 브리지는 `base_url`/`api_key` 를 절대 프런트로 노출하지 않는다. `capabilities` 는 활성 여부와
  모델명(비밀 아님)만 반환한다.

---

## 5. 오프라인 의존성

`backend/requirements.txt` 에 추가된 것(차트 서버 집계용):

| 패키지 | 버전 | 용도 | 미설치 시 |
|---|---|---|---|
| `pandas` | 2.2.3 | 차트 데이터 집계 | 차트 도구 동작 불가 → wheelhouse 확보 필수 |
| `numpy` | 2.2.6 | pandas 의존 | 상동 |
| `openpyxl` | 3.1.5 | `.xlsx`/`.xlsm` 입력(선택) | xlsx 업로드만 422 로 안내, CSV/JSON 은 정상 |

- **폐쇄망 wheel 확보**: pandas/numpy wheel 은 빌드 PC OS/Python 에 종속된다. 오프라인 번들을
  **운영과 동일한 Windows/Python** 에서 생성해야 한다(기존 wheelhouse 규칙과 동일).
- **CairoSVG/Matplotlib/CJK 폰트 불필요**: 이번 빌드는 서버 PNG 를 만들지 않으므로 Cairo/Pango
  DLL·Noto/Nanum 폰트 설치가 필요 없다. 차트/다이어그램 이미지는 브라우저(ECharts/Mermaid)가
  렌더한다. 추후 서버 PNG 를 켤 경우에만 폰트/네이티브 런타임 절차가 추가된다.
- **프런트 렌더 라이브러리**: ECharts / Mermaid 는 `frontend/package.json` 에 추가되어 Next 빌드
  산출물에 포함되므로 별도 CDN 반입이 필요 없다(외부 CDN 0 원칙 유지).

---

## 6. 사용법 (관리자)

1. AeroOne 에 관리자 계정으로 로그인한다(도구 카드는 `visibility='admin'`).
2. (선택) AI 보조를 쓰려면 먼저 관리자 콘솔에서 LLM 연결을 하나 등록·기본 지정한다
   ([`llm-connections.md`](llm-connections.md)). 등록이 없으면 도구는 규칙 기반으로 동작한다.
3. 대시보드 개발중 섹션에서 원하는 스튜디오 카드를 연다.
   - **보고서**: Markdown 파일(+이미지/ZIP)과 제목/부제/버전/태그를 넣고 `ai_mode` 를 고른 뒤
     생성 → 미리보기·다운로드(단일 오프라인 HTML).
   - **차트**: 데이터 파일 업로드 → `inspect` 로 열 프로필 확인 → 목적 문장/차트 유형을 정해
     생성 → 브라우저 ECharts 미리보기·집계 CSV 다운로드.
   - **다이어그램**: 유형(flow/seq/state/gantt)과 설명을 넣고 생성 → 브라우저 Mermaid 미리보기·
     `.mmd` 다운로드.
4. 산출물은 본인 소유 job 으로만 조회된다(타 사용자 job 은 403).

> 안정화 후 일반 사용자에게 열려면 카드 `visibility` 를 `admin`→`public` 으로 관리자 콘솔에서
> 전환한다(코드 기본값은 개발 중 `admin` 유지).

---

## 7. 회귀 테스트

| 테스트 파일 | 건수 | 다루는 영역 |
|---|---|---|
| `backend/tests/unit/test_office_tools_auth.py` | 6 | 라우터 레벨 로그인 강제(미로그인 401), capabilities 비밀 미노출 |
| `backend/tests/unit/test_office_tools_report.py` | 12 | 보고서 생성/확장자·크기·문자수 422/AI 폴백/sanitize |
| `backend/tests/unit/test_office_tools_charts.py` | 19 | inspect/generate/pandas 집계/행수·확장자 422/수동 스펙/ECharts option |
| `backend/tests/unit/test_office_tools_diagrams.py` | 13 | Mermaid 생성/유형별 접두/금지 지시어 422/AI 폴백 |
| `backend/tests/unit/test_office_tools_jobs.py` | 3 | job 조회 소유권 403 / 없는 job 404 |
| `backend/tests/unit/test_service_modules_office_seed.py` | 2 | office 3종 카드 멱등 시드 |
| `backend/tests/unit/test_service_modules_leantime_seed.py` | 2 | Leantime 외부 링크 카드 멱등 시드 |
| `frontend/tests/app/office-tools-*.test.tsx` | 10 | report/chart/diagram 페이지 + 공통 페이지 렌더/폼 |
| `frontend/tests/lib/office-tools-api.test.ts` | 6 | 프런트 API 클라이언트 |
| `frontend/tests/app/home-page.test.tsx` | — | fallback 대시보드에 office/Leantime 카드 포함 계약 |

최종 게이트: backend `pytest tests` = 356 passed / 2 failed(사전 실패 `run_all.bat` 관련 2건,
새 회귀 0). frontend Vitest = 336 passed(72 files) / 0 failed. `tsc --noEmit` 통과.
`next build` 성공(static 7/7).

---

## 8. 운영자 검증 필요 (실배포 전)

- [ ] `backend/.venv` 에 pandas/numpy/openpyxl wheel 설치(운영과 동일 Windows/Python 로 생성한
      wheelhouse).
- [ ] `alembic upgrade head` 로 `20260711_0009~0011` 반영(llm_connections 테이블 + 카드 3종 +
      Leantime 카드).
- [ ] AI 보조를 쓸 경우 LLM 연결 1건 등록·검증·기본 지정([`llm-connections.md`](llm-connections.md)).
- [ ] 안정화 후 카드 `visibility` 를 `public` 으로 전환할지 결정.

---

## 관련 문서

- LLM 연결 설정: [`llm-connections.md`](llm-connections.md)
- Leantime 동거: [`leantime-codeploy.md`](leantime-codeploy.md)
- 통합 분석/결정: [`../../AeroOne Tool/INTEGRATION_ANALYSIS.md`](../../AeroOne%20Tool/INTEGRATION_ANALYSIS.md)
- 폐쇄망 종합 가이드: [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
