# 단계 15 — Open WebUI 참조 기능 연구 보고서

- 분류: **research / next minor 후보 (`1.5.x` 또는 `1.6.0`)**
- 참조 프로젝트: `D:\Chanil_Park\Project\Programming\open-webui`
- 목적: AeroOne 의 폐쇄망 Ollama AI 기능을 단순 채팅에서 **업무형 AI 콘솔**로 발전시킬 때 참고할 기능을 선별한다.
- 범위: 기능·정보구조·운영 정책 연구. Open WebUI 코드/브랜딩을 복사하지 않고, AeroOne 의 폐쇄망·same-origin·문서 열람 원칙에 맞게 재설계한다.

---

## 1. 요약 결론

Open WebUI 는 단순 Ollama 채팅 UI가 아니라 **채팅 기록, 계정/권한, 지식베이스, 관리자 설정, 평가/분석, 모델·연결 관리**를 갖춘 AI 운영 플랫폼이다. AeroOne 에 바로 필요한 것은 Open WebUI 전체 복제가 아니라, 폐쇄망 문서 시스템에 맞는 다음 4가지 축이다.

| 축 | AeroOne 에 필요한 이유 | 추천 |
|---|---|---|
| 채팅 기록 | 현재 `/ai` 는 대화가 화면 상태에만 머물러 업무 검토 이력이 남지 않는다. | **최우선**: 대화 저장·목록·검색·삭제·핀·보관 |
| 관리자 AI 설정 | `backend/.env` 수정 없이 Ollama URL/model/상태를 운영자가 확인해야 한다. | **최우선**: 관리자 AI 설정 탭 + 연결 테스트 |
| 문서 근거/지식 세트 | `_database` HTML 검색은 있지만 “어떤 문서 묶음으로 답하게 할지”가 아직 약하다. | **우선**: 저장된 문서 컬렉션/프리셋/인용 패널 |
| 사용/품질 관찰 | AI 답변 품질, 응답 시간, 실패 원인을 추적해야 폐쇄망 운영에서 원인 분석이 된다. | **우선**: 사용 통계·피드백·오류 로그 |

반대로 Open WebUI 의 web search, 이미지 생성, 음성/영상 통화, 플러그인/코드 실행, SCIM/OAuth 대형 엔터프라이즈 인증은 현재 AeroOne 의 폐쇄망 문서 열람 목적에는 과하다. 후순위 또는 제외가 맞다.

---

## 2. 참조한 Open WebUI 영역

| 영역 | 참조 파일/경로 | 관찰한 기능 |
|---|---|---|
| 전체 기능 개요 | `open-webui/README.md` | Ollama/OpenAI 통합, RBAC, RAG, 모델 빌더, 함수 호출, 분석, LDAP/SSO, PWA 등 |
| 채팅 저장 모델 | `backend/open_webui/models/chats.py` | chat JSON, title, share_id, archived, pinned, folder_id, summary, last_read_at, usage stats |
| 채팅 API | `backend/open_webui/routers/chats.py`, `src/lib/apis/chats/index.ts` | 생성·목록·검색·폴더·핀·보관·공유·복제·태그·삭제·통계 export |
| 계정/인증 | `backend/open_webui/models/users.py`, `backend/open_webui/routers/auths.py`, `routers/users.py` | 역할(`pending/user/admin`), 사용자 설정, API key, LDAP, 관리자 추가/수정/삭제, 기본 권한 |
| 관리자 설정 | `src/lib/components/admin/Settings.svelte` | General, Connections, Models, Documents, Web Search, Code Execution, Interface, Audio, Images, DB |
| RAG/지식베이스 | `backend/open_webui/routers/retrieval.py`, `models/knowledge.py`, `src/lib/components/workspace/Knowledge/` | 파일/텍스트/웹 처리, collection query, batch ingest, knowledge directory, access grants |
| 채팅 UI | `src/lib/components/chat/Chat.svelte`, `MessageInput.svelte`, `ChatControls.svelte` | stop/regenerate, files, system prompt, advanced params, temporary chat, model selector, web/knowledge/tools |
| 사이드바/정리 | `src/lib/components/layout/Sidebar/*` | 채팅 목록, 폴더, 검색, pinned models/chats, user menu |
| 평가/분석 | `src/lib/components/admin/Evaluations/*`, `Analytics/*` | feedback, leaderboard, model/user usage dashboard |

---

## 3. Open WebUI 기능군별 분석과 AeroOne 반영 판단

| 기능군 | Open WebUI 방식 | AeroOne 적용 판단 | 이유 |
|---|---|---|---|
| 채팅 기록 | `chat` 테이블에 대화 JSON, 제목, folder, pinned, archived, summary 저장 | **채택** | 보고서 검토/문서 질문은 업무 이력이 중요하다. |
| 채팅 목록/검색 | sidebar 목록, text search, folder/tag 필터 | **채택** | “지난번 그 질문”을 다시 찾는 기능이 필요하다. |
| 채팅 핀/보관/삭제 | pinned/archived/delete endpoints | **채택** | 업무별 대화 정리 UX가 단순하면서 효과가 크다. |
| 채팅 공유 | share_id/access grants | **부분 채택** | 폐쇄망 내부 공유는 필요하지만 외부 공개 링크는 위험하다. 내부 사용자/역할 기반 공유만 권장. |
| 대화 복제 | 기존 대화 clone | **부분 채택** | 같은 문서 세트로 다른 질문을 시작할 때 유용하다. 단순 “복사해서 새 대화”부터. |
| 제목 자동 생성 | 모델로 title 생성 | **후순위** | gemma4:12b 로 가능하지만 저장 기능 다음 단계. 초기에는 첫 질문 기반 제목이면 충분. |
| 태그/폴더 | chat tag, folder_id | **채택** | 부서/문서분류/보고서 검토별 정리가 가능하다. |
| Temporary chat | 기록 저장 없는 임시 대화 | **채택** | 민감하거나 일회성 질문은 저장하지 않는 선택지가 필요하다. |
| 모델 선택 | 여러 Ollama/OpenAI 모델 선택 | **후순위** | 현재 폐쇄망 기본 모델은 gemma4:12b 하나. 단, 관리자 설정 구조는 확장 가능하게. |
| 관리자 연결 설정 | Ollama/OpenAI URL, key, proxy | **채택** | `.env` 직접 수정보다 운영자 UI에서 상태 확인/테스트가 필요하다. |
| 사용자 계정/RBAC | pending/user/admin, group permissions | **부분 채택** | AeroOne 은 현재 단일 관리자 중심. AI 기록을 개인별로 나누려면 최소 user/admin부터 도입. |
| API key | 개인 API key 생성/삭제 | **보류** | 외부 API 소비 제품이 아니므로 현재 필요 낮음. |
| LDAP/SSO/SCIM | 엔터프라이즈 계정 연동 | **제외/장기** | 폐쇄망 단일 PC/소규모 운영에는 과함. |
| Knowledge base | 파일/텍스트/디렉터리/권한 | **부분 채택** | AeroOne 은 `_database` 가 원천이다. 업로드형 지식베이스보다 “저장된 검색 범위/문서 묶음”이 먼저. |
| Vector RAG | embedding, vector DB, chunking | **후순위** | SQLite FTS5 로 이미 본문 검색이 된다. 의미 검색은 품질 요구가 확인된 뒤 ADR 필요. |
| Web search | 다수 provider | **제외** | 폐쇄망 원칙과 충돌. 내부 문서 검색만 유지. |
| 파일 업로드 채팅 | chat file attach | **부분 채택** | 폐쇄망에서 임시 PDF/HTML 검토에는 유용. 단, import 루트와 저장/삭제 정책 설계 필요. |
| Prompt presets | workspace prompts, suggestions | **채택** | 보고서 검토, 요약, 위험 식별, 비교 등 버튼형 프롬프트가 AeroOne 업무에 잘 맞다. |
| System prompt/advanced params | UI에서 system prompt, temperature 등 제어 | **부분 채택** | 일반 사용자에게 노출하면 혼란. 관리자/고급 옵션으로 제한. |
| Stop/regenerate/copy | 생성 중단, 재생성, 복사 | **채택** | 채팅 기본 사용성. 현재 AeroOne 은 대기 표시만 있으므로 다음 개선 대상. |
| Feedback/evaluation | 메시지 rating, leaderboard | **부분 채택** | 별점/좋아요/문제 신고 정도부터 시작. 리더보드는 불필요. |
| Analytics | user/model usage, response time | **채택** | Ollama 장애, 느린 응답, 사용량 추적에 필요. |
| Voice/video | STT/TTS, call overlay | **제외** | 현재 요구와 무관하고 폐쇄망 장비 편차가 큼. |
| Image generation | DALL-E/ComfyUI 등 | **제외** | 뉴스레터·문서 열람 제품 범위 밖. |
| Plugin/tools/code execution | Python functions, tools, code execution | **제외/장기** | 폐쇄망 보안·운영 리스크가 큼. 단순 문서 QA에 필요하지 않다. |
| PWA/mobile | manifest, responsive | **후순위** | LAN 태블릿 사용 요구가 생기면 검토. |

---

## 4. AeroOne 권장 정보구조

Open WebUI 의 좌측 사이드바/관리자 탭 구조를 그대로 가져오면 AeroOne 이 AI 플랫폼처럼 비대해진다. AeroOne 은 뉴스레터·문서 열람이 중심이므로 다음처럼 축소한 정보구조가 적절하다.

| 위치 | 메뉴/화면 | 기능 |
|---|---|---|
| 상단 nav | `AI` | 현재 `/ai` 를 정식 상단 메뉴로 승격할지 검토. 대시보드 카드만으로 부족하면 추가. |
| `/ai` 좌측 | 대화 목록 | 새 대화, 최근 대화, 검색, 핀, 보관, 삭제 |
| `/ai` 중앙 | 채팅 | gemma4:12b 대화, 문서 근거 토글, citation, stop/regenerate/copy |
| `/ai` 우측 | 문서 근거 패널 | 검색 결과, 선택된 문서 묶음, 파일 열기, citation preview |
| `/admin/ai` | AI 운영 설정 | Ollama URL/model, 연결 테스트, timeout/context 길이, AI on/off |
| `/admin/ai/usage` | AI 사용 현황 | 대화 수, 응답 시간, 실패 수, 사용 모델, 최근 오류 |
| `/admin/users` 확장 | 사용자별 AI 권한 | AI 사용 가능 여부, 기록 열람 범위, 관리자 권한 |

---

## 5. 추천 구현 로드맵

### 5.1 최우선(P0) — “업무에 쓸 수 있는 AI 기록”

| 작업 | 내용 | 수용 기준 | 영향 파일 후보 |
|---|---|---|---|
| AI 대화 DB 모델 | `ai_conversations`, `ai_messages` 추가 | 새 대화가 저장되고 새로고침 후 복원됨 | `backend/app/modules/ai/models.py`, Alembic migration |
| 대화 CRUD API | 목록/상세/생성/수정/삭제 | 사용자별 대화 목록, 제목 변경, 삭제 가능 | `backend/app/modules/ai/api/public.py` 또는 `api/admin.py` |
| 채팅 UI 좌측 목록 | `/ai` 에 최근 대화 목록 | 새 대화/이전 대화 전환 가능 | `frontend/components/ai/` |
| 핀/보관 | pinned/archived 필드 | 중요한 대화 고정, 숨김 처리 가능 | backend + UI |
| 임시 대화 | 저장하지 않는 체크/버튼 | temporary on이면 DB 저장 없음 | backend request flag + UI |

### 5.2 우선(P1) — “관리자가 운영할 수 있는 AI”

| 작업 | 내용 | 수용 기준 | 영향 파일 후보 |
|---|---|---|---|
| 관리자 AI 설정 화면 | Ollama URL/model/timeout/status | `.env` 열지 않고 상태 확인 가능 | `frontend/app/admin/ai`, backend admin route |
| 연결 테스트 | `/api/v1/ai/status` 를 관리자 화면에서 실행 | reachable/model_available/detail 표시 | existing AI service 재사용 |
| 모델 목록 조회 | Ollama `/api/tags` 결과 표시 | gemma4:12b 존재 여부와 후보 모델 확인 | `OllamaClient.list_models()` 확장 |
| 사용량/오류 로그 | 요청 시간, 성공/실패, 모델 기록 | 최근 실패 원인을 관리자 화면에서 확인 | `ai_request_logs` 테이블 또는 기존 로깅 |

### 5.3 우선(P1) — “문서 근거 품질 개선”

| 작업 | 내용 | 수용 기준 | 영향 파일 후보 |
|---|---|---|---|
| 문서 묶음 프리셋 | document/civil/nsa 또는 폴더 단위 저장 범위 | “항공”, “민간항공기”, “NSA” 같은 범위 선택 | collections service + AI UI |
| citation 패널 | 답변 아래 출처를 우측 패널과 연결 | citation 클릭 시 해당 HTML 열림 | `ai-chat-workspace.tsx` |
| 보고서 검토 프롬프트 | 요약/오류찾기/비교/리스크 식별 버튼 | 버튼 클릭 시 표준 프롬프트 입력 | prompt preset config |
| 검색 결과 선택 후 질문 | 검색 결과 몇 개를 체크해 질문 근거로 사용 | 선택된 문서만 context 로 전송 | frontend state + chat request schema |

### 5.4 후순위(P2) — “품질/협업”

| 작업 | 내용 | 이유 |
|---|---|---|
| 메시지 평가 | 👍/👎, 문제 신고 | 답변 품질 개선과 운영 판단 근거 |
| 대화 export | Markdown/JSON 저장 | 보고서 검토 결과 보존 |
| 대화 공유 | 내부 사용자에게 읽기 공유 | 다중 계정 도입 후 의미 있음 |
| 요약/제목 자동 생성 | 대화 title/summary 자동 생성 | 대화 수가 많아진 뒤 필요 |
| embedding 의미 검색 | FTS 한계를 넘는 의미 검색 | 문서량/품질 요구 확인 후 별도 ADR |

---

## 6. 계정/권한 제안

Open WebUI 는 `pending/user/admin` 과 group permission 을 폭넓게 사용한다. AeroOne 은 현재 단일 관리자 중심이므로 처음부터 LDAP/SCIM/OAuth 까지 가면 과하다. 다음 순서가 안전하다.

| 단계 | 기능 | 설명 |
|---|---|---|
| 1 | `admin` + `user` | 관리자와 일반 사용자 2역할. 일반 사용자는 AI 채팅과 공개 문서만 사용. |
| 2 | 사용자별 AI 기록 | 각 사용자 자신의 대화만 목록/삭제. 관리자는 사용량만 보고 본문은 기본 비공개. |
| 3 | 권한 플래그 | `can_use_ai`, `can_use_nsa_context`, `can_export_chat` 정도만 도입. |
| 4 | 그룹 | 부서별 문서 묶음 공유 요구가 생기면 group 도입. |
| 장기 | LDAP/SSO | 폐쇄망 AD 연동 요구가 명확할 때만 별도 계획. |

보안 원칙: AI 대화에는 문서 일부와 질문이 함께 저장되므로, 뉴스레터 읽음 추적보다 더 민감하게 취급한다. 관리자라고 해도 사용자 대화 본문 전체를 기본 열람하게 만들면 사내 신뢰 문제가 생긴다. 초기 설계는 “관리자는 운영 통계, 본문 열람은 본인 또는 명시 공유만”이 낫다.

---

## 7. 관리자 메뉴 제안

| 관리자 메뉴 | 필드/기능 | Open WebUI 참조 | AeroOne 적용 방식 |
|---|---|---|---|
| AI 연결 | enabled, Ollama URL, model, timeout, 연결 테스트 | Connections / Models | 단일 Ollama 우선. OpenAI 호환 API는 후순위. |
| AI 문서 근거 | 기본 collection, context chars, max citations, NSA 포함 여부 | Documents / RAG | `_database` 컬렉션 정책과 연결. |
| AI 프롬프트 | 기본 system prompt, 보고서 검토 preset | Prompts / Interface | 관리자만 편집, 일반 사용자는 선택만. |
| AI 사용 현황 | 요청 수, 실패 수, 평균 응답 시간, 모델 상태 | Analytics | 폐쇄망 장애 분석용 최소 지표. |
| AI 품질 피드백 | thumbs up/down, 신고 사유 | Evaluations | leaderboard 없이 문제 답변 수집. |
| 사용자 권한 | AI 사용 가능, NSA 근거 사용 가능, export 가능 | Users / Permissions | 단순 플래그부터 시작. |

---

## 8. 채팅 GUI 세부 추천

| UI 기능 | 추천 | 이유 |
|---|---|---|
| 왼쪽 대화 목록 | 채택 | OpenWebUI 의 가장 큰 사용성 요소. 대화가 쌓이면 필수. |
| 새 채팅 버튼 | 채택 | 현재 화면 상태 초기화보다 명확하다. |
| 검색창 | 채택 | 대화 제목/본문 검색. |
| 핀/보관 | 채택 | 중요 대화와 오래된 대화를 분리. |
| Stop 버튼 | 채택 | 로컬 LLM 응답이 길 때 필요. backend 에 request cancel/task id 설계 필요. |
| Regenerate | 채택 | 같은 문서 근거로 재답변 요청. |
| Copy | 채택 | 보고서/메일 작성에 바로 사용. |
| Citation card | 채택 | 답변 신뢰성 확보. 파일 열기 deep-link 포함. |
| Context selector | 채택 | document/civil/nsa/선택 파일/검색 결과를 사용자가 명시. |
| System prompt 편집 | 관리자/고급만 | 일반 사용자에게 노출하면 품질이 흔들림. |
| 모델 선택 | 후순위 | 기본 gemma4:12b 단일 모델이면 불필요. |
| 음성 입력 | 제외 | 현재 폐쇄망 업무 우선순위 낮음. |

---

## 9. 데이터 모델 초안

AeroOne 에 맞춘 최소 모델은 Open WebUI 의 `chat` JSON 전체 저장 방식보다 명시 테이블이 낫다. 통계/검색/삭제/권한 처리가 단순해진다.

| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `ai_conversations` | `id`, `user_id`, `title`, `pinned`, `archived`, `temporary`, `created_at`, `updated_at`, `last_message_at`, `default_collections` | 대화 단위 메타데이터 |
| `ai_messages` | `id`, `conversation_id`, `role`, `content`, `model`, `latency_ms`, `created_at`, `error_code` | 사용자/AI 메시지 |
| `ai_message_citations` | `id`, `message_id`, `collection`, `path`, `snippet`, `navigation_url` | 답변 출처 |
| `ai_presets` | `id`, `name`, `prompt`, `default_collections`, `is_active` | 보고서 검토/요약 등 프롬프트 버튼 |
| `ai_request_logs` | `id`, `user_id`, `conversation_id`, `model`, `status`, `latency_ms`, `detail`, `created_at` | 운영 통계/장애 분석 |
| `ai_user_permissions` 또는 users 확장 | `can_use_ai`, `can_use_nsa_context`, `can_export_chat` | 단순 권한 플래그 |

---

## 10. 제외/보류해야 할 기능

| 기능 | 결정 | 이유 |
|---|---|---|
| 외부 Web Search | 제외 | 폐쇄망 원칙과 맞지 않음. |
| 이미지 생성/편집 | 제외 | AeroOne 의 뉴스레터·문서 열람 목적 밖. |
| 음성/영상 통화 | 제외 | 장비/브라우저/보안 변수가 크다. |
| Python tools/code execution | 제외 | 폐쇄망 PC에서 임의 코드 실행 표면이 생긴다. |
| 플러그인 마켓/커뮤니티 import | 제외 | 폐쇄망 재현성과 검증 가능성을 해친다. |
| SCIM/OAuth/LDAP | 장기 보류 | 사내 AD 연동 요구가 명확할 때 별도 보안 계획 필요. |
| 다중 vector DB | 보류 | SQLite FTS5 로 충분한지 운영 데이터로 먼저 판단. |
| 다중 모델 병렬 대화 | 보류 | 기본 모델 gemma4:12b 단일 운영을 먼저 안정화. |

---

## 11. 추천 실행 순서

| 순서 | 단위 | 산출물 | 검증 |
|---:|---|---|---|
| 1 | AI 대화 저장 | DB migration + conversation/message API | backend CRUD/integration tests |
| 2 | AI 좌측 대화 목록 | `/ai` sidebar, 새 대화/이전 대화/삭제 | frontend component tests + browser flow |
| 3 | 채팅 기본 UX | stop/copy/regenerate, pending 상태 강화 | mocked route tests + 실제 Ollama smoke |
| 4 | 관리자 AI 설정 | `/admin/ai` 연결 테스트/모델 확인 | admin auth tests + settings tests |
| 5 | 문서 근거 프리셋 | 검색 결과 선택, preset prompt | AI citation tests + browser flow |
| 6 | 사용량/피드백 | logs, thumbs up/down, admin summary | analytics API tests |

---

## 12. 최종 권고

다음 구현은 “Open WebUI 처럼 보이는 대형 AI 플랫폼”이 아니라 **AeroOne 문서 업무에 맞는 경량 OpenWebUI식 채팅 기록/관리 구조**가 되어야 한다. 1.5에서 이미 확보한 same-origin AI proxy, backend-only Ollama, FTS5 본문 검색을 유지하면서 다음 단계는 아래 3개를 먼저 진행하는 것이 가장 효과적이다.

1. **AI 대화 저장과 목록** — 업무 이력을 남기는 핵심.
2. **관리자 AI 설정/상태 화면** — 폐쇄망 운영자가 `.env` 없이 진단 가능.
3. **문서 근거 프리셋 + citation 패널** — AeroOne 고유 강점인 `_database` 문서 열람과 AI 답변을 결합.

이 3개가 끝난 뒤에 사용자 계정 분리, 피드백/통계, export/share 를 추가하면 Open WebUI 의 장점을 가져오면서도 AeroOne 의 폐쇄망 단순성과 운영 재현성을 유지할 수 있다.

---

## 13. 우선순위 반영 타당성 검토

현재 1.5 개발 상태는 `gemma4:12b` 채팅, same-origin backend proxy, `_database` HTML FTS 검색, citation 응답, `/ai` 화면, 전체 사용법 팝업까지 이미 확보되어 있다. 따라서 Open WebUI 참조 기능을 지금 반영하는 것은 **타당하지만, 전체 복제가 아니라 “대화 이력과 운영 진단” 중심의 제한된 2차 증분**으로 진행해야 한다.

| 후보 | 지금 반영 적절성 | 판단 | 이유 | 권장 범위 |
|---|---|---|---|---|
| AI 대화 저장·목록·삭제 | **높음** | 바로 진행 적절 | 현재 `/ai` 의 가장 큰 한계는 새로고침/이동 시 대화가 사라지는 점이다. DB·API·UI 증분이 명확하고 Open WebUI 참조 효과가 크다. | `ai_conversations`, `ai_messages`, 목록/상세/삭제, 첫 질문 기반 제목 |
| 핀·보관·대화 검색 | **높음** | 대화 저장과 함께 포함 가능 | 컬럼/필터 수준의 확장이라 구현 부담이 작고 업무 이력 정리에 바로 도움이 된다. | pinned, archived, 제목/본문 LIKE 또는 FTS |
| 임시 대화 | **높음** | 함께 포함 권장 | AI 질문에는 민감 내용이 들어갈 수 있으므로 “저장하지 않음” 옵션이 초기부터 있어야 신뢰성이 높다. | temporary 토글이면 DB 미저장 |
| 관리자 AI 연결 상태/모델 확인 | **높음** | 바로 진행 적절 | 폐쇄망에서는 `.env` 직접 수정보다 화면에서 Ollama URL/model/reachable/model_available 을 보는 기능이 운영에 중요하다. | 읽기 중심 `/admin/ai`, 연결 테스트, 모델 목록 |
| 관리자 설정값 DB 저장 | **중간** | 일부 보류 | `.env` 와 DB 설정이 충돌하면 운영 원천이 둘로 갈라진다. 초기에는 읽기/진단 중심이 안전하다. | 1차는 상태 표시, 2차에서 DB override ADR |
| Stop 버튼 | **중간** | 설계 후 진행 | 현재 API 는 동기 `stream:false` 이므로 브라우저 취소만으로 Ollama 작업 중단 보장이 약하다. | AbortController UI 먼저, 서버 취소/streaming 은 별도 |
| Regenerate/Copy | **높음** | UI 개선으로 적절 | 저장된 메시지를 재사용하거나 클립보드 복사하는 기능이라 위험이 낮다. | copy 즉시, regenerate 는 마지막 user 메시지 재호출 |
| 문서 근거 프리셋 | **높음** | 바로 진행 적절 | 이미 document/civil/nsa 검색이 있으므로 사용자 선택 UI와 preset 만 추가하면 된다. | document/civil/nsa/검색결과 선택 |
| 검색 결과 선택 후 질문 | **높음** | P1 초반 적절 | AeroOne 고유 강점이다. 사용자가 근거 문서를 명시하면 답변 신뢰성이 오른다. | selected citations/path 를 chat request context 로 전달 |
| citation 우측 패널 강화 | **높음** | 적절 | 이미 citation 과 파일 열기 URL 이 있으므로 UI 연결 강화가 주 작업이다. | 답변 citation 클릭 → 우측 패널/문서 열기 |
| 프롬프트 preset | **중간~높음** | 작게 시작 적절 | 보고서 검토/요약/위험 식별은 업무 적합성이 높다. 다만 관리자 편집형은 나중이 안전하다. | 코드/DB seed 기반 기본 preset 4~6개 |
| 사용량·오류 로그 | **중간** | 최소 로깅부터 적절 | 운영 진단에 필요하지만 개인정보/대화 본문 저장 정책과 묶인다. | 본문 없는 request log, latency/status/detail |
| 사용자별 권한 | **중간** | 대화 저장 뒤 진행 | 현재 단일 관리자 중심이면 권한 구조를 먼저 크게 벌릴 필요는 없다. 다만 `user_id` 컬럼은 선반영해야 한다. | admin/user 2역할, can_use_ai 정도 |
| 대화 공유/export | **낮음~중간** | 후순위 | 저장·권한 정책이 먼저 안정화되어야 한다. | export 먼저, 공유는 내부 사용자 모델 이후 |
| Vector RAG/embedding | **낮음** | 지금은 부적절 | SQLite FTS5 로 빠른 본문 검색이 이미 작동한다. 의미 검색은 품질 요구가 확인된 뒤 별도 ADR 이 맞다. | 운영 데이터 수집 후 재검토 |
| Open WebUI식 플러그인/코드 실행/API key/SSO | **낮음** | 제외 유지 | 폐쇄망 보안·운영 단순성·검증 가능성과 충돌한다. | 이번 버전 범위 제외 |

### 권장 의사결정

이번 개발선에서 가장 타당한 반영 범위는 **P0 “AI 대화 이력화” + P1 일부 “관리자 진단/문서 근거 UX”** 이다. 구체적으로는 다음 순서가 안전하다.

| 순서 | 반영 항목 | 포함 | 제외 |
|---:|---|---|---|
| 1 | 대화 저장 기반 | conversation/message DB, 목록, 새 대화, 삭제, 핀, 보관, 임시 대화 | 공유, 자동 제목 생성 |
| 2 | 채팅 편의 기능 | copy, regenerate, pending/error 표시 강화 | 완전한 서버-side stop/streaming |
| 3 | 관리자 AI 진단 | Ollama 상태, 모델 목록, timeout/context 현재값 표시, 연결 테스트 | DB 기반 설정 override |
| 4 | 문서 근거 UX | 문서 묶음 preset, 검색 결과 선택 후 질문, citation 패널 강화 | embedding/vector RAG |
| 5 | 최소 운영 로그 | 요청 성공/실패, latency, model, 오류 detail | 대화 본문 관리자 열람, leaderboard |

이 순서는 현재 코드의 same-origin proxy 와 FTS 검색을 그대로 재사용하므로 위험이 낮고, 새로 필요한 것은 주로 DB migration/API/UI 상태 관리다. 반면 관리자 설정 쓰기, 계정/RBAC, vector RAG, streaming 취소는 설계 파급이 커서 다음 승인 단위로 분리하는 것이 맞다.

---

## 14. AI 대화 신원 전략 재검토 — IP 기반 vs 계정 기반

운영자 추가 요청: "Open WebUI 처럼 접속 IP/사용자별로 AI·사용자 기록이 남는 기능이 좋아 보인다. AeroOne 도 IP 기반으로 대화를 기억하거나, 가장 좋은 방식은 Open WebUI 처럼 기록이 필요한 것은 계정으로 유지하게 하자." 이 절은 섹션 6(계정/권한)·섹션 9(데이터 모델)·섹션 13(우선순위) 을 신원(identity) 관점에서 다시 검토한다.

### 14.1 현재 코드의 신원 사실관계

| 항목 | 현재 상태 | 근거 |
|---|---|---|
| `/ai` 채팅 | **완전 무인증** (공개 라우터, 쿠키/로그인 불필요) | `backend/app/main.py:74` (`/api/v1/ai`), `backend/app/modules/ai/api/public.py` |
| 일반 사용자 계정 | **없음** — 로그인/회원가입 흐름 없음 | `backend/app/modules/auth/api.py` 는 `login`/`logout`/`me` 만, 단일 관리자 전제 |
| 인증 주체 | **관리자 1종**뿐 (JWT 쿠키 세션) | `get_current_admin` (`auth/dependencies.py`), `User` 모델 단일 |
| IP 기반 식별 선례 | **이미 있음** — 뉴스레터 읽음추적이 `client_ip` 키로 집계/디바운스 | `NewsletterReadEvent` (`(newsletter_id, client_ip)` unique, `unique_ips`), `_client_ip()` = `request.client.host` |
| 프록시 전제 | 리버스 프록시 없음, `X-Forwarded-For` 미신뢰, `request.client.host` 가 곧 LAN IP | `read_tracking/api/public.py:17-23` |

즉 운영자가 본 "cmd 창/로그에 접속 IP 가 기록과 함께 남는" 모양은 AeroOne 에 이미 부분적으로 존재한다(읽음추적). 다만 **AI 대화에는 신원이 전혀 묶여 있지 않다.** 그래서 IP든 계정이든, AI 대화를 "기억"시키려면 신원 컬럼을 새로 도입해야 한다.

### 14.2 세 가지 신원 모델 비교

| 기준 | A. IP 기반 | B. 계정 기반(Open WebUI식) | C. 하이브리드(IP 기본 + 계정 승격) |
|---|---|---|---|
| 사용자 마찰 | **없음** (로그인 불필요) | 로그인/회원가입 필요 | 기본 없음, 필요 시 로그인 |
| 식별 신뢰성 | **낮음** — DHCP 재할당, NAT/공유 PC, 같은 IP 다수 사용자 | **높음** — 사람 단위 고정 | 중간→높음 (승격 시 고정) |
| 개인정보/민감도 | 대화에 IP 가 박혀 추적 가능, 책임소재 모호 | 대화=사람 매핑 명확, 본인만 열람 설계 가능 | 단계적으로 강화 |
| 구현 부담 | **작음** — 읽음추적 `_client_ip` 패턴 재사용 | **큼** — 회원가입·비밀번호·세션·역할·관리 UI 필요 | 중간 — IP 먼저, 계정은 후속 |
| Open WebUI 일치도 | 낮음 (Open WebUI 는 계정 필수) | **높음** | 높음(최종 상태) |
| 폐쇄망 적합성 | LAN 소규모엔 충분하나 공용 PC 에서 대화 섞임 위험 | 사람별 분리·감사 추적에 가장 적합 | 폐쇄망 점진 도입에 가장 현실적 |

### 14.3 IP 기반만으로는 부족한 이유 (운영자 의도 보정)

운영자 직관(IP 로 기억)은 읽음추적에서 통했기 때문에 합리적이지만, **AI 대화는 읽음추적보다 훨씬 민감**하다(질문 + 문서 일부가 함께 저장됨). IP 단독은 다음 한계가 있다.

- 같은 공용/공유 PC를 여러 사람이 쓰면 **남의 AI 대화가 내 목록에 보인다.**
- DHCP 임대 갱신으로 IP 가 바뀌면 **내 과거 대화를 잃는다.**
- "이 민감한 질문은 누가 했나"를 IP 로만 추적하면 **책임소재가 사람이 아니라 단말**에 머문다.

따라서 운영자의 "가장 좋은 방식은 계정"이라는 판단이 맞다. 다만 폐쇄망 LAN 에서 처음부터 전원 로그인 강제는 마찰이 크므로, **C. 하이브리드**가 가장 타당하다.

### 14.4 권장 결론 — 하이브리드(IP 기본, 계정 승격)

| 단계 | 신원 | 동작 | 산출물 |
|---|---|---|---|
| 1 | **IP 기반 익명 세션** | 무로그인 사용자는 `client_ip`(+서버 발급 익명 세션 토큰 쿠키)로 자기 대화만 목록/이어가기. 읽음추적 `_client_ip` 재사용. | `ai_conversations.owner_ip`, `owner_session_id` (nullable), 익명 세션 쿠키 |
| 2 | **선택적 계정 로그인** | 로그인한 사용자는 `user_id` 로 대화가 묶여 IP/단말이 바뀌어도 유지·본인만 열람. 관리자는 운영 통계만. | `auth` 를 admin 단일 → `admin`/`user` 2역할로 확장, 로그인 UI |
| 3 | **익명→계정 승격(claim)** | 로그인 시 같은 세션/IP 의 익명 대화를 본인 계정으로 귀속(claim)할지 선택. | `claim` 엔드포인트, `owner_ip`→`user_id` 이관 |
| 4 | **운영 로그/감사** | AI 요청 로그에 IP·user_id·model·status·latency 기록(대화 본문 제외). cmd/관리자 화면에서 "누가/어디서 AI 를 썼는가" 확인. | `ai_request_logs.client_ip`, `user_id` |

핵심 설계 원칙:

- **본문 열람은 본인(또는 명시 공유)만.** 관리자라도 IP/계정 무관하게 대화 본문 전체를 기본 열람하지 않는다(섹션 6 보안 원칙 유지).
- **IP 는 보조 식별자**로만 쓰고, 사람 단위 신뢰가 필요한 기록은 `user_id` 를 진실 원천으로 둔다.
- **임시 대화는 어느 신원에도 저장하지 않는다.**
- 프록시 전제(`request.client.host` = LAN IP, `X-Forwarded-For` 미신뢰)는 14.1 그대로 유지하고, 프록시 도입 시 재검토한다(읽음추적과 동일 함정).

### 14.5 데이터 모델 보정 (섹션 9 갱신)

섹션 9 의 `ai_conversations` / `ai_request_logs` 에 신원 컬럼을 다음과 같이 보정한다.

| 테이블 | 추가/변경 컬럼 | 의미 |
|---|---|---|
| `ai_conversations` | `user_id` (nullable), `owner_ip`, `owner_session_id` (nullable) | 로그인=user_id, 익명=owner_ip+session. 둘 중 하나는 항상 채움 |
| `ai_messages` | (변경 없음) | 대화에 종속 |
| `ai_request_logs` | `client_ip`, `user_id` (nullable), `model`, `status`, `latency_ms`, `detail` | 운영/감사용. **대화 본문은 저장하지 않음** |
| `users` 확장 | `role`(`admin`/`user`), `can_use_ai` | 2단계에서 계정 도입 시 |

### 14.6 우선순위 영향 (섹션 13 갱신)

섹션 13 의 1순위 "대화 저장 기반"은 **IP 기반 익명 세션(하이브리드 1단계)으로 곧바로 구현 가능**하다 — 계정 시스템 없이도 `owner_ip`+익명 세션 쿠키로 "내 대화 기억"이 동작한다. 계정 기반(2~3단계)은 auth 를 admin 단일에서 다중 사용자로 확장하는 별도 승인 단위로 분리한다.

| 재배치 | 항목 | 근거 |
|---|---|---|
| **지금(P0)** | IP+익명 세션 대화 저장, 목록, 삭제, 핀, 보관, 임시 대화 | 읽음추적 패턴 재사용으로 위험 낮음, 로그인 마찰 없음 |
| **지금(P0)** | AI 요청 로그(IP·model·status·latency, 본문 제외) | 운영자가 원한 "IP 와 함께 남는 기록" 충족, 민감 본문 회피 |
| **다음(P1)** | `admin`/`user` 2역할 + 로그인 UI + `user_id` 귀속 | 사람 단위 신뢰가 필요해질 때. 설계 파급 큼 |
| **다음(P1)** | 익명→계정 claim, 본인 전용 열람 | 계정 도입 직후 |
| **후순위(P2)** | 그룹/부서 공유, export/share | 다중 계정 안정화 이후 |

결론: 운영자가 원한 "IP 로 대화를 기억" 은 **지금 바로(P0)** 하이브리드 1단계로 반영하는 것이 타당하고, "가장 좋은 계정 기반 유지" 는 **그 위에 얹는 2단계(별도 승인)** 로 두는 것이 폐쇄망 마찰·보안·구현 부담을 모두 만족하는 가장 타당한 경로다.
