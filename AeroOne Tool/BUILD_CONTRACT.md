# AeroOne 통합 빌드 계약서 (BUILD_CONTRACT)

> 이 문서는 후속 구현 에이전트들이 **그대로 따르는 단일 진실**이다. 파일 경로/컬럼값/권한키/라우터
> prefix 는 아래 표기가 최종이며, 임의 변경 금지. 모호한 부분이 생기면 이 문서를 갱신한 뒤 진행한다.
>
> - 기준 브랜치: `feature/dashboard-enhancements` (worktree `.worktrees/dashboard-enhancements`)
> - Alembic head (작업 시작 시점): `20260707_0008`
> - 백엔드 파이썬: `backend/.venv/Scripts/python.exe` (backend cwd 기준)
> - 포트: 백엔드 18437 / 프런트 29501 고정. 새 포트/새 배치 **0**. Leantime 만 외부 링크(예 8081).
> - 언어: 코드 주석/문서/커밋 한국어, 식별자 영어. 불변성(spread), 함수 <50줄, 파일 <800줄, 중첩 <4.
> - 커밋/add/push 금지 — 작업트리에만 변경을 남긴다.

---

## 0. 이번 빌드의 3개 산출물

| # | 산출물 | 한 줄 정의 |
|---|--------|-----------|
| A | **LLM 연결 레지스트리** | 관리자가 OpenAI 호환 엔드포인트(base_url + api_key)를 DB 에 등록·암호화 저장하고, `/v1/models` 로 모델 목록을 로드해 `/v1/chat/completions` 로 호출. 키는 서버 저장·마스킹. |
| B | **office-tools 모듈 (보고서/차트/다이어그램)** | MVP 3종을 AeroOne 백엔드 라우터 + Next.js 페이지로 흡수. 브라우저 렌더 우선(ECharts/Mermaid), 서버 PNG 생략. |
| C | **Leantime 동거 통합면** | 흡수 불가(PHP+MariaDB+IIS, AGPL). service_modules 외부 링크 카드 + run_all.bat 기동 훅 + 오프라인 런북 + AGPL 소스오퍼. 실제 설치는 운영자 검증. |

---

## 1. 산출물 A — LLM 연결 레지스트리

### 1.1 DB 테이블 `llm_connections`

ORM 은 기존 ai 모듈 import 체인(`app.modules.ai import models`)에 이미 걸리도록 **`backend/app/modules/ai/models.py` 하단에 클래스 추가**한다(신규 파일 아님 — create_all 등록 자동).

```
테이블: llm_connections
- id                int      PK
- name              String(120)  NOT NULL                # 표시명 (예: "사내 gpt-oss", "로컬 Ollama")
- base_url          String(500)  NOT NULL                # 예: http://127.0.0.1:11434/v1, https://gpt-oss.intra/v1
- api_key_encrypted Text         NOT NULL server_default '' # 대칭 암호화된 키(아래 1.3). 없으면 빈 문자열(Ollama 등 무키).
- default_model     String(160)  NULLABLE                # /v1/models 중 선택. NULL 이면 호출 시 필수 지정.
- is_enabled        Boolean      NOT NULL server_default true()
- is_default        Boolean      NOT NULL server_default false()   # 활성 연결 1개. 아래 1.4 유일성 규칙.
- verify_tls        Boolean      NOT NULL server_default true()
- created_at        DateTime(tz) NOT NULL server_default func.now()
- updated_at        DateTime(tz) NOT NULL server_default func.now() onupdate func.now()
```

- 시각 컬럼은 기존 선례대로 **DB-side `func.now()`** 로만 채운다(SQLite naive 함정 회피 — ai/models.py docstring 참조).
- `api_key_encrypted` 는 절대 평문 저장 금지. 응답에도 절대 평문 반환 금지(마스킹만).

### 1.2 Alembic 마이그레이션 (0009)

- 파일: `backend/alembic/versions/20260711_0009_llm_connections.py`
- `revision = "20260711_0009"`, `down_revision = "20260707_0008"`
- `upgrade()`: `op.create_table('llm_connections', ...)` 위 컬럼 그대로. `downgrade()`: `op.drop_table('llm_connections')`.
- 시드 없음(연결은 운영자가 UI 로 등록). 단, 로컬 Ollama 를 예시로 등록하는 방법은 런북에만 문서화.

### 1.3 암호화 방식 (stdlib only — 새 의존성 0)

`cryptography`/`httpx` 등 신규 패키지를 추가하지 않는다(폐쇄망 wheel 마찰 회피). `secrets` 대칭키를 아래
**HMAC 스트림 암호 + Encrypt-then-MAC** 로 구현한다. 파일: `backend/app/modules/ai/llm_crypto.py`.

- 키 원천: `settings.jwt_secret_key` (production/closed_network 은 이미 ≥32자 강제 — config.py `validate_runtime_security`).
- 파생: `enc_key = sha256(b'aeroone-llm-enc-v1' + secret.encode())`, `mac_key = sha256(b'aeroone-llm-mac-v1' + secret.encode())`.
- 암호화 `encrypt(plaintext: str) -> str`:
  1. `nonce = os.urandom(16)`
  2. keystream = `HMAC-SHA256(enc_key, nonce + counter_be4)` 블록들을 이어붙여 XOR (counter 0,1,2...)
  3. `ciphertext = plaintext_utf8 XOR keystream[:len]`
  4. `tag = hmac_sha256(mac_key, nonce + ciphertext)`
  5. return `"v1:" + base64.urlsafe_b64encode(nonce + tag + ciphertext).decode()`
- 복호화 `decrypt(token: str) -> str`: prefix/`b64` 검증 → tag 를 `hmac.compare_digest` 로 상수시간 검증(실패 시 `ValueError`) → XOR 복원.
- 마스킹 `mask(plaintext: str) -> str`: `sk-...abcd` 형태(앞 접두 + 뒤 4자만, 8자 미만이면 전체 `****`). 응답 DTO 에는 마스킹 값만.

### 1.4 서비스 계층

파일: `backend/app/modules/ai/llm_connection_service.py` (CRUD + 활성 연결 해석), `backend/app/modules/ai/openai_client.py` (OpenAI 호환 호출 — MVP `llm_client.py` 로직을 **stdlib `urllib` 로 포팅**, 기존 `OllamaClient` 와 동일 transport).

- `LlmConnectionService(db, settings)`:
  - `list() -> list[LlmConnection]`
  - `create(payload) -> LlmConnection` (api_key 를 `encrypt` 후 저장)
  - `update(id, payload)` (api_key 필드가 오면 재암호화, 안 오면 유지 — `exclude_unset`)
  - `delete(id)`
  - `set_default(id)`: 트랜잭션 내 다른 모든 행 `is_default=False` 후 대상만 True (유일성 보장).
  - `get_active() -> LlmConnection | None`: `is_enabled AND is_default` 우선, 없으면 `is_enabled` 중 `id` 최소. 없으면 None.
  - `decrypt_key(conn) -> str`
- `OpenAiCompatibleClient(base_url, api_key, model, verify_tls, settings)`:
  - `list_models() -> list[str]`: `GET {base_url}/models`, `Authorization: Bearer {key}`(key 있을 때만). 응답 `data[].id` 파싱. `_endpoint` 규칙은 MVP `llm_client._endpoint` 처럼 base 가 `/v1` 로 끝나고 path 가 `/v1/` 로 시작하면 중복 제거.
  - `chat(messages, temperature=0.2, max_tokens=1200) -> str`: `POST {base_url}/chat/completions`. `choices[0].message.content` 만 반환(reasoning/CoT 필드 노출 금지). 빈/비문자 응답은 예외.
  - transport: `urllib.request` + `ssl` context(`verify_tls=False` 면 `ssl._create_unverified_context()`). 타임아웃은 settings 의 ollama read/connect 타임아웃 재사용.
  - 예외 타입: `LlmConnectionError`(연결 다운), `LlmConfigError`(미설정).
- **기존 ai 모듈과의 관계**: `office_tools` AI 보조와 신규 연결 기반 경로는 `get_active()` 연결을 우선 사용. 활성 연결이 없으면 기존 `OllamaClient`(config.py `ollama_*` env) 로 폴백. 로컬 Ollama 는 `base_url=http://127.0.0.1:11434/v1`, 무키로 레지스트리에 등록해 동일 경로로 커버 가능. **기존 `/api/v1/ai/chat`(AeroAI) 의 Ollama 경로는 이번 빌드에서 변경하지 않는다**(회귀 위험 최소화 — 리스크 §7 참조).

### 1.5 백엔드 관리자 API

파일: `backend/app/modules/ai/api/admin.py` (신규). `main.py` 에서 **`/api/v1/admin` prefix 로 include** (기존 admin 프록시 `/api/frontend/admin/[...segments]` 재사용을 위해).

| 메서드 | 경로 | 권한 | CSRF | 설명 |
|--------|------|------|------|------|
| GET | `/llm-connections` | `admin.ai.read` | - | 목록. api_key 는 마스킹만. |
| POST | `/llm-connections` | `admin.ai.manage` | `require_csrf` | 생성. 감사기록 `llm_connection.create`. |
| PATCH | `/llm-connections/{id}` | `admin.ai.manage` | `require_csrf` | 수정. 감사 `llm_connection.update`. |
| DELETE | `/llm-connections/{id}` | `admin.ai.manage` | `require_csrf` | 삭제. 감사 `llm_connection.delete`. |
| POST | `/llm-connections/{id}/default` | `admin.ai.manage` | `require_csrf` | 기본 연결 지정. 감사 `llm_connection.set_default`. |
| POST | `/llm-connections/{id}/verify` | `admin.ai.manage` | `require_csrf` | 저장된 키로 `/v1/models` 호출 → 성공/실패 + 모델목록 반환. |
| GET | `/llm-connections/{id}/models` | `admin.ai.read` | - | 캐시 없이 실시간 모델목록(연결 다운 시 degraded). |

- 데코레이션 패턴은 기존 admin/api.py 와 동일: `dependencies=[Depends(require_permission('admin.ai.manage')), Depends(require_csrf)]`.
- 감사기록은 `record_admin_audit(db, actor=..., action=..., target_type='llm_connection', target_id=str(id), request=..., before/after=...)`. **after 스냅샷에 평문 키 절대 포함 금지**(마스킹 값만).
- 입력 검증: pydantic 스키마 `backend/app/modules/ai/schemas.py` 에 추가.
  - `LlmConnectionCreate`: `name: str(1..120)`, `base_url: str` (http/https 만 허용하는 validator), `api_key: str = ''`(옵션), `default_model: str | None`, `is_enabled: bool = True`, `is_default: bool = False`, `verify_tls: bool = True`.
  - `LlmConnectionUpdate`: 전 필드 Optional(`exclude_unset` 로 부분수정, api_key 미포함 시 키 유지).
  - `LlmConnectionResponse`: `id,name,base_url,default_model,is_enabled,is_default,verify_tls,api_key_masked,created_at,updated_at` — **평문 키 필드 없음**.
  - `LlmVerifyResponse`: `ok: bool, models: list[str], detail: str | None`.

### 1.6 프런트 관리자 UI

- **위치**: `frontend/components/admin/sections/admin-system-section.tsx` 의 시스템 탭 안에 "AI 연결" 카드 블록을 **추가**(기존 DB/자산 상태, AI 운영 상태, 비밀번호 카드와 나란히).
- 상태/액션은 `admin-console-tabs.tsx` 의 `PanelState`/`AdminConsoleContextValue`/`refresh` 에 `llmConnections` 키와 CRUD 액션을 추가(기존 `runBusy` 패턴 그대로, `getCsrfCookie()` 전달).
- 프록시: 기존 `frontend/app/api/frontend/admin/[...segments]/route.ts` 가 이미 `/api/v1/admin/*` 를 중계 → **신규 프록시 파일 불필요**.
- API 클라이언트: `frontend/lib/api.ts` 에 `fetchLlmConnections / createLlmConnection / updateLlmConnection / deleteLlmConnection / setDefaultLlmConnection / verifyLlmConnection / fetchLlmConnectionModels` 추가.
- 타입: `frontend/lib/types.ts` 에 `LlmConnection`, `LlmVerifyResponse` 추가.
- UI 규칙: 키 입력은 `type="password"`. 목록에는 마스킹 값만 표시. "검증" 버튼 → verify 호출 → 모델 드롭다운 채움. "기본 지정" 토글. console.log 금지, 에러는 toast.

---

## 2. 산출물 B — office-tools 모듈

### 2.1 백엔드 모듈 구조

신규 패키지 `backend/app/modules/office_tools/` (모두 신규 생성):

```
backend/app/modules/office_tools/
  __init__.py
  schemas.py                     # pydantic 요청/응답 (zod 대응은 프런트)
  job_store.py                   # MVP core/job_store.py 포팅 (파일 JobStore). DB 모델 불요.
  security.py                    # MVP core/security.py 에서 sanitize_markdown/validate_mermaid/sanitize_svg 포팅.
                                 #  단, cairosvg/bleach 의존 부분 제거(아래 2.5). 보고서 sanitize 는
                                 #  기존 newsletter html_render_service.sanitize_html_fragment 재사용.
  services/
    __init__.py
    report_service.py            # svc01 포팅: markdown -> sanitize HTML (서버). 벤더 build_report.py subprocess 미사용.
    chart_service.py             # svc02 포팅: pandas 집계 -> ECharts option JSON 반환(서버 SVG/PNG 렌더 제거).
    diagram_service.py           # svc03 포팅: description -> Mermaid 소스(브라우저 렌더). cairosvg export 제거.
    data_loader.py               # svc02 data_loader.py 포팅(pandas/numpy CSV/XLSX/JSON 로드 + profile).
  api/
    __init__.py
    reports.py                   # router prefix 조각 (아래 2.2)
    charts.py
    diagrams.py
    jobs.py                      # 산출물 다운로드/번들 (path-guard)
```

- **models 불요**: 작업 산출물은 파일 JobStore(`backend/data/office_jobs/`)에 저장. DB 테이블 추가 없음.
- JobStore 루트: `settings` 에 신규 프로퍼티 추가 대신, `office_tools/job_store.py` 가 `settings.project_root / 'backend' / 'data' / 'office_jobs'` 를 사용(경로는 `config.py` 의 `project_root` 프로퍼티 재사용). 디렉터리는 JobStore 생성자에서 `mkdir(parents=True, exist_ok=True)`.
- job_id 형식/‑path guard/‑artifact 등록은 MVP `job_store.py` 계약을 그대로 유지(정규식 `[0-9a-f]{32}`, `safe_name`, atomic write).

### 2.2 라우터 등록 (main.py)

`backend/app/main.py` `create_app()` 에 기존 `include_router` 패턴으로 추가:

```python
from app.modules.office_tools.api.reports import router as office_reports_router
from app.modules.office_tools.api.charts import router as office_charts_router
from app.modules.office_tools.api.diagrams import router as office_diagrams_router
from app.modules.office_tools.api.jobs import router as office_jobs_router
from app.modules.ai.api.admin import router as ai_admin_router
...
app.include_router(ai_admin_router, prefix='/api/v1/admin')            # 산출물 A
app.include_router(office_reports_router, prefix='/api/v1/office-tools/reports')
app.include_router(office_charts_router,  prefix='/api/v1/office-tools/charts')
app.include_router(office_diagrams_router, prefix='/api/v1/office-tools/diagrams')
app.include_router(office_jobs_router,     prefix='/api/v1/office-tools/jobs')
```

### 2.3 인증 의존성 (로그인 필수)

개발 중 도구 API 는 **로그인 필수**. 각 office_tools 라우터에 라우터-레벨 의존성:

```python
from app.modules.auth.dependencies import get_current_user
router = APIRouter(dependencies=[Depends(get_current_user)])
```

- 미로그인 시 401. 신규 권한키는 만들지 않는다(카드 visibility='admin' + 로그인만으로 게이트). 추후 public 전환 시 완화.

### 2.4 엔드포인트 계약

| 라우터 | 메서드 | 경로(모듈 prefix 이후) | 입력 | 출력 |
|--------|--------|----------------------|------|------|
| reports | POST | `/generate` | `multipart`: `markdown_file`(.md/.markdown/.txt), `title`,`subtitle`,`document_version`,`tags`,`ai_mode`(none/polish/executive) | job record(JSON) + `preview_url` |
| charts | POST | `/inspect` | `multipart`: `data_file`(.csv/.xlsx/.xlsm/.json) | dataframe profile JSON |
| charts | POST | `/generate` | `multipart`: `data_file`,`prompt`,`ai_assist`(bool),`chart_type`,`manual_spec_json` | job record + `chart_spec` + `echarts_option` |
| diagrams | POST | `/generate` | `json`: `{description, diagram_type, title, ai_assist}` | job record + `mermaid` |
| jobs | GET | `/{job_id}` | - | job.json |
| jobs | GET | `/{job_id}/artifacts/{filename}` | - | 파일(FileResponse, path-guard) |
| jobs | GET | `/{job_id}/bundle` | - | zip 번들 |

- **AI 보조**(`ai_mode`/`ai_assist`)는 §1.4 `get_active()` 연결 → `OpenAiCompatibleClient` 로 호출. 미설정/실패 시 규칙기반 폴백 + warning(“LLM 미설정/실패로 규칙 기반 사용”). MVP 서비스의 폴백 구조 그대로.
- 서버 검증: markdown 크기/문자수 제한, 데이터 행수 제한(config 에 상수 추가 또는 모듈 상수). 확장자 화이트리스트.

### 2.5 렌더링 결정(중요) — 서버 PNG 제거

- **차트**: `chart_service.py` 는 pandas 집계 후 **ECharts option(JSON)만** 반환. MVP `renderer.render_chart`(matplotlib SVG/PNG), `chart.svg/chart.png` 산출은 **삭제**. 미리보기는 브라우저 ECharts.
- **다이어그램**: `diagram_service.py` 는 **Mermaid 소스(.mmd)만** 산출 + `validate_mermaid` 로 금지 지시어 차단. MVP `cairosvg` export(`export_svg`)는 **삭제**(브라우저에서 Mermaid→SVG/PNG). `preview.build_mermaid_preview`(벤더 mermaid.min.js) 대신 프런트가 렌더하므로 서버는 소스만.
- **보고서**: `report_service.py` 는 markdown→sanitize HTML 을 **기존 `markdown` 패키지 + `newsletter/services/html_render_service.sanitize_html_fragment`** 로 생성(render 모듈 `api.py` 와 동일 경로). MVP 의 벤더 `build_report.py` subprocess/`bleach` 의존은 **미사용**(신규 의존성 회피). 산출물: `aeroone_report.md`, `aeroone_report.html`, `manifest.json`.
- **신규 백엔드 의존성**: `pandas`, `numpy` (차트 집계) 만 `backend/requirements.txt` 에 추가. `openpyxl` 은 xlsx 지원 시 추가(선택 — 미설치면 xlsx 만 422 로 안내). `bleach`/`cairosvg`/`matplotlib`/`httpx` 는 추가하지 않는다. → 리스크 §7 에 폐쇄망 wheel 확보 항목 기록.

### 2.6 프런트 페이지 + 프록시

- 페이지(모두 `AppShell` 사용, `active` 는 'dashboard' 유지 또는 신규 nav 값):
  - `frontend/app/office-tools/report/page.tsx`
  - `frontend/app/office-tools/chart/page.tsx`
  - `frontend/app/office-tools/diagram/page.tsx`
- 클라이언트 컴포넌트(렌더 라이브러리는 **dynamic import + client component**, SSR 비활성 `{ ssr: false }`):
  - `frontend/components/office-tools/chart-preview.tsx` → `echarts` dynamic import.
  - `frontend/components/office-tools/diagram-preview.tsx` → `mermaid` dynamic import.
  - `frontend/components/office-tools/report-form.tsx`, `chart-form.tsx`, `diagram-form.tsx`.
- 프록시(단일 catch-all, 업로드 multipart/스트림 통과):
  - `frontend/app/api/frontend/office-tools/[...segments]/route.ts` (GET/POST). 쿠키 전달 + same-origin. AI 프록시(`ai/upstream.ts`)의 local-first(127.0.0.1:18437) 후 server base 폴백 패턴 참고. multipart 는 `request.body` 스트림/`request.formData()` 재전송, `Content-Type` 보존.
- API 클라이언트/타입: `frontend/lib/api.ts`, `frontend/lib/types.ts` 에 office-tools 호출/타입 추가.
- **package.json 신규 의존성**: `echarts`, `mermaid` (dynamic import). 폐쇄망 오프라인 번들에 포함되도록 리스크 §7 에 기록. CDN 금지(폐쇄망) — npm 설치 후 로컬 번들.

### 2.7 alembic 는 office_tools 에는 불필요

office_tools 는 파일 JobStore 라 DB 스키마 변경 없음. **단, 대시보드 카드 시드는 §3 의 마이그레이션 0010 에서 처리**.

---

## 3. 대시보드 카드 (service_modules) — office 3종 + Leantime

세 자리 동시 변경(진실 원천 일치): **(a) alembic 시드 (b) `admin/api.py` DEFAULT_SERVICE_MODULES (c) `frontend/app/page.tsx` FALLBACK_MODULES**. 세 자리의 컬럼값이 서로 어긋나면 안 된다.

### 3.1 정확한 컬럼값 (4개 카드)

`section` 은 기존 개발도구(ai/viewer/ladder)와 **동일하게 `'Development'`** 사용(page.tsx `SECTION_ORDER` 에 이미 존재).

| key | title | description | href | section | status | badge | sort_order | is_enabled | is_external | visibility | required_permission | resource_type | resource_id |
|-----|-------|-------------|------|---------|--------|-------|-----------|-----------|------------|-----------|--------------------|--------------|-------------|
| `office-report` | `보고서 스튜디오` | `Markdown 을 사내 표준 HTML 보고서로 변환.` | `/office-tools/report` | `Development` | `development` | `Active` | 110 | true | false | `admin` | null | null | null |
| `office-chart` | `차트 스튜디오` | `CSV·표 데이터를 ECharts 차트로 시각화.` | `/office-tools/chart` | `Development` | `development` | `Active` | 120 | true | false | `admin` | null | null | null |
| `office-diagram` | `다이어그램 스튜디오` | `설명을 Mermaid 다이어그램으로 생성.` | `/office-tools/diagram` | `Development` | `development` | `Active` | 130 | true | false | `admin` | null | null | null |
| `leantime` | `Leantime` | `프로젝트 관리(외부 폐쇄망 앱). 운영자 설치 필요.` | `http://localhost:8081` | `Development` | `development` | `External` | 140 | true | true | `admin` | null | null | null |

- Leantime 은 `is_external=true` → `page.tsx` 에서 `NotebookLinkCard` 로 렌더(기존 open-notebook 과 동일 분기). href 는 운영자 환경에 맞게 바꿀 수 있게 런북에 명시.

### 3.2 alembic 마이그레이션 (0010) — 멱등 삽입

- 파일: `backend/alembic/versions/20260711_0010_office_tools_service_modules.py`
- `revision = "20260711_0010"`, `down_revision = "20260711_0009"`
- 기존 운영 DB 에는 이미 기본 10개 행이 있으므로 `_ensure_service_modules`(빈 테이블일 때만 시드)로는 안 들어간다. → **마이그레이션에서 4개 행을 멱등 삽입**한다:
  - `bind.execute(sa.text("INSERT INTO service_modules (key,title,...) SELECT ... WHERE NOT EXISTS (SELECT 1 FROM service_modules WHERE key=:key)"), {...})` 를 4회, 또는 각 key 존재 확인 후 `op.bulk_insert`.
- `downgrade()`: `DELETE FROM service_modules WHERE key IN ('office-report','office-chart','office-diagram','leantime')`.

### 3.3 코드 시드 (DEFAULT_SERVICE_MODULES)

`backend/app/modules/admin/api.py` 의 `DEFAULT_SERVICE_MODULES` 리스트에 §3.1 4개 dict 추가(신규 설치/빈 테이블용). 컬럼 키는 기존 dict 와 동일하게 전부 명시.

### 3.4 프런트 fallback (FALLBACK_MODULES)

`frontend/app/page.tsx` 의 `FALLBACK_MODULES` 배열에 §3.1 4개 항목 추가(id 는 11..14). `ServiceModule` 타입 형태 그대로. degraded 경로에서 비관리자에게는 자동 숨김(기존 필터 `visibility==='public' && !required_permission` — admin visibility 라 숨겨짐 = 의도대로).

---

## 4. Alembic 체인 요약

```
20260707_0008 (head, 기존)
   └─ 20260711_0009_llm_connections            (create llm_connections)
        └─ 20260711_0010_office_tools_service_modules  (seed 4 service_modules, 멱등)  ← 새 head
```

`down_revision` 체인을 반드시 위대로 연결. 적용 검증: `backend/.venv/Scripts/python.exe -m alembic upgrade head` 후 `alembic current` = `20260711_0010`.

---

## 5. TDD 테스트 목록

### 5.1 백엔드 (`backend/tests/unit/`, pytest)

| 파일 | 핵심 검증 |
|------|-----------|
| `test_llm_crypto.py` | encrypt→decrypt 왕복 일치; tag 변조 시 `ValueError`; nonce 매번 상이; `mask()` 접두+뒤4자·짧은 키 전체 마스킹. |
| `test_llm_connection_service.py` | create 시 키 암호화 저장(평문 아님); `set_default` 후 활성 1개 유일; `get_active()` 우선순위(default→enabled 최소 id→None); update 부분수정 시 키 유지. |
| `test_llm_connections_api.py` | `admin.ai.manage` 없으면 403; CSRF 없으면 403; 응답 DTO 에 평문 키 부재(마스킹만); verify 가 `/v1/models` 호출(모킹)·성공/실패 분기; 감사기록 after 에 평문 키 부재. |
| `test_office_tools_auth.py` | 4개 라우터 대표 엔드포인트가 미로그인 401; 로그인 시 통과. |
| `test_office_tools_report.py` | markdown→HTML 생성; `<script>`/이벤트 핸들러 제거(sanitize); job artifact(md/html/manifest) 등록; ai_mode 잘못된 값 422. |
| `test_office_tools_charts.py` | CSV inspect profile(row/col/columns); generate 가 echarts_option 반환; 빈/미지원 확장자 422; manual_spec 컬럼 검증. |
| `test_office_tools_diagrams.py` | Mermaid 소스 생성; 금지 지시어(`click`,`javascript:`,`<script>`) 거부(422/ValueError); 잘못된 diagram_type 거부. |
| `test_office_tools_jobs.py` | 잘못된 job_id(정규식 밖)·경로탈출(`..`) 404/차단; 정상 artifact 다운로드; bundle zip 생성. |
| `test_service_modules_office_seed.py` | 신규 4개 카드 존재·`visibility='admin'`·`section='Development'`·leantime `is_external=true`; 비관리자 public 목록에서 미노출. |

- 테스트 하네스는 기존 `backend/tests/unit/ai`, `test_admin_permissions.py` 의 앱/DB 픽스처 패턴을 재사용(마이그레이션 or create_all 로 llm_connections 포함되게).

### 5.2 프런트 (`frontend/tests/`, vitest)

| 파일 | 핵심 검증 |
|------|-----------|
| `frontend/tests/app/home-page.test.tsx` (수정) | 기존 계약 유지 + 관리자에게 office 3종·leantime 카드 노출; 익명/비관리자에게 미노출(degraded/live 양쪽). |
| `frontend/tests/app/office-tools-report-page.test.tsx` | 페이지가 AppShell + 폼 렌더; 제출 시 프록시 경로 호출(모킹). |
| `frontend/tests/app/office-tools-chart-page.test.tsx` | inspect/generate 흐름; echarts 컴포넌트 dynamic import 경계(모킹). |
| `frontend/tests/app/office-tools-diagram-page.test.tsx` | generate 흐름; mermaid 컴포넌트 경계(모킹). |
| `frontend/tests/lib/office-tools-api.test.ts` | api 클라이언트가 `/api/frontend/office-tools/*` 정확 경로·메서드 구성. |
| `frontend/tests/app/admin-llm-connections.test.tsx` | 시스템 탭 "AI 연결" 카드: 목록/생성/검증 액션이 `/api/frontend/admin/llm-connections*` 호출; 키 입력 password·목록 마스킹 표시. |

- 회귀 0: 기존 vitest/pytest 전부 통과 유지. `home-page.test.tsx` 계약을 깨지 않도록 추가만.

---

## 6. Leantime 동거 통합면 (산출물 C)

실제 IIS/PHP/MariaDB 설치는 이 환경에서 **실행 불가** → 통합면(카드/스크립트/문서)만 구현하고 **'운영자 검증 필요'** 로 명시.

### 6.1 카드
- §3.1 `leantime` 외부 링크 카드(세 자리 시드). 끝.

### 6.2 run_all.bat 기동 훅
파일: `scripts/run_all.bat` 수정(기존 Open Notebook 훅과 동일한 **있으면 호출/없으면 폴백** 구조).
- 신규 변수: `set "LEANTIME_PORT=8081"`, 런처 경로 `set "LEANTIME_LAUNCHER=%AEROONE_LEANTIME_LAUNCHER%"` (기본 `%ROOT%\..\Leantime\start-leantime.bat` 또는 미정의 시 스킵).
- 포트 preflight 에 `call :probe_port %LEANTIME_PORT% "Leantime" warn` 추가(warn — 없어도 AeroOne 진행).
- Open Notebook 기동 이후 단계에 Leantime 훅: `if exist "%LEANTIME_LAUNCHER%" ( call "%LEANTIME_LAUNCHER%" ) else ( echo [RUN-ALL][INFO] Leantime launcher 없음 → 통합면만 제공, 운영자 설치 필요 )`.
- `--help`/`:help` 라벨에 Leantime 훅 설명 한 줄 추가(CLAUDE.md §2.3 batch `:help` 라벨 요구).
- `--dry-run` 경로에도 Leantime 계획 출력 추가.

### 6.3 오프라인 런북
파일: `docs/runbook/leantime-offline.md` (신규).
- 내용: IIS + PHP(FastCGI) + MariaDB 설치 순서, Leantime 배포, 포트 8081 바인딩, AeroOne 카드 href 조정, AGPL v3 소스오퍼(수정 소스 제공 의무) 안내, run_all.bat 훅 연결(`AEROONE_LEANTIME_LAUNCHER`).
- `docs/INDEX.md` 에 입구 링크 추가(CLAUDE.md §2.5 wiki 입구 갱신 의무). 폐쇄망 운영자 섹션에 링크.

### 6.4 운영자 검증 항목(문서 말미 체크리스트)
- [ ] IIS/PHP/MariaDB 실제 설치·기동 확인
- [ ] Leantime 8081 바인딩 및 브라우저 접속 확인
- [ ] 대시보드 Leantime 카드 → 8081 링크 이동 확인
- [ ] AGPL 소스오퍼(수정본 포함) 게시 위치 확보
- [ ] run_all.bat 에서 `AEROONE_LEANTIME_LAUNCHER` 훅 동작 확인

---

## 7. 리스크 / 운영자 검증 필요 사항

1. **신규 백엔드 의존성(pandas/numpy)**: 폐쇄망 오프라인 wheel 확보 필요. `openpyxl`(xlsx) 는 선택. bleach/cairosvg/matplotlib/httpx 는 도입하지 않음으로 마찰 최소화. → `setup_offline.bat`/requirements 동결 확인.
2. **신규 프런트 의존성(echarts/mermaid)**: CDN 금지(폐쇄망). npm 설치 후 로컬 번들에 포함되어야 함. dynamic import + `ssr:false` 로 서버 번들 오염 회피.
3. **암호화 키가 `jwt_secret_key` 파생**: 시크릿 회전 시 기존 `api_key_encrypted` 복호 불가 → 재등록 필요. 런북에 명시. development(기본 `change-me`)에서는 약한 키 — production/closed_network 은 config 가 ≥32자 강제.
4. **기존 AeroAI Ollama 경로 미변경**: 레지스트리 도입 후에도 `/api/v1/ai/chat` 은 Ollama 유지(회귀 위험 회피). 통합 전환은 후속 빌드. 로컬 Ollama 를 레지스트리에 등록하면 office-tools 는 동일 OpenAI 호환 경로로 커버됨.
5. **service_modules 멱등 삽입**: 기존 운영 DB(행 존재)와 신규 설치(빈 테이블) 양쪽 동작을 마이그레이션 0010 의 `WHERE NOT EXISTS` 로 보장해야 함. 마이그레이션 시드/코드 DEFAULT/프런트 FALLBACK 세 자리 값 불일치 금지.
6. **section 표기 불일치 유산**: 마이그레이션 0004 는 `section='개발중'` 으로 시드했으나 현재 코드/프런트 진실은 `'Development'`. 신규 카드는 `'Development'` 로 통일(page.tsx SECTION_ORDER 기준). 기존 '개발중' 행 마이그레이션은 이번 스코프 밖(건드리지 않음).
7. **Leantime 전 과정 운영자 검증**: IIS/PHP/MariaDB 설치·AGPL 소스오퍼는 이 환경에서 실행/검증 불가 — 문서+스크립트 훅+카드만 제공.
8. **office-tools 파일 JobStore 정리**: `backend/data/office_jobs/` 무한 증가 → 보존일 정리는 후속(런북에 수동 정리 안내). 백업(admin backup)에는 포함하지 않음(공개/정적 루트 제외 정책 유지).

---

## 8. 단계별 "만질 파일" 색인 (구현 순서)

### 단계 1 — LLM 연결 레지스트리 (산출물 A)
- 생성: `backend/app/modules/ai/llm_crypto.py`, `backend/app/modules/ai/llm_connection_service.py`, `backend/app/modules/ai/openai_client.py`, `backend/app/modules/ai/api/admin.py`
- 수정: `backend/app/modules/ai/models.py`(LlmConnection 추가), `backend/app/modules/ai/schemas.py`(연결 DTO), `backend/app/main.py`(ai_admin_router include)
- 마이그레이션: `backend/alembic/versions/20260711_0009_llm_connections.py`
- 프런트: `frontend/components/admin/sections/admin-system-section.tsx`(AI 연결 카드), `frontend/components/admin/admin-console-tabs.tsx`(state/액션/refresh), `frontend/lib/api.ts`, `frontend/lib/types.ts`
- 테스트: `backend/tests/unit/test_llm_crypto.py`, `test_llm_connection_service.py`, `test_llm_connections_api.py`, `frontend/tests/app/admin-llm-connections.test.tsx`

### 단계 2 — office-tools 모듈 (산출물 B)
- 생성: `backend/app/modules/office_tools/{__init__,schemas,job_store,security}.py`, `.../services/{__init__,report_service,chart_service,diagram_service,data_loader}.py`, `.../api/{__init__,reports,charts,diagrams,jobs}.py`
- 수정: `backend/app/main.py`(4개 router include), `backend/requirements.txt`(pandas/numpy[/openpyxl])
- 프런트: `frontend/app/office-tools/{report,chart,diagram}/page.tsx`, `frontend/components/office-tools/{report-form,chart-form,diagram-form,chart-preview,diagram-preview}.tsx`, `frontend/app/api/frontend/office-tools/[...segments]/route.ts`, `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/package.json`(echarts/mermaid)
- 테스트: `backend/tests/unit/test_office_tools_{auth,report,charts,diagrams,jobs}.py`, `frontend/tests/app/office-tools-{report,chart,diagram}-page.test.tsx`, `frontend/tests/lib/office-tools-api.test.ts`

### 단계 3 — 대시보드 카드 (office 3종 + Leantime)
- 마이그레이션: `backend/alembic/versions/20260711_0010_office_tools_service_modules.py`
- 수정: `backend/app/modules/admin/api.py`(DEFAULT_SERVICE_MODULES), `frontend/app/page.tsx`(FALLBACK_MODULES)
- 테스트: `backend/tests/unit/test_service_modules_office_seed.py`, `frontend/tests/app/home-page.test.tsx`(확장)

### 단계 4 — Leantime 동거 (산출물 C)
- 수정: `scripts/run_all.bat`(기동 훅 + :help + dry-run), `docs/INDEX.md`(입구)
- 생성: `docs/runbook/leantime-offline.md`

### 최종 게이트 (CLAUDE.md §2.6)
- `backend/.venv/Scripts/python.exe -m pytest backend/tests` 전량 통과 카운트
- `npm run test`(Vitest) 전량 통과 카운트
- `alembic upgrade head` → current = `20260711_0010` 확인
- 두 카운트를 커밋 `Tested:` 에 병기(구현 에이전트가 커밋 시).
