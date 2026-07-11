# LLM 연결(AI 연결) 설정 운영 런북

> AeroOne 의 AI 보조는 **관리자가 시스템 설정에서 등록하는 OpenAI 호환 엔드포인트 하나**로
> 단일화된다. 관리자가 `base_url` + `api_key` 를 등록하면 `/v1/models` 로 모델 목록을 확인하고,
> `/v1/chat/completions` 로 호출한다. **키는 서버에만 암호화 저장**하고, 응답과 감사기록에는
> 마스킹 값만 나간다(브라우저에 평문 노출 0).
>
> Ollama(`http://127.0.0.1:11434/v1`)와 외부 gpt-oss 계열을 **같은 방식**으로 커버한다. 이
> 레지스트리는 office-tools(보고서/차트/다이어그램)의 AI 보조가 우선 사용한다.

---

## 0. 결론 먼저

- 관리자 콘솔 **시스템 탭의 'AI 연결' 카드**에서 연결을 등록/수정/삭제/검증/기본 지정한다
  (`frontend/components/admin/sections/admin-llm-connections-card.tsx`).
- 백엔드 API 는 `/api/v1/admin/llm-connections*` 이며, **읽기 = `admin.ai.read`**, **변경 =
  `admin.ai.manage` + CSRF** 로 게이트하고 모든 변경을 감사기록에 남긴다.
- 활성 기본 연결은 **최대 1개**(`is_enabled AND is_default`)다. office-tools 는 이 활성 연결을
  써서 AI 보조를 수행하고, 없으면 규칙 기반 폴백으로 내려간다.
- API 키는 `llm_crypto`(stdlib HMAC 스트림 + Encrypt-then-MAC)로 암호화하며 키 원천은
  `settings.jwt_secret_key` 다. **시크릿을 회전하면 기존 토큰은 복호 불가**가 되어 연결을 재등록
  해야 한다.

---

## 1. 데이터 모델

`llm_connections` 테이블(마이그레이션 `backend/alembic/versions/20260711_0009_llm_connections.py`,
모델 `backend/app/modules/ai/models.py` `LlmConnection`).

| 컬럼 | 의미 |
|---|---|
| `name` | 표시 이름(필수, 1~120자) |
| `base_url` | OpenAI 호환 base URL. **http/https 스킴만 허용**(내부망 IP/도메인 통과) |
| `api_key_encrypted` | 암호화된 키(`v1:` 토큰). 평문 저장·응답 반환 금지 |
| `default_model` | 기본 모델명(`/chat/completions` 의 `model`) |
| `is_enabled` | 활성 여부(기본 true) |
| `is_default` | 기본 연결(활성 기본 1개 유일, 서비스 `set_default` 가 보장) |
| `verify_tls` | TLS 검증(기본 true). false 는 폐쇄망 사설 인증서 대응 |

---

## 2. API

| 메서드 | 경로 | 권한 | 용도 |
|---|---|---|---|
| GET | `/api/v1/admin/llm-connections` | `admin.ai.read` | 목록(마스킹 키만) |
| POST | `/api/v1/admin/llm-connections` | `admin.ai.manage` + CSRF | 등록 |
| PATCH | `/api/v1/admin/llm-connections/{id}` | `admin.ai.manage` + CSRF | 수정(키 미전송 시 기존 유지) |
| DELETE | `/api/v1/admin/llm-connections/{id}` | `admin.ai.manage` + CSRF | 삭제 |
| POST | `/api/v1/admin/llm-connections/{id}/default` | `admin.ai.manage` + CSRF | 기본 지정(다른 행 기본 해제) |
| POST | `/api/v1/admin/llm-connections/{id}/verify` | `admin.ai.manage` + CSRF | `/v1/models` 호출 검증(모델 목록 반환) |
| GET | `/api/v1/admin/llm-connections/{id}/models` | `admin.ai.read` | 모델 목록 재조회 |

- 라우터는 `main.py` 에서 `/api/v1/admin` prefix 로 등록(기존 admin same-origin 프록시 재사용).
  브라우저는 `/api/frontend/admin/llm-connections*` 로 호출한다.
- 응답 DTO(`LlmConnectionResponse`)에는 `api_key_masked`(앞 3자 + `...` + 뒤 4자, 8자 미만은
  `****`)만 담기고 `base_url` 은 노출하되 **평문 키는 어디에도 없다**. 감사 스냅샷도 마스킹
  값만 기록하며 `audit._redact` 가 `api_key` 포함 키를 한 번 더 REDACT 한다.

---

## 3. 등록 절차 (관리자)

1. 관리자 계정으로 로그인 후 `/admin` → **시스템** 탭 → **AI 연결** 카드로 이동한다.
2. **새 연결 추가**:
   - 이름(예: `사내 gpt-oss`, `로컬 Ollama`)
   - base_url
     - 로컬 Ollama: `http://127.0.0.1:11434/v1`
     - 외부 OpenAI 호환: 사내에서 제공하는 `http(s)://<host>:<port>/v1`
   - API Key(키가 필요 없는 Ollama 는 비워둔다 — `Authorization` 헤더가 생략된다)
   - 기본 모델명(비우면 `/verify` 로 목록을 먼저 확인 후 지정)
   - TLS 검증(사설 인증서면 해제)
3. **검증**: `verify` 를 눌러 `/v1/models` 응답의 `data[].id` 목록이 뜨는지 확인한다. 실패하면
   `ok=false` + 사유(`detail`)가 표시된다(연결 다운/HTTP 오류/빈 응답).
4. 목록에서 사용할 모델을 **기본 모델**로 지정하고, 이 연결을 **기본 연결**로 설정한다.
5. 이후 office-tools 의 AI 보조와 `capabilities.llm.active` 가 이 활성 연결을 사용한다.

---

## 4. 보안 규칙

- **키는 서버에만**: 등록 즉시 `llm_crypto.encrypt` 로 암호화(`v1:` 토큰). 복호화는 서버가
  호출 직전에만 하고, 프런트/감사/로그에는 마스킹 값만 나간다.
- **입력 검증**: `base_url` 은 http/https 스킴만 허용(파일/기타 스킴 거부, `LlmConnectionCreate`
  의 `field_validator`). 이름 공백 거부.
- **권한 분리**: 읽기(`admin.ai.read`)와 변경(`admin.ai.manage`)을 분리하고, 변경은 CSRF 토큰을
  요구한다. `admin.ai.read` 는 기존에 존재, `admin.ai.manage` 를 변경 권한으로 사용한다.
- **추론 필드 비노출**: `OpenAiCompatibleClient.chat` 은 `choices[0].message.content` 만 반환하고
  reasoning/chain-of-thought 필드는 절대 반환하지 않는다.
- **감사기록**: create/update/delete/set_default/verify 가 모두 `record_admin_audit` 로 남으며,
  before/after 스냅샷에도 평문 키가 없다.

---

## 5. 시크릿 회전 시 주의 (운영자 검증 필요)

- 키 암호화의 원천은 `settings.jwt_secret_key`(production/closed_network 은 config 가 ≥32자
  강제)다.
- **`jwt_secret_key` 를 바꾸면 기존 `api_key_encrypted` 토큰은 복호 불가**가 된다
  (`llm_crypto.decrypt` 가 MAC 검증 실패로 `ValueError`). 이 경우 목록의 마스킹 키는 `****` 로
  퇴화하고 실제 호출이 실패한다.
- 조치: 시크릿 회전 후 **각 LLM 연결을 재등록(또는 키만 PATCH 로 재입력)** 한다.

---

## 6. 회귀 테스트

| 테스트 파일 | 건수 | 다루는 영역 |
|---|---|---|
| `backend/tests/unit/test_llm_crypto.py` | 7 | encrypt/decrypt 왕복, 변조/잘림/잘못된 키 ValueError, mask 규칙 |
| `backend/tests/unit/test_llm_connection_service.py` | 9 | CRUD, set_default 유일성, get_active 우선순위, 키 암·복호화 |
| `backend/tests/unit/test_llm_connections_api.py` | 11 | 권한/CSRF 게이트, 마스킹 응답, verify, 감사기록 redaction |
| `frontend/tests/components/admin-llm-connections.test.tsx` | 3 | AI 연결 카드 렌더/등록/검증 UX |

최종 게이트: backend `pytest tests` = 356 passed / 2 failed(사전 실패 2건, 새 회귀 0).
frontend Vitest = 336 passed(72 files). `tsc --noEmit` 통과. `next build` 성공.

---

## 7. 운영자 검증 필요 (실배포 전)

- [ ] `alembic upgrade head` 로 `20260711_0009` 반영(`llm_connections` 테이블 생성).
- [ ] `admin.ai.manage` 권한이 운영 관리자 역할에 포함되는지 확인.
- [ ] 실 LLM 엔드포인트(사내 gpt-oss 또는 로컬 Ollama)의 base_url/키로 연결 1건 등록 후
      `verify` 로 `/v1/models` 응답 실측.
- [ ] TLS 사설 인증서 환경이면 `verify_tls` 해제 필요 여부 확인.
- [ ] `jwt_secret_key` 회전 정책과 연결 재등록 절차를 운영 문서에 반영.

---

## 관련 문서

- 오피스 도구(AI 보조 소비자): [`office-tools.md`](office-tools.md)
- 관리자 RBAC/감사: [`admin-auth.md`](admin-auth.md)
- 폐쇄망 종합 가이드: [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md)
