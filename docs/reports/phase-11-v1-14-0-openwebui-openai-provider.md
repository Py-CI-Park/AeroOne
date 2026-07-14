# 단계 28 — Open WebUI 링크 실행 + OpenAI 호환 AI Provider (1.14.0)

- 버전: `1.14.0`
- 날짜: 2026-07-14
- 성격: minor — 신규 대시보드 launcher 표면(Open WebUI) + 관리자 전용 AI provider 병행 관리(설정/등록/회전/폐기)
- 기준 계획: `.gjc/_session-019f5ed2-bcd4-7000-8455-34da0bed5a92/plans/ralplan/019f5ed2-bcd4-7000-8455-34da0bed5a92/pending-approval.md`, SHA-256 `fdfa2f0e19abfaad14f4c6cc6b86f9754b70d51ada31efe16afa33d05a6429d6`(최종 stage-05 revision SHA `105fc8be689091d3b50788c73eb14b3f5725207c85aae8fbba67a17f9726a2f8`)
- 합의 receipt:
  - Architect CLEAR/APPROVE — `.gjc/_session-019f5eec-bc73-7000-8485-84c440329451/plans/ralplan/019f5eec-bc73-7000-8485-84c440329451/stage-05-architect.md`, SHA-256 `bb4f1ac44ce3793797164981bea63f918cde8a352394f80b96633136a26d87f0`
  - Critic OKAY — `.gjc/_session-019f5eec-ebe0-7000-9bb9-d0d931cfa271/plans/ralplan/019f5eec-ebe0-7000-9bb9-d0d931cfa271/stage-05-critic.md`, SHA-256 `06d8988af095dd2fa69a70876c7dc69d5404ccc62d4cf486593dc3696ec6e815`

---

## 1. 배경

1.13.2 까지는 AI 대화가 backend-only Ollama 단일 경로로 고정되어 있었고, Open WebUI/Open Notebook 같은 별도 배포 도구는 운영 참고 자료(단계 15 연구)로만 남아 있었다. 폐쇄망 현장에서는 두 가지 요구가 확인되었다.

- Open WebUI 를 이미 같은 PC(호스트 8080)에 병행 설치해 둔 현장에서, AeroOne 대시보드에서 별도 URL 암기 없이 새 탭으로 바로 열 수 있어야 한다. Open Notebook(8502) 카드와 동일한 "링크만" 원칙을 유지해야 하며, iframe 임베드나 상태 프록시는 추가 공격면이므로 배제한다.
- Ollama 모델이 부족한 업무(예: 더 큰 문맥, 특정 임베딩)에서 OpenAI 호환 엔드포인트를 병행 등록해 관리자가 명시적으로 전환할 수 있어야 한다. 다만 폐쇄망 보안 정책상 provider 키는 항상 write-only 여야 하고, 등록 대상은 신뢰된 HTTPS 또는 loopback 으로 제한되며, 실패 시 다른 provider 로 조용히 넘어가는 fallback 은 금지된다.

이 두 표면은 서로 독립적이지만 같은 릴리스로 묶어 관리자 AI 운영 UX 를 한 번에 정리한다.

## 2. 스레드 모델(Threat Model)

- **provider 키 노출**: 키는 저장 시 즉시 DPAPI(현재 Windows 로그인 SID 스코프)로 봉인되고, 이후 모든 조회 경로는 마스킹된 상태만 반환한다. 평문 키는 API 응답, 로그, 감사 이벤트 어디에도 남기지 않는다.
- **신뢰되지 않은 enrollment 대상**: provider 등록은 검증된 TLS 체인을 가진 `https://` 또는 loopback(`127.0.0.1`/`localhost`) 만 명시적 allow-list 로 통과시킨다. 그 외 대상(평문 HTTP, 임의 호스트)은 요청을 실제로 보내기 전에 fail-closed 로 거부해 SSRF/자격 유출 경로를 차단한다.
- **조용한 fallback**: provider 선택은 단일 명시적 선택이며, 실패한 provider 호출을 다른 provider 로 자동 재시도하지 않는다. 사용자가 어떤 provider 가 응답했는지 항상 명확해야 한다는 요구를 지킨다.
- **권한 상승**: provider 조회는 `admin.ai.read`, 등록·활성화·회전·폐기 mutation 은 `admin.ai.manage` 를 요구하는 기존 `ADMIN_PERMISSIONS` 카탈로그 키를 재사용한다. 신규 `admin.ai_provider.*` 키를 추가하지 않아 권한 카탈로그가 불필요하게 늘어나는 것을 피한다. mutation 은 `require_csrf` 와 조합하고, 조회·mutation 응답 모두 `Cache-Control: no-store` 를 강제해 provider 상태(등록 여부 포함)가 캐시/뒤로가기에 남지 않게 한다.
- **회전 경계 혼선**: provider 키 회전·폐기는 JWT/전체 사용자 비밀번호 사고 대응 회전(`scripts\rotate_aeroone_credentials.ps1`, [`credential-rotation.md`](../runbook/credential-rotation.md))과 저장 위치·코드 경로를 공유하지 않는다. provider 키는 `provider-credentials/<SID>/credential.dpapi` 단일 blob 의 원자적 교체이며, DB 사용자 비밀번호·세션·JWT 비밀값과는 별도 계약이다.
- **DPAPI 신원 이동**: provider 키는 현재 Windows 로그인 사용자 SID 로 스코프된다. 프로필 재발급이나 기기 교체로 SID 가 바뀌면 기존 암호문은 자동 복구되지 않고 그대로 읽을 수 없는 상태(부재로 취급)가 된다. 교차 프로필/교차 기기 DPAPI 복구·이관 경로는 의도적으로 제공하지 않으며, 운영자는 신뢰된 HTTPS/loopback 등록 절차로 재등록해야 한다.
- **감사 가시성**: provider 등록/활성화/회전/폐기/검증 실패는 기존 `admin_audit_events` same-transaction 감사 계약을 따르는 별도 카테고리로 남긴다. 키 값·요청 원문 등 비밀 소재는 기록하지 않고 결과(성공/실패, provider 종류, 조작자, 시각)만 metadata-only 로 남긴다.

## 3. 구현 범위

### 3.1 Open WebUI 링크 실행 (frontend)

- 대시보드에 `Open WebUI` 카드를 추가한다. 기존 `NotebookLinkCard` 를 일반화한 external-launcher 컴포넌트가 `launcher_kind`(`open-notebook` 8502 / `open-webui` 8080)를 분기하며, 두 카드 모두 현재 접속 호스트 기준 새 탭 링크(`target="_blank" rel="noopener noreferrer"`)만 열고 iframe 임베드나 헬스체크 프록시는 사용하지 않는다.
- 노출 조건은 `dashboard.openwebui.launch` 권한이다. 활성 관리자·일반 사용자 로그인에 기본 노출되며, 대기(pending) 계정과 비로그인 접속에는 노출되지 않는다.

### 3.2 OpenAI 호환 AI Provider (backend)

- `backend/alembic/versions/20260714_0011_ai_provider_and_launchers.py`(`down_revision=20260712_0010`)가 `ai_provider_config` 싱글턴 테이블(`singleton_id=1`, `selected_kind` `ollama`/`openai_compatible`, 독립된 `compatible_state`, `compatible_canonical_url`/`compatible_display_url`/`compatible_model`/`compatible_generation`, opaque `compatible_credential_ref` + 불변 `compatible_credential_binding_version`, 낙관적 `config_version`, `compatible_test_proof_*`)과 `ai_provider_operation_journal`(metadata-only 결과 감사, 후보 자재/키 미기록)을 추가한다. DPAPI 암호문 자체는 이 테이블에 저장하지 않고 opaque ref/version 만 저장한다.
- Ollama 는 별도 설정 행이 없다 — `selected_kind='ollama'` 가 기본/무자격 경로이며 `compatible_*` DPAPI 바인딩 컬럼과 완전히 분리된다.
- 신규 관리자 라우트: `/api/v1/admin/ai-provider/{config,test,activate,selection,rotate,credential,reconcile}`. 조회는 `admin.ai.read`, mutation 은 `admin.ai.manage` 를 요구하며 CSRF·no-store 계약을 조합한다.

## 4. 검증 계획 (미실행 — pending)

> 아래 항목은 실행 계획이며, 이 보고서 작성 시점에는 **아직 실행되지 않았다**. 리더가 구현 병합 후 실제 수치로 이 절을 갱신한다.

| 구분 | 명령/절차 | 상태 |
|---|---|---|
| backend 회귀 | `cd backend && .venv\Scripts\python.exe -m pytest tests -q` | pending |
| backend 정적 | ruff, basedpyright, compileall(변경 Python) | pending |
| frontend 타입 | `cd frontend && npm run typecheck` | pending |
| frontend 단위 | `cd frontend && npm test` | pending |
| frontend 빌드 | `cd frontend && npm run build` | pending |
| alembic | `20260714_0011_ai_provider_and_launchers` upgrade/downgrade 확인 | pending |
| 브라우저 스모크 | Open WebUI 카드 새 탭 오픈(8080), 관리자 provider 등록/활성화/회전/폐기 UX, 권한 없는 계정에서 카드/메뉴 비노출 | pending |
| 보안 계약 확인 | provider 키 API 응답 평문 미노출, 비-allowlist 대상 enrollment 거부, mutation CSRF 401/403, no-store 헤더 | pending |
| 오프라인 패키지 | `scripts\build_offline_package.ps1` dry-run, `packaging/verify_offline_package.py` | pending |

이 보고서는 어떤 수치도 미실행 상태로 기재하며, 실행하지 않은 검증을 "통과"로 표기하지 않는다.

## 5. Korean PR/릴리즈 제약

- 저장소 [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §2, §3 규칙에 따라 이 minor 릴리즈의 PR 제목·본문은 한국어로 작성하며, 변경 배경/핵심 수정 사항/검증 결과/영향 범위·후속 작업 절을 포함해야 한다.
- 머지 커밋도 한국어 제목 + 한국어 본문 + Lore protocol trailer 를 따른다. 자기 PR 자기 승인이 제한되므로 검증 결과 절을 충분히 채워 셀프 머지 근거를 남긴다.
- `auth`/`csrf`/`cookie`/`cors`/`storage` 정적 노출에 영향을 주는 변경이므로 PR 본문에 위협 모델 변화(본 보고서 §2)를 한 단락으로 요약해 포함한다.
- 이 문서의 ralplan/합의 receipt SHA 는 리더가 최종 diff 확정 후 실제 병합 커밋 SHA 와 함께 재확인한다.

## 6. 비범위

- Open WebUI 자체 인증·RBAC·데이터는 AeroOne 이 관리하지 않는다. 링크만 제공하며 세션/권한은 Open WebUI 자체 설정을 따른다.
- 기존 `ai.use`(AI 대화 사용) 권한 범위는 이번 변경으로 넓어지지 않는다.
- Ollama ↔ OpenAI 호환 provider 간 자동 장애조치(auto-failover)는 명시적으로 제공하지 않는다(요구사항상 fail-closed, no-fallback).
- provider 키의 교차 Windows 프로필/교차 기기 복구는 제공하지 않는다(§2 DPAPI 신원 이동 참고).

## 7. 후속 후보

- provider 응답 지연/오류에 대한 관리자 대시보드 상태 카드(운영 가시성) 추가 검토.
- Open WebUI 헬스 상태를 same-origin 프록시 없이 안전하게 힌트만 주는 방법(예: 마지막 성공 접속 시각 표시) 검토.
