# 오피스 도구(보고서·차트·다이어그램) 운영 런북

> 폐쇄망에서 반복하는 보고서 양식화·데이터 시각화·업무 도식화를 **AeroOne 로그인·테마·nav 안**
> 으로 흡수한 3종 도구다. 별도 포트·별도 배치·별도 로그인을 만들지 않고, 기존 백엔드
> (uvicorn 18437)와 프런트(Next 29501) **두 프로세스 안에서만** 동작한다.
>
> 원본은 `AeroOne Tool/tool-mvp-v0.1.0/`(FastAPI + Vite MVP, 포트 8088)이다. 이 런북은
> `backend/app/modules/office_tools/`와 Next.js 통합면의 **현재 운영 계약**을 설명한다.
> [`../../AeroOne Tool/INTEGRATION_ANALYSIS.md`](../../AeroOne%20Tool/INTEGRATION_ANALYSIS.md)는
> 2026-07-11/12 분석·완료 기록이며, 이 런북과 현재 소스보다 우선하지 않는다.

---

## 0. 결론 먼저

- 대시보드 개발중(Development) 섹션에는 관리자 전용(`visibility='admin'`) **Office Studio 단일
  허브 카드**(`key='office-tools'`, `/office-tools`)가 있다. 허브에서 보고서·차트·다이어그램 탭을
  연다. 하위 페이지(`/office-tools/{report,chart,diagram}`)는 직접 딥링크로 유지되지만 대시보드
  카드 3장이 아니다.
- 카드 `visibility` 는 대시보드 노출 후보만 제어한다. 활성 `public` 모듈의
  `required_permission=None` 은 로그인 사용자 전용이 아니라 **익명 요청도 통과시키는 권한 조건 없음**을
  뜻한다.
- Office API와 스튜디오 사용은 카드와 별개로 항상 세션 로그인과 `office.use` 를 요구한다. 따라서
  `public`+`required_permission=None` 카드가 익명에게 보이더라도 Office API 요청은 401이며, 이는
  로그인 전용 rollout 이 아니다.
- 백엔드는 `/api/v1/office-tools/*` 한 prefix 로 등록되고 이 로그인·`office.use` 검사를 라우터
  레벨에서 강제한다(미로그인 401, 권한 없음 403). 브라우저는 same-origin 프록시
  `/api/frontend/office-tools/[...segments]` 만 호출한다.
- **렌더링 결정**: 차트는 브라우저 ECharts, 다이어그램은 브라우저 Mermaid 로 렌더한다. 서버
  PNG(CairoSVG/Matplotlib)는 폐쇄망 마찰이라 이번 빌드에서 **비활성**이다. 서버는 소스/스펙만
  만든다(차트 집계는 pandas 서버 처리).
- **AI 는 선택적**이다. 활성 LLM 연결(관리자 등록, [`llm-connections.md`](llm-connections.md))이
  있으면 AI 보조를 쓰고, 없거나 실패하면 **규칙 기반 폴백**으로 내려가 도구는 계속 동작한다.
- **URL 동기 탭**: `/office-tools`는 세그먼트 ARIA 탭(`role="tablist"`/`role="tab"`)
  허브다. `?tab=diagram|chart|report` 쿼리로 탭을 딥링크·새로고침·뒤로가기까지 동기화하고,
  탭 전환 시에도 세 폼이 모두 마운트된 채 `hidden` 속성만 바뀌므로 각 탭의 입력·결과 상태가
  유지된다.
- 각 도구 결과와 허브 하단 **내 작업 이력**(`GET /jobs`)은 `llm_used`(AI 제안 사용 여부)를
  provenance로 표시한다. AI 미사용/폴백이면 "규칙 기반"으로 구분해 보여준다.
- 차트 스튜디오는 목적 문장 기반 자동 스펙 외에 **고급 컨트롤**(X축, 다중 Y, 그룹, 집계
  `none`/`sum`/`mean`/`count`/`min`/`max`, 누적, 정렬, 상위 N 제한, 방향)을 제공한다. 고급
  컨트롤은 새 API가 아니라 기존 `manual_spec_json` 경로로 같은 서버 ChartSpec을 만들며,
  서버(pandas 집계·`ChartSpec` 검증)가 여전히 최종 권한을 가진다.
- 작업 이력 카드는 **다시 열기**(완료된 결과를 그대로 복원, 재실행 없음)와 **설정 복제**(안전한
  구성만 복제, 서버 재실행 없음, 원본 파일/텍스트는 사용자가 다시 첨부)를 제공한다.

---

## 1. 통합 구조 (5자리)

새 도구가 대시보드에 등장하는 AeroOne 정형 패턴 5자리를 모두 채웠다.

| # | 자리 | 파일 |
|---|---|---|
| 1 | 대시보드 카드(DB 시드) | 초기 `20260711_0010` 뒤 `20260712_0012_office_tools_single_card.py`가 3개 카드를 삭제하고 `office-tools` 허브를 삽입, `0013`이 제목을 `Office Studio`로 갱신. Leantime은 `0014`가 내부 `/leantime`으로 갱신 |
| 2 | 대시보드 카드(코드 시드) | `backend/app/modules/admin/api.py` `DEFAULT_SERVICE_MODULES` (`office-tools`, `leantime`) |
| 3 | 대시보드 카드(Fallback) | `frontend/app/page.tsx` `FALLBACK_MODULES` (Office Studio ID `11`, Leantime ID `12`) |
| 4 | 프런트 허브·딥링크 | `frontend/app/office-tools/page.tsx`(URL 동기 ARIA 탭 허브, `?tab=`) + `frontend/app/office-tools/{report,chart,diagram}/page.tsx` + `frontend/components/office-tools/*`(`office-tools-hub.tsx`, `office-job-history.tsx`, `workspace-context.tsx`, `{report,chart,diagram}-form.tsx` 등) |
| 5 | 백엔드 모듈 + 라우터 등록 | `backend/app/modules/office_tools/` + `backend/app/main.py` (`include_router(prefix='/api/v1/office-tools')`) |
| — | same-origin 프록시 | `frontend/app/api/frontend/office-tools/[...segments]/route.ts` (쿠키 전달) |

진실 원천은 최종 카드 상태의 **마이그레이션 체인 · `DEFAULT_SERVICE_MODULES` · `FALLBACK_MODULES`**
3자리다. 현재 최종 체인은 `20260712_0014`까지이며, `office-tools`/`leantime`의 값이 세 자리에서
일치해야 한다. 회귀 계약은 `frontend/tests/app/home-page.test.tsx`가 지킨다.

### 1.1 백엔드 모듈 배치

```
backend/app/modules/office_tools/
├─ api/
│  ├─ router.py        상위 라우터. 로그인 + `office.use` 로 전 하위 경로를 강제
│  ├─ system.py        GET /health, GET /capabilities
│  ├─ samples.py       GET /samples, GET /samples/{key}
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
| 보고서 스튜디오(svc01) | `.md`/`.markdown`/`.txt` + 이미지/ZIP + 메타 + `ai_mode` | 인라인 CSS 자립형 sanitize HTML + Markdown 원본 + `manifest.json` | 서버가 오프라인 HTML 생성(외부 CDN 0) | Markdown·개별 자산 20MiB, 자산 압축/해제·멤버·이름·임베드 예산 |
| 차트 스튜디오(svc02) | `.csv`/`.xlsx`/`.json` + 목적 문장 + 옵션 | ChartSpec + **ECharts option(JSON)** + 집계 CSV + `manifest.json` | **브라우저 ECharts** (서버 PNG 없음) | 데이터 파일 20MiB, 100,000행(`MAX_CHART_DATA_ROWS`) |
| 다이어그램 스튜디오(svc03) | 자연어 설명 + 유형(flowchart/sequence/state/gantt) | **Mermaid 소스(.mmd)** + `manifest.json` | **브라우저 Mermaid(strict)** (서버 PNG 없음) | `validate_mermaid` 로 `click`/`javascript:`/`<script>`/`<iframe>`/`%%{init` 차단, 유형별 허용 접두 강제 |

세 도구 공통 규칙:

- **AI 는 명세만 제안, 앱이 재검증, 고정 렌더러가 최종 산출**. 모델이 꺼져 있어도 규칙 기반
  폴백으로 동작한다(보고서=원문 유지, 차트=규칙 기반 스펙, 다이어그램=규칙 기반 소스). 폴백
  사용 시 응답 `warnings` 에 사유를 붙인다.
- 업로드 전송량·raw multipart 전체/개별 파일 상한 및 보고서 자산의 압축 업로드 예산 초과는 **413**,
  파싱·의미 검증에서 판정되는 확장자·Markdown 문자 수·차트 행 수·수동 스펙·ZIP 중앙 디렉터리/
  멤버/경로/이름/압축 해제/임베드 예산 위반은 **422** 로 거부한다. §3.1의 HTTP 계약을 따른다.
- 산출물은 `OfficeJobStore` 에 `owner_id` 로 저장하고, 조회/다운로드 시 세션 사용자와
  `owner_id` 가 다르면 **403**, 없는 job/경로 탈출은 **404** 다.
- Office 도구 경로는 로그인뿐 아니라 정확한 `office.use` 권한을 요구한다. 보고서·차트·다이어그램 생성,
  차트 inspect, 본인 job 삭제, recovery evidence discard, 격리 복원·삭제, 관리자 purge 같은 mutation 은
  `X-CSRF-Token` 검증을 추가로 요구한다.
- `OfficeJobStore` 는 기본 30일 보존, 사용자당 100개/1GiB, 저장 볼륨 최소 여유 512MiB를
  강제한다. 값은 `OFFICE_JOB_RETENTION_DAYS`, `OFFICE_JOB_MAX_JOBS_PER_OWNER`,
  `OFFICE_JOB_MAX_BYTES_PER_OWNER`, `OFFICE_JOB_MIN_FREE_DISK_BYTES` 환경변수로 조정한다.
  보존 기간 삭제는 자동 생성 경로가 아니라 명시적인 관리자 purge로만 실행하며, `office.use` 외에
  별도 `admin.office.manage` 권한과 감사 기록이 필요하다.
- 차트 스튜디오의 프런트 **고급 컨트롤**(X축·다중 Y·그룹·집계·누적·정렬·상위 N 제한·방향)은
  `ChartManualSpecInput`을 만들어 기존 `POST /charts/generate`의 `manual_spec_json` 필드로
  보낸다. 새 엔드포인트나 클라이언트측 집계는 없다 — 서버가 여전히 `ChartSpec` 스키마 검증과
  pandas 집계를 수행하며, 프로파일에 없는 열 지정·중복 축 지정은 프런트에서도 선제 차단하지만
  최종 판정은 서버 422다.
- 산출물 다운로드·manifest artifact 링크(작업 이력의 manifest 파일 포함)는 브라우저가 백엔드를
  직접 호출하지 않고 same-origin 프록시 `/api/frontend/office-tools/...`를 통해서만 연다
  (`getOfficeArtifactProxyPath`).

---

## 3. API 요약

Office 도구 경로는 `/api/v1/office-tools` prefix 아래이며 **로그인 + `office.use` 권한 필수**
(미로그인 401, 권한 없음 403)다. 전역 상태는 별도 공개 경로 `/api/v1/health` 다. 브라우저는 Office
API를 직접 호출하지 않고 same-origin 프록시 `/api/frontend/office-tools/...` 를 통한다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/api/v1/health` | 전역 상태. `db_ok`와 canonical recovery fields `office_job_recovery_ok`, `office_job_unresolved_recovery_transactions` 포함(legacy alias 미제공) |
| GET | `/capabilities` | 서비스 플래그 + 활성 LLM 여부/모델명 + 상한. **base_url/api_key 미노출** |
| GET | `/samples`, `/samples/{key}` | 허브의 bundled 예제 목록 또는 단일 예제 |
| POST | `/reports/generate` | multipart(Markdown + 이미지/ZIP + 메타 + `ai_mode`) → sanitize HTML 보고서 |
| POST | `/charts/inspect` | 데이터 프로필(행/열/샘플)만. job 미생성 |
| POST | `/charts/generate` | multipart(데이터 + `prompt` + `ai_assist` + `chart_type`/`manual_spec_json`) → ECharts option |
| POST | `/diagrams/generate` | JSON(설명 + 유형) → Mermaid 소스 |
| GET | `/jobs/{job_id}` | 산출물 메타/다운로드/번들. 소유자 스코프(403/404) |
| GET | `/jobs` | 본인 job 최신순 목록 + 현재 job/byte 사용량과 quota |
| DELETE | `/jobs/{job_id}` | 본인 job 삭제. CSRF 필수, 타인 job 403. 성공은 `outcome`을 포함한 200, 부분 실패·미해결은 typed 500 |
| GET | `/jobs/recovery` | 정상 recovery와 손상 placeholder를 포함한 안전 inventory. `admin.office.manage` 필요 |
| DELETE | `/jobs/recovery/{recovery_id}` | 정상 recovery evidence 제거. `admin.office.manage` + CSRF + intent/완료·실패 감사 |
| GET | `/jobs/owner-identities` | 정상 owner-identity sidecar와 손상 placeholder의 안전 inventory. `office.use` + `admin.office.manage` 필요 |
| DELETE | `/jobs/evidence/{management_token}` | 손상 quarantine/recovery/owner-identity evidence의 **opaque token 기반 비가역 처분**. `admin.office.manage` + CSRF + intent/완료·실패 감사 |
| GET | `/jobs/storage` | owner quota와 분리된 logical artifact 및 모든 managed physical storage category/total. `admin.office.manage` 필요 |
| POST | `/jobs/admin/purge` | 만료 job 관리자 정리. `office.use` + 별도 `admin.office.manage` + CSRF + 감사 기록 |
| GET | `/jobs/admin/pending-receipts` | 모든 actor의 미해결 receipt 안전 inventory. intent·provenance·replay evidence·token 미노출, `admin.office.manage` 필요 |
| POST | `/jobs/admin/pending-receipts/{pending_result_id}/replay` | 비활성·삭제 actor를 포함한 receipt를 원래 provenance/idempotency로 재실행. `admin.office.manage` + CSRF + 별도 operator 감사 |
| GET | `/jobs/quarantine` | 정상 격리 job과 손상 placeholder를 포함한 안전 inventory. `admin.office.manage` 필요 |
| POST | `/jobs/quarantine/{quarantine_id}/restore` | 정상 격리 job 복원. `admin.office.manage` + CSRF + 감사 기록 |
| DELETE | `/jobs/quarantine/{quarantine_id}` | 정상 격리 job 제거. `admin.office.manage` + CSRF + 감사 기록 |

허브 하단의 **내 작업 이력**(`office-job-history.tsx`)이 `GET /jobs`로 본인 job 목록·현재
job/byte 사용량·quota를 표시하고, 카드 선택 시 `GET /jobs/{job_id}`로 상세를 가져와 다시
열기/설정 복제에 쓴다. 목록 항목은 소유자 스코프의 안전한 표시 필드(`title`, `service`,
`status`, `updated_at`, `llm_used`, `warnings`, manifest artifact 목록)만 노출하며, 원본
파일명·경로 같은 내부 필드는 포함하지 않는다. `admin.office.manage` 전용 recovery·storage·
purge API는 여전히 UI가 아니라 API 전용 운영 표면이다.

본인 job 삭제의 성공 응답은 `OfficeJobOwnerDeletionResponse`이며 job 제거와 owner-identity sidecar 제거를
분리해 `removed`, `durability`, `owner_identity_removed`, `owner_identity_durability`,
`retry_required`를 반환한다. Windows directory fsync 미지원은 두 durability를
`platform_best_effort`로 공개하며 완료된 삭제를 204 bodyless 응답으로 축약하지 않는다. 실제 fsync나
sidecar 정리 실패는 `OfficeJobOwnerDeletionFailureResponse`의 typed partial/unresolved detail과
감사 receipt를 남기므로 클라이언트는 응답 본문을 버리지 말고 재시도 여부를 판단해야 한다.

미해결 receipt는 원래 actor가 비활성화·삭제돼도 `GET /jobs/admin/pending-receipts`에서 안전한 상태만
조회할 수 있다. 관리자는 CSRF를 포함한 replay API로 receipt ID 하나를 재실행하며, 원 lifecycle 감사는
receipt에 저장된 원래 actor username/role·request provenance·idempotency key를 유지한다. 실행한 관리자는
별도의 `office_jobs.pending_receipt.replay.intent` 및 성공/실패 감사에 기록된다. 공개 inventory와 operator
감사에는 private intent, IP/user-agent, replay hash/path, audit metadata, corrupt-evidence token을 내보내지 않는다.

`ai_mode`(보고서) = `none`/`polish`/`executive`. `ai_assist`(차트/다이어그램) = bool.
`capabilities.llm.fallback` 은 항상 `rule-based`.

### 3.1 업로드 거부 HTTP 계약

Office의 보고서·차트 multipart 경로는 FastAPI form 파싱 전에 `OfficeMultipartIngressLimitMiddleware`가
경계한다. `Content-Length`가 endpoint 전체 상한을 넘거나, 스트리밍 중 raw multipart 전체·개별 파일·파일
개수 상한을 넘으면 **413**이다. 라우트의 bounded stream과 보고서 자산의 요청 공유 **압축 업로드** 예산
초과도 413으로 응답한다.

**422**는 바이트 전송량 자체가 아니라 파싱·검증 후에만 판단 가능한 입력이다. 미지원 확장자, Markdown
문자 수, 차트 행 수와 `manual_spec_json`, Mermaid 금지 지시어, ZIP 중앙 디렉터리·암호화/심볼릭 링크·
canonical 중복/경로·파일명·멤버 수·압축 해제·임베드 보고서 예산이 여기에 해당한다. 거부된 요청은 job이나
산출물을 만들지 않는다. 프록시와 호출자는 413과 422을 구분해 사용자에게 다시 업로드할지 입력을 고칠지
안내해야 한다.

### 3.2 Recovery·저장소·purge 판독

`GET /api/v1/health` 는 현재 `OfficeJobStore` recovery inventory를 읽는다. canonical health field는
`office_job_recovery_ok` 와 `office_job_unresolved_recovery_transactions` 뿐이며 legacy alias는 제공하지 않는다.
`office_job_recovery_ok` 는 정상 recovery와 손상 placeholder를 포함해 evidence가 없을 때만 `true` 이고,
`office_job_unresolved_recovery_transactions` 는 그 현재 항목 수다. 이 수가 0보다 크거나 inventory를 읽지 못하면
전역 `status` 는 `degraded` 이다(데이터베이스 상태도 함께 판정한다). 따라서 malformed recovery child도 즉시
degraded 상태로 보이며, 안전 처분 후 health는 남은 inventory를 반영한다.

`GET /jobs/recovery`, `GET /jobs/quarantine`, `GET /jobs/owner-identities` 항목은 항상 `kind` 로 정상
(`recovery`/`quarantine`/`owner_identity`)과 손상(`corrupt`)을 구분한다. 정상 owner-identity 항목은
`job_id`, `owner_id`, `physical_bytes`와 `null` `management_token`·`reason`을 제공하고, 손상 placeholder는
ID·owner를 `null`로 두며 opaque `management_token`, 실제 `physical_bytes`, 안전한 사유만 제공한다.
owner-identity inventory는 `total_bytes`, `corrupt_entries`, `corrupt_physical_bytes`도 함께 반환한다. 어느
inventory도 원본 파일명·경로·journal 내용은 응답과 감사에 노출하지 않는다.

정상 recovery는 `DELETE /jobs/recovery/{recovery_id}` 로만 삭제한다. malformed quarantine/recovery/
owner-identity child는 ID나 경로를 재구성하지 말고 각각의 inventory에서 받은 opaque
`DELETE /jobs/evidence/{management_token}` 로만 비가역 처분한다. owner-identity inventory 조회는
상위 `office.use`와 `admin.office.manage`가 모두 필요하지만 read-only라 CSRF나 감사 event를 만들지 않는다.
evidence 처분 경로는 상위 Office guard와 `admin.office.manage`, CSRF를 모두 요구하며, token의 intent를
먼저 commit한 뒤 성공 또는 `partial_failure` 감사를 남긴다.

recovery 삭제와 quarantine 복원·삭제의 성공 응답은 호환 inventory `item`과 전체 `outcome`을 함께 반환한다.
`outcome`은 `operation`, 대상 ID/token, job/owner ID, 논리·물리 bytes, `partial_bytes_removed`,
`published`, `removed`, `durably_synced`, `durability`, `retry_required`를 보존한다. `durability`는
`synced`, `platform_best_effort`, `pending` 중 하나다. Windows가 directory fsync를 제공하지 않으면
`platform_best_effort`·`durably_synced=false`·`retry_required=false`로 실제 한계를 공개하고, 실제 fsync
오류는 `pending`·`retry_required=true`와 HTTP 500
`{detail: {error, outcome}}`로 반환한다. response와 `partial_failure` audit은 같은 실제 outcome을
남기며, 이미 수행된 publish/delete를 일반 오류로 덮어 재시도 판단을 흐리지 않는다.

`POST /jobs/admin/purge` 가 이미 일부 파괴 작업을 완료한 뒤 실패하면 HTTP 500의
`{detail: {error, partial_result}}` 를 반환한다. `partial_result` 의 삭제·격리·실패 ID와 byte 수,
maintenance 결과는 실제 완료분의 증거이므로 재시도 전에 이를 확인하고 감사의 intent 및
`partial_failure` 기록과 대조한다. 모든 HTTP 500이 부분 결과를 뜻하는 것은 아니며, 이 구조는
부분 파괴 작업이 발생한 경우에만 제공된다.

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
  렌더한다. 서버 PNG는 현재 범위 밖이므로 Cairo/Pango·CJK 폰트 절차를 포함하지 않는다.
- **프런트 렌더 라이브러리**: ECharts / Mermaid 는 `frontend/package.json` 에 추가되어 Next 빌드
  산출물에 포함되므로 별도 CDN 반입이 필요 없다(외부 CDN 0 원칙 유지).

---

## 6. 사용 및 rollout

1. 기본값은 `office-tools` 카드를 `visibility='admin'`으로 유지하는 것이다. `public`과
   `required_permission=None`의 조합은 모든 로그인 사용자가 아니라 익명도 볼 수 있는 공개 모듈이다.
   이 조합으로 Office Studio를 login-scoped로 rollout 하지 않는다.
2. 로그인한 특정 사용자·그룹만 대상으로 rollout 하려면 먼저 사용자/RBAC 관리에서 대상에
   `office.use`를 부여한다. 그 다음 **지원되는 서비스 모듈 구성 경로**에서 `office-tools`의
   `visibility='public'`과 `required_permission='office.use'`를 함께 저장한다. 이 필수 권한을
   저장·보존할 수 없는 콘솔/자동화라면 `visibility='admin'`을 유지한다. 직접 DB 수정이나
   visibility만 바꾸는 우회는 지원되는 rollout 절차가 아니다.
3. 만료 산출물 purge, recovery/owner-identity inventory·evidence discard, 격리 inventory/복원/삭제,
   storage accounting 담당자에게만 별도 `admin.office.manage` 를 부여한다. 이 권한은 감사 기록이 남는
   `/api/v1/office-tools/jobs/admin/purge`, `/jobs/admin/pending-receipts*`, `/jobs/recovery`,
   `/jobs/owner-identities`, `/jobs/quarantine`, `/jobs/storage` 운영 작업에 쓰며 `office.use` 를 대체하지 않는다.
4. `office.use`와 카드 필수 권한이 모두 설정된 비관리자 계정으로 로그인해 대시보드 개발중 섹션의
   Office Studio 허브 카드를 연다.
   - **보고서**: Markdown 파일(+이미지/ZIP)과 제목/부제/버전/태그를 넣고 `ai_mode` 를 고른 뒤
     생성 → 미리보기·다운로드(단일 오프라인 HTML).
   - **차트**: 데이터 파일 업로드 → `inspect` 로 열 프로필 확인 → 목적 문장/차트 유형을 정해
     생성 → 브라우저 ECharts 미리보기·집계 CSV 다운로드.
   - **다이어그램**: 유형(flow/seq/state/gantt)과 설명을 넣고 생성 → 브라우저 Mermaid 미리보기·
     `.mmd` 다운로드.
5. 산출물은 본인 소유 job 으로만 조회·다운로드·삭제된다(타 사용자 job 은 403). 본인 job 목록과 현재
   job/byte 사용량·quota는 `GET /jobs` API로 확인하며, storage/recovery/purge는
   `admin.office.manage` 운영자가 API로 처리한다. 허브 UI는 생성 결과를 처리하며 운영 inventory와
   lifecycle 관리는 API를 사용한다.
6. (선택) AI 보조를 쓰려면 먼저 관리자 콘솔에서 LLM 연결을 하나 등록·기본 지정한다
   ([`llm-connections.md`](llm-connections.md)). 등록이 없으면 도구는 규칙 기반으로 동작한다.

> 로그인 범위 rollout은 `office.use`를 대상 사용자·그룹에 부여하는 것만으로 완료되지 않는다.
> 지원되는 모듈 구성 경로가 같은 카드에 `required_permission='office.use'`를 저장하기 전까지는
> `visibility='admin'`을 유지한다. 카드가 보인다는 사실만으로 Office API 접근은 허용되지 않는다.

---

## 7. G008 현재 테스트 계약과 source evidence

| 대상 | 현재 계약 |
|---|---|
| `backend/tests/unit/test_office_tools_auth.py`, `backend/tests/unit/test_office_tools_jobs.py` | `office.use`, CSRF, owner job 격리·quota, purge/recovery/evidence 감사, read lease와 durability partial outcome을 검증한다. |
| `backend/tests/unit/test_office_tools_report.py` | 413 Markdown·공유 압축 예산, 422 canonical 중복·경로/ZIP 중앙 디렉터리/압축 해제·임베드 예산, bounded image embedding을 검증한다. |
| `backend/tests/unit/test_office_tools_charts.py` | raw multipart의 선언·chunked 전체/개별 파일·파일 수 상한 413과 차트 입력 422 경계를 검증한다. |
| `backend/tests/unit/test_office_tools_diagrams.py` | 생성 mutation의 CSRF, 규칙 기반 폴백, Mermaid 검증과 산출물 계약을 검증한다. |
| `frontend/tests/lib/permission-catalog.test.ts`, `frontend/tests/app/office-tools-*.test.tsx`, `frontend/tests/lib/office-tools-api.test.ts` | 권한 카탈로그, Office Studio 허브·폼·same-origin API 클라이언트 계약을 검증한다. |
| `frontend/tests/app/home-page.test.tsx` | fallback 대시보드의 단일 Office Studio 카드와 내부 Leantime 카드 계약을 검증한다. |
| `frontend/tests/components/office-tools-hub.test.tsx` | URL 동기 ARIA 탭(딥링크·popstate·화살표/Home/End 키보드), 탭 전환 중에도 세 폼이 마운트 유지, 소유자 job 이력의 안전 표시 필드·manifest artifact 프록시 링크 화이트리스트, 다시 열기/설정 복제의 monotonic selection 전달과 미지원 service 거부를 검증한다. |
`G008`에서 추가·강화된 명시적 경계 사례는 `test_multipart_ingress_enforces_exact_and_chunked_file_and_total_limits`,
`test_generate_route_applies_compressed_budget_across_zip_parts_with_413`,
`test_generate_route_rejects_duplicate_canonical_key_across_zip_parts_with_422`,
`test_unpack_asset_zip_rejects_central_directory_amplification`,
`test_unpack_asset_zip_rejects_double_encoded_traversal`,
`test_embed_markdown_images_caches_repeated_image_and_enforces_budgets`,
`test_artifact_read_lease_blocks_concurrent_destructive_lifecycle_operation`,
`test_direct_quarantine_late_failures_preserve_exact_outcome_in_response_and_audit`다.

G008의 현재 evidence는 위 테스트 소스와 `backend/app/modules/office_tools/`의 대응 구현이다. 이 문서
정리 작업에서는 지시대로 테스트·lint·format·build·typecheck를 실행하지 않았으므로 새 pass/fail 수치를
기록하지 않는다. 실행 결과가 생길 때만 그 결과와 정확한 명령을 별도 검증 기록에 추가한다.

---

## 8. 운영자 검증 필요 (실배포 전)

- [ ] `backend/.venv` 에 pandas/numpy/openpyxl wheel 설치(운영과 동일 Windows/Python 로 생성한
      wheelhouse).
- [ ] `alembic upgrade head` 로 `20260712_0014`까지 반영(LLM 연결 `0009`, 초기 카드 시드
      `0010/0011`, 단일 Office Studio 허브 `0012`, 제목 갱신 `0013`, Leantime 내부 안내 `0014`).
- [ ] AI 보조를 쓸 경우 LLM 연결 1건 등록·검증·기본 지정([`llm-connections.md`](llm-connections.md)).
- [ ] login-scoped rollout은 대상 사용자·그룹에 `office.use`를 부여하고, 지원되는 모듈 구성 경로가 `office-tools`에 `required_permission='office.use'`와 `visibility='public'`을 함께 저장할 수 있을 때만 수행한다. 그 전에는 `visibility='admin'`을 유지한다.

---

## 관련 문서

- LLM 연결 설정: [`llm-connections.md`](llm-connections.md)
- Leantime 동거: [`leantime-codeploy.md`](leantime-codeploy.md)
- 통합 분석 역사 기록: [`../../AeroOne Tool/INTEGRATION_ANALYSIS.md`](../../AeroOne%20Tool/INTEGRATION_ANALYSIS.md)
- 폐쇄망 종합 가이드: [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
