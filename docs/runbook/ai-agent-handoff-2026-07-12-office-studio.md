# AI 에이전트 핸드오프 — `feature/dashboard-enhancements` (Office Studio 구현 세션)

- 작성일: 2026-07-12
- 작성 워크트리: `D:\Chanil_Park\Project\Programming\AeroOne\.worktrees\dashboard-enhancements`
- 브랜치: `feature/dashboard-enhancements` (로컬 전용, origin push 안 됨)
- 이 세션 시작 커밋: `0f7307d` (직전 핸드오프 색인) / 이 세션 마지막 커밋: `d687c9b`
- 선행 핸드오프: [`ai-agent-handoff-2026-07-11-dashboard-enhancements.md`](ai-agent-handoff-2026-07-11-dashboard-enhancements.md) — 이 브랜치가 왜 `1.13.0-dev` 활성 계획과 독립인지, 병합 보류 조건
- 대상 독자: 이 워크트리를 이어받는 AI 에이전트 / 사람 운영자
- 목적: 이 세션에서 구현한 **Office Studio(오피스 도구) + 관리자 LLM 연결 + Leantime 동거**의 전체 그림, 실행·검증 방법, 남은 운영자 작업, 진실 원천 지도를 한 자리에서 파악하게 한다.

---

## 0. 가장 먼저 읽을 결론

| 질문 | 답 |
|---|---|
| 무엇을 만들었나 | 대시보드에 로그인 후 보이는 **Office Studio**(보고서·차트·다이어그램 허브) + 관리자 등록형 **LLM 연결(AI 연결)** + **Leantime 동거** 통합면 |
| 지금 동작하나 | 예. 로컬에서 backend(18437)+frontend(29501) 프로덕션 기동 상태로 브라우저 실구동 확인함 |
| 병합됐나 | 아니오. `feature/dashboard-enhancements` 에만 있음. main 병합은 운영자 승인 + `1.13.0-dev` Task 10 gate 확인 후(선행 핸드오프 참조) |
| 테스트 통과하나 | backend 364 passed / 2 failed(사전 실패, 아래 §9), frontend 348 passed, typecheck 0, build 성공 |
| 커밋 규칙 | `AGENTS.md`/`CLAUDE.md` 동일 적용(한국어 3문단 + Lore trailer). 이 세션 11개 커밋 모두 준수 |
| 커밋 안 한 것 | `AeroOne Tool/`(원본 MVP zip·추출본)은 `.gitignore` 참조로만 두고 미추적. 런타임 DB(`backend/data/aeroone.db`)도 미추적 |

---

## 1. 이 세션에 만든 것 (기능 단위)

### 1.1 관리자 등록형 LLM 연결 레지스트리 (커밋 `32ed6b1`)
- 관리자 콘솔 **시스템 → AI 연결** 카드에서 OpenAI 호환 엔드포인트(base_url + api_key)를 등록 → `/v1/models` 로 모델 목록을 불러오고 `/v1/chat/completions` 로 호출.
- 사내 Ollama(`http://<host>:11434/v1`)와 외부 gpt-oss(OpenAI 호환) 둘 다 이 방식으로 커버.
- 키는 서버에만 암호화 저장(`llm_crypto`, stdlib HMAC Encrypt-then-MAC, 원천 `jwt_secret_key`), 응답·감사에는 마스킹만. 권한 `admin.ai.read`(읽기)·`admin.ai.manage`(변경)+CSRF.
- office-tools 의 AI 보조가 이 "활성 기본 연결"을 소비. 없으면 규칙 기반 폴백.

### 1.2 Office Studio — 오피스 도구 3종 흡수 (커밋 `e66cf69` → `52110a5` → `c1fdf77` → `45c963f` → `d687c9b`)
- Tool MVP(`AeroOne Tool/tool-mvp-v0.1.0/`)의 보고서(SVC-01)·차트(SVC-02)·다이어그램(SVC-03)을 AeroOne 백엔드 라우터 + Next.js 페이지로 **흡수**(새 포트·배치 0).
- **단일 허브**: 대시보드 카드 1장 `Office Studio`(`/office-tools`) → 다이어그램/차트/보고서 **탭 허브**. 딥링크 `/office-tools?tab=chart`.
- **처리 과정 표시**: 각 도구에 파이프라인 스텝퍼(입력→AI/규칙→검증→렌더→산출물), 생성 후 완료·사용 엔진(AI/규칙) 표기.
- **표현 고급화**: 차트=검증 팔레트+라운드 막대(단일 막대 그라디언트)·부드러운 선+영역 그라디언트·파이 보더·툴팁/레전드(`echarts-beautify.ts`), 다이어그램=Mermaid 브랜드 컬러 `base` 테마+곡선 엣지. **다계열 지원**: `ChartSpec.stacked` + 그룹/다중 y → 누적막대·그룹막대·다계열선(누적 세그먼트는 2px 표면 틈).
- **입력 방식(3가지)**: 각 폼 상단 `UsageGuide`(기본 펼침)가 ① 예제 선택 → 바로 생성 / ② 파일·정형 텍스트 / ③ 목적·서술형을 상시 안내. 차트·보고서는 파일 ↔ 직접 입력 토글(`DataInput`, 모드별 형식 힌트).
- **단계형 UX**: 3폼 모두 `StepSection` 으로 ① 입력 → ② 옵션/메타 → ③ 생성 번호 단계(왼쪽 강조선·완료 시 체크).
- **예제 원클릭 생성**: 예제 칩을 누르면 폼을 채우고 **곧바로 생성까지** 실행(`runGenerate` 명시 인자). 다계열 예제는 완성된 `manual_spec`(ChartSpec)을 그대로 넘겨 결정적 렌더.
- **예제 샘플 18종**: 다이어그램 6(플로우·시퀀스·상태·간트·로드맵·**주문 결제 시퀀스**), 차트 8(막대·선·파이·산점·히스토그램·**누적막대·그룹막대·다계열선**), 보고서 4(매출·장애 사후분석·주간·**경영 대시보드**). 도구별 '예제' 칩(`SamplePicker`).
- 서버 PNG(CairoSVG/Matplotlib)는 폐쇄망 마찰이라 **비활성**(브라우저 ECharts/Mermaid 렌더). 차트 집계는 pandas 서버 처리.
- 산출물은 `OfficeJobStore`(`backend/data/office_jobs`)에 `owner_id` 스코프(타인 접근 403).

### 1.3 Leantime 동거 (커밋 `35ae363` → `9b5df55`)
- Leantime(PHP+MariaDB+IIS 완제품, AGPL)은 **흡수 불가** → 동거: 링크 카드 + `run_all.bat` 기동 훅 + 오프라인 런북.
- 카드는 처음에 외부 링크(:8081)였으나, 미설치 시 빈 화면이 나서 **내부 안내 페이지 `/leantime`** 로 변경(설명·설치 3단계·호스트 인식 열기 버튼·런북 안내).
- **킷 기반 실시간 감지**: 사용자 제공 SaaS Kit v2.0.0(Leantime v3.9.8+MariaDB 11.4+PHP 8.3 오프라인 설치) 의 `health_url` 설계를 이어, 백엔드 `GET /api/v1/leantime/health`(127.0.0.1:8081 TCP 프로브, env `AEROONE_LEANTIME_HEALTH_URL`) 가 `/leantime` 페이지(`LeantimeStatus`)에 '구동 중/미설치' 배지를 실시간 표시. '열기'는 구동 중일 때만 활성(미구동이면 비활성 안내 → 빈 화면 차단). 실제 스택 설치는 여전히 운영자 단계(관리자 권한).

### 1.4 성능 (커밋 `c1fdf77`)
- 대시보드 SSR 이 테마·권한·모듈 조회를 `Promise.all` 병렬화 + Next 15 `cookies()` await(동기 경고 제거).
- 체감 속도의 핵심은 **프로덕션 빌드**(`next build`→`next start`): dev 첫-컴파일(특히 mermaid)로 `/office-tools`가 ~13초 걸리던 것을 ~0.03초로.

---

## 2. 이 세션 커밋 목록 (11개, `034bd03..HEAD`)

| 커밋 | 요지 |
|---|---|
| `0f7307d` | 대시보드 워크트리 핸드오프 문서를 색인에 연결(직전) |
| `b644f3f` | 두 MVP 참조 패키지 보존 + 무거운 추출본 `.gitignore` 제외 |
| `32ed6b1` | 관리자 등록형 LLM 연결 레지스트리 |
| `e66cf69` | 오피스 도구 3종(보고서·차트·다이어그램) 흡수 |
| `35ae363` | Leantime 동거 통합면(카드·`run_all` 훅·런북) |
| `aafe3ed` | 신규 런북 3종을 `docs/INDEX.md` 색인 |
| `52110a5` | 오피스 도구를 단일 허브로 + 샘플 예제·처리 과정 |
| `c1fdf77` | 대시보드 속도 + 차트·다이어그램 표현/UX 고급화 + 'Office Studio' 영문명 |
| `45c963f` | 샘플을 도구별 다중 예제(12→13종)로 확장 |
| `9b5df55` | Leantime 카드 → 내부 안내 페이지(빈 화면 해결) |
| `d687c9b` | 입력을 파일·텍스트 겸용 단계형 UX 로 고도화 |
| `e8abd8d` | 이 핸드오프 문서 최초 작성·색인 |
| `ee382a2` | Leantime 킷 기반 실시간 감지·연결(`/api/v1/leantime/health` + `LeantimeStatus`) |
| `b0aac38` | 오피스 스튜디오 원클릭 예제·상시 사용법(`UsageGuide`)·단계 구분 강화 |
| `c7b57f5` | 차트 누적·그룹·다계열(`ChartSpec.stacked`+`manual_spec`) + 복합 샘플(13→18종) |

---

## 3. 아키텍처 / 통합 지점

새 "로그인 후 도구" 는 아래 자리로 대시보드에 붙는다(기존 정형 패턴).

| 자리 | 위치 |
|---|---|
| 대시보드 카드(DB 시드) | `backend/alembic/versions/*` bulk_insert / update + `backend/app/modules/admin/api.py` `DEFAULT_SERVICE_MODULES` |
| 대시보드 카드(Fallback) | `frontend/app/page.tsx` `FALLBACK_MODULES` (회귀 계약 `frontend/tests/app/home-page.test.tsx`) |
| 프런트 페이지 | `frontend/app/office-tools/page.tsx`(허브) + `/office-tools/{report,chart,diagram}` + `/leantime` |
| 백엔드 라우터 | `backend/app/modules/office_tools/api/router.py` → `main.py` `include_router('/api/v1/office-tools')`, 상위 라우터가 `Depends(get_current_user)` 로 로그인 강제 |
| same-origin 프록시 | `frontend/app/api/frontend/office-tools/[...segments]/route.ts`, LLM 은 admin 프록시 재사용 |
| LLM 게이트웨이 | `backend/app/modules/ai/{llm_connection_service,llm_crypto,openai_client,api/admin}.py` |

3자리 일치 규칙: 카드값은 **마이그레이션 + `DEFAULT_SERVICE_MODULES` + `FALLBACK_MODULES`** 가 항상 같아야 함.

---

## 4. 마이그레이션 (0009~0014, 선형 단일 head)

| 리비전 | 내용 |
|---|---|
| `20260711_0009` | `llm_connections` 테이블 |
| `20260711_0010` | office-report/chart/diagram 카드 3행 시드(멱등) |
| `20260711_0011` | Leantime 카드 시드(당시 외부 링크) |
| `20260712_0012` | office 3종 카드 삭제 → 단일 허브 카드 `office-tools`(`/office-tools`) |
| `20260712_0013` | 허브 카드 제목 한글→`Office Studio` |
| `20260712_0014` | Leantime 카드 → 내부 `/leantime`, `is_external=0` |

현재 head = `20260712_0014`. 신규 DB 는 `alembic upgrade head` 한 번으로 위 상태에 도달.

---

## 5. 로컬 실행 방법 (이 워크트리 기준, dev)

이 워크트리는 처음엔 `.venv`·`node_modules`·DB 가 없다. 아래로 부트스트랩:

```bash
# 1) 백엔드 의존성
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# 2) DB 생성 + 마이그레이션 + 관리자 시드 (SQLite, dev)
export DATABASE_URL="sqlite:///<절대경로>/backend/data/aeroone.db"
export PYTHONPATH=.
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m scripts.seed      # 관리자 admin / (settings.admin_password 기본 'change-me')

# 3) 프런트 의존성
cd ../frontend && npm install
```

**기동 (개발용, dev — 첫 라우트 컴파일 지연 있음):**
```bash
# 백엔드 (APP_ENV=development 여야 secure_cookies=false, 로그인 쿠키가 http localhost 에서 동작)
cd backend && APP_ENV=development PYTHONPATH=. DATABASE_URL="sqlite:///.../backend/data/aeroone.db" \
  ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18437
# 프런트
cd frontend && npm run dev      # next dev -p 29501
```

**기동 (실사용 속도 — 프로덕션, 권장):**
```bash
cd frontend && npm run build && npm run start   # next start -p 29501, /office-tools 즉시 응답
```

- 접속: `http://localhost:29501`, 로그인 `admin` / (이 세션 로컬 DB 는 비번을 `27882788` 로 재설정해 둠 — 신규 DB 는 `ADMIN_PASSWORD` 환경변수 또는 기본값).
- 폐쇄망 정식 배포는 기존 `setup_offline.bat`/`start_offline.bat` 체계 + `alembic upgrade head`. 신규 파이썬 의존성(pandas/numpy/openpyxl)은 wheelhouse 재생성 필요.

---

## 6. 검증 게이트 (이 세션 마지막 실측)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend | `cd backend && ./.venv/Scripts/python.exe -m pytest tests -q` | **364 passed / 2 failed**(사전 실패, §9) |
| frontend 단위 | `cd frontend && npx vitest run` | **348 passed (75 파일) / 0 failed** |
| frontend 타입 | `cd frontend && npm run typecheck` | 에러 0 |
| frontend 빌드 | `cd frontend && npm run build` | 성공(전 라우트) |

병합 전 게이트는 backend pytest + frontend vitest 동시 통과(`CLAUDE.md` §2.6).

---

## 7. 현재 실행 상태

- backend uvicorn `127.0.0.1:18437`, frontend `next start` `29501` 이 이 세션 동안 기동 상태. 세션이 끝나면 프로세스가 정리될 수 있으니 §5 로 재기동.
- 로컬 DB `backend/data/aeroone.db` 에 마이그레이션 head + 관리자(admin/27882788) + 카드 시드가 들어 있음(gitignore, 커밋 안 됨).

---

## 8. 운영자 후속 작업 (실배포 전)

1. `alembic upgrade head`(0009~0014) 반영.
2. 관리자 콘솔 **시스템 → AI 연결** 에 실 LLM(사내 gpt-oss URL+키 또는 Ollama `…:11434/v1`) 등록 → verify → 기본 지정. `admin.ai.manage` 가 운영 관리자 역할에 포함되는지 확인.
3. Leantime 실 스택(IIS+PHP+MariaDB 8081/3307) 설치·기동·검증 — [`leantime-codeploy.md`](leantime-codeploy.md) §7. AGPL 소스오퍼 게시.
4. 차트 서버 PNG 를 켤 경우에만 CairoSVG/Matplotlib 네이티브 런타임 + CJK 폰트 설치(현재 빌드는 불필요).
5. 안정화 후 `office-tools`·`leantime` 카드 `visibility` 를 `admin`→`public` 전환 여부 결정.
6. `AeroOne Tool/` 참조 패키지(원본 zip·추출본)를 정식 커밋할지 결정(현재 gitignore).
7. 병합 판단: `1.13.0-dev` Task 10 gate 상태 재확인 후 운영자 승인 하에(선행 핸드오프 §2).

---

## 9. 알려진 이슈 / 함정

- **사전 실패 2건**: `tests/unit/shared/test_windows_batch_scripts.py::test_run_all_dry_run_waits_for_open_notebook_readiness`, `::test_run_all_passes_network_mode_to_open_notebook_bundle`. 이 워크트리에 Open Notebook 번들(`..\AeroOne-bundle`)이 없어 `run_all.bat --dry-run` 이 "번들 없음 폴백"을 출력해 나는 **환경 사전 실패**로, 이 세션 작업과 무관(변경 전 기준선에서도 동일). 새 회귀 아님.
- **예제 샘플 칩은 로그인 필요**: `SamplePicker` 가 `/api/frontend/office-tools/samples`(로그인 필수)를 호출한다. 미로그인 시 401 → 칩을 우아하게 숨김(폼은 정상). 로그인해야 칩이 뜬다.
- **dev vs 프로덕션 속도**: dev 는 라우트 첫 진입 시 컴파일 지연(특히 mermaid ~5000모듈)로 느리게 느껴진다. 실사용 체감은 프로덕션 빌드로 확인.
- **로컬 dev 계정**: `admin`/기본 `change-me`(이 DB 는 `27882788`). 실배포는 `ADMIN_PASSWORD`(≥12자) + `JWT_SECRET_KEY`(≥32자)를 `closed_network`/`production` 에서 강제.
- **AI 산출물 품질**: 실 LLM 미연결 상태에선 규칙 기반 폴백이라 AI 제안 경로는 mock/규칙 기준으로만 검증됨.

---

## 10. 코드 진실 원천 지도 (Office Studio)

| 영역 | 파일 |
|---|---|
| 허브·페이지 | `frontend/app/office-tools/page.tsx`, `frontend/components/office-tools/office-tools-hub.tsx`, `/office-tools/{report,chart,diagram}/page.tsx`, `frontend/app/leantime/page.tsx` |
| 폼·입력 UX | `frontend/components/office-tools/{report,chart,diagram}-form.tsx`, `step-section.tsx`, `data-input.tsx`, `sample-picker.tsx`, `process-steps.tsx`, `leantime-launch.tsx` |
| 표현(렌더) | `frontend/components/office-tools/{chart-preview,diagram-preview}.tsx`, `frontend/lib/echarts-beautify.ts` |
| 프런트 API/타입 | `frontend/lib/api.ts`(`fetchOfficeSamples`, generate*), `frontend/lib/types.ts`(`OfficeSample`, office 응답) |
| 백엔드 도구 | `backend/app/modules/office_tools/` (api/, services/{report,chart,diagram}, core/{job_store,llm_bridge}, samples_service.py, samples/*, schemas.py, security.py) |
| 백엔드 LLM | `backend/app/modules/ai/{llm_connection_service,llm_crypto,openai_client,api/admin,models,schemas}.py` |
| 카드 시드 | 마이그레이션 `20260711_0009`~`20260712_0014`, `backend/app/modules/admin/api.py`(`DEFAULT_SERVICE_MODULES`), `frontend/app/page.tsx`(`FALLBACK_MODULES`) |
| 런북 | [`office-tools.md`](office-tools.md), [`llm-connections.md`](llm-connections.md), [`leantime-codeploy.md`](leantime-codeploy.md) |
| 참조 패키지(미추적) | `AeroOne Tool/INTEGRATION_ANALYSIS.md`, `AeroOne Tool/BUILD_CONTRACT.md`(추출본·원본 zip 은 gitignore) |

---

## 11. 다음 에이전트 실행 순서

1. `git log --oneline 034bd03..HEAD` 로 이 세션 11개 커밋과 워킹트리 clean 확인.
2. §5 로 로컬 부트스트랩(venv/npm/alembic/seed) 후 프로덕션 빌드로 기동, 브라우저에서 로그인→Office Studio→각 탭 예제·생성 확인.
3. §6 게이트 재실행으로 회귀 0(사전 실패 2건 제외) 확인.
4. 운영자 요청이 있으면 §8 후속 작업으로 진행. 병합은 별도 승인 필요(선행 핸드오프 §2).
5. 새 도구/샘플 추가 시 진실 원천 3자리(마이그레이션+DEFAULT+FALLBACK) 일치와 `samples_service` 레지스트리만 채우면 프런트 칩이 자동 반영됨.
