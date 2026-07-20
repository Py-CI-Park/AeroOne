# Aero Work × OpenAI API 사용 가능성 재검토 (폐쇄망)

- 작성일: 2026-07-20 (1.19.0-dev)
- 질문: "AeroOne 에 등록한 Ollama 모델 말고, **OpenAI API 주소와 키**로 Aero Work 를 쓸 수 있는가?" (운영자 폐쇄망에서 OpenAI 사용 예정)
- 방식: 코드 실측(provider 디스패치·egress 정책·임베딩 경로)

---

## 결론 요약

| 기능 | OpenAI 호환 API(base_url+key) 사용 | 상태 |
|---|---|---|
| **업무대화·문서 생성·요약·분류(chat 계열)** | ✅ **이미 가능** | admin LLM 연결 등록·선택 + Aero Work 프로필 `default` |
| **지식폴더 벡터(의미) 검색·색인(embeddings)** | ❌ **현재 Ollama 전용** | OpenAI `/v1/embeddings` 경로 없음 → **1.19.0에서 구현** |
| **지식폴더 키워드 검색(FTS5)** | ✅ 임베딩 불필요 | AI provider 무관하게 동작 |

**요지**: 대화·문서·요약·분류는 이미 OpenAI 호환 API 로 동작한다(아래 §1 설정만 하면 됨). **유일한 갭은 지식폴더 임베딩**이며, 1.19.0-dev 에서 OpenAI 임베딩 경로를 추가한다(§3).

---

## 1. Chat 계열 — 이미 OpenAI 호환 지원 (설정만 필요)

Aero Work 의 업무대화·문서 생성·요약·분류·오케스트레이터 합성은 전부 `AiChatService(settings, db, ProviderConfigService)` 를 경유한다(`document_composer.py`·`intent_router.py`·`streaming.py`·`orchestrator_service.py`). 이 서비스는:

- `_is_compatible_selected()` → provider 선택이 `openai_compatible` 이면 `_compatible_chat()` 로 분기 (`ai/service.py:533`).
- `_compatible_chat()` 는 admin 이 등록한 활성 바인딩(`load_active_compatible_binding()`)의 **base_url + model + api_key** 로 `chat_completion()`(SSRF 핀닝 egress 경유) 호출 (`ai/service.py:428-466`).

**설정 절차(운영자):**
1. 관리자 콘솔 → **LLM 연결**(`admin-llm-connections-card`) → OpenAI 호환 엔드포인트 **base_url + api_key** 등록 → `/v1/models` 검증.
2. 해당 연결을 **활성 provider 로 선택**(`set_selection` → `selected_kind=openai_compatible`).
3. Aero Work **환경설정** → LLM 프로필을 **`default`**(=관리자 선택 provider 따름)로 둔다. `local` 로 두면 Ollama 를 강제하므로 OpenAI 로 안 감.
4. **egress 허용**: 폐쇄망 기본 egress 는 loopback 전용(`ai_compatible_allowed_cidrs=127.0.0.1/32,::1/128`). 내부 OpenAI 게이트웨이(예: `10.x.x.x`)나 특정 호스트를 쓰려면 `backend/.env` 에 허용을 추가한다:
   ```
   AI_COMPATIBLE_ALLOWED_CIDRS=127.0.0.1/32,::1/128,10.0.0.0/8
   AI_COMPATIBLE_ALLOWED_HOSTNAMES=llm.internal.example
   AI_COMPATIBLE_ALLOWED_PORTS=443,80,8080,8000,11434,1234
   ```
   > 폐쇄망 순도상 기본은 loopback 만 허용한다. OpenAI(사내 게이트웨이 포함)를 쓰려면 그 대상만 명시 허용하는 것이 안전 경계다. 실제 `api.openai.com`(공인망) 사용은 폐쇄망이 아니라 인터넷 egress 가 필요하다.

---

## 2. Embeddings — 현재 Ollama 전용 (갭)

지식폴더 색인·의미검색은 `KnowledgeService(db, OllamaEmbedder(settings))` 로 **Ollama `/api/embeddings`(nomic-embed-text)** 만 호출한다(`api.py:86,149` · `embedding_client.py`). OpenAI `/v1/embeddings` 경로가 없다.

- 결과: **Ollama 없이 OpenAI 만으로는 지식폴더 의미검색·근거 답변이 동작하지 않는다**(키워드 FTS5 검색은 됨).
- 단, `KnowledgeService` 의 embedder 는 **주입식(duck-typed)** 이라 동일 인터페이스(`.embed()`/`.embed_one()`/`.model`)의 OpenAI 임베더로 교체 가능하다 — 구조는 이미 열려 있다.

---

## 3. 1.19.0 구현 계획 — OpenAI 임베딩 지원

1. `ai/egress_transport.py` 에 `embeddings()` 추가 — `chat_completion()` 과 동형(SSRF 핀닝 `_execute` 재사용), `POST /v1/embeddings {model, input}` → `data[].embedding` 파싱.
2. `config.py` 에 `ai_compatible_embed_model`(기본 `text-embedding-3-small`) 추가.
3. `aero_work/embedding_client.py` 에 `CompatibleEmbedder`(활성 바인딩 base_url+key + embed model) + `build_embedder(settings, db)` 팩토리 — provider 선택이 `openai_compatible` 면 OpenAI 임베더, 아니면 Ollama.
4. **차원 불일치 가드**: Ollama(768d) ↔ OpenAI(1536d) 벡터는 호환 불가 → 청크별 `embed_model` 을 저장하고, 활성 임베더와 다른 모델로 색인된 폴더는 **"현재 AI provider 로 재색인 필요"** 로 표시(무증상 혼합 금지).
5. `api.py` 임베더 주입부를 `build_embedder(settings, db)` 로 교체.
6. 테스트(스텁 egress)·문서(폐쇄망 OpenAI 설정 가이드).

---

## 4. 운영자 요약 (폐쇄망 OpenAI 사용)

- **지금(1.18.0)**: 대화·문서·요약·분류는 관리자 LLM 연결(OpenAI 호환) 등록+선택+프로필 default 로 **바로 사용 가능**. 지식폴더 의미검색만 Ollama 필요.
- **1.19.0 이후**: 지식폴더 임베딩도 OpenAI `/v1/embeddings` 로 전환 가능(embed 모델 설정). Ollama 완전 미사용 가능(단, provider 전환 시 지식폴더 재색인 필요).
