# 단계 14 — 폐쇄망 Ollama AI 채팅 + HTML 본문 검색

- 분류: **minor (`1.5.0`)** — AI 채팅 + 컬렉션 본문 검색
- 계획 산출물: `.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`
- 진입점: 대시보드 → `AI` 카드 → `/ai`

---

## 1. 배경

폐쇄망 PC에는 Ollama 가 `11434` 포트로 설치되어 있고 기본 모델은 `gemma4:12b` 로 제공된다. 운영 요구는 두 가지다. 첫째, OpenWebUI 나 `ollama run` 처럼 AeroOne 안에서 바로 기본 모델과 대화할 수 있어야 한다. 둘째, `_database` 에 존재하는 HTML 문서를 파일명뿐 아니라 **본문 전체 기준으로 빠르게 검색**하고 검색 결과에서 해당 파일을 바로 열 수 있어야 한다.

기존 Document/Civil/NSA 컬렉션은 이미 same-origin 프록시와 sandbox iframe 렌더링을 갖고 있으므로, 새 AI 기능은 이 원칙을 깨지 않고 붙여야 한다. 특히 브라우저가 `localhost:11434` 를 직접 호출하면 LAN 다른 PC에서는 visitor PC의 localhost를 보게 되어 실패하고, Ollama 포트도 사용자 브라우저에 노출된다.

## 2. 선택한 접근

**컬렉션 본문 검색은 AI가 아니라 collections/shared 계층이 소유한다.** `HtmlCollectionSearchService` 는 기존 `HtmlCollectionService.discover_list()` 와 `resolve_download_path()` 를 재사용한다. 그래서 `.html` 만 검색하고, `_debug.html` 을 제외하며, collection whitelist 와 path guard 정책이 list/content/download 와 같다. 검색 엔진은 SQLite FTS5 이며, FTS5 미지원 환경에서는 앱 시작을 깨지 않고 degraded 응답을 돌려준다.

**AI 채팅은 백엔드 전용 Ollama 호출로 제한한다.** `/api/v1/ai/status` 와 `/api/v1/ai/chat` 을 FastAPI 에 두고, 브라우저는 `/api/frontend/ai/status`, `/api/frontend/ai/chat` same-origin 라우트만 호출한다. 기본 모델은 `gemma4:12b` 이며 `OLLAMA_DEFAULT_MODEL` 로 바꿀 수 있다. 채팅 UI 는 답변 생성 중 즉시 대기 표시를 보여주고 pending 중 중복 전송을 막는다.

**검색 결과와 citation 은 viewer deep-link 를 가진다.** 결과 target 은 `document -> /documents?path=...`, `civil -> /reports/civil-aircraft?path=...`, `nsa -> /nsa?path=...` 이다. `DocumentsWorkspace` 는 `initialPath` 를 받아 목록 로드 후 해당 문서를 선택한다. NSA 는 기존 casual gate 를 유지하여 unlock 전에는 목록·본문·path 대상이 노출되지 않고, unlock 이후에만 `initialPath` 를 전달한다.

## 3. 보안 / 폐쇄망 원칙

| 원칙 | 적용 |
|---|---|
| 브라우저 직접 Ollama 호출 금지 | frontend 는 `/api/frontend/ai/*` 만 호출 |
| collection policy 단일 원천 | 검색 서비스가 기존 collection discovery/path guard 재사용 |
| NSA 기본 비노출 | global/dashboard 검색과 AI context 기본 범위는 `document,civil` |
| 장애 격리 | Ollama unavailable/model missing/timeout 은 AI 영역만 degrade |
| prompt injection 완화 | 문서 snippet 은 untrusted context 로 system prompt 에 주입 |
| 출처 기반 답변 | `use_search` 시 citations 와 navigation URL 을 응답 |

## 4. 코드 (진실 원천)

| 영역 | 위치 |
|---|---|
| AI 설정 | `backend/app/core/config.py` (`AI_FEATURES_ENABLED`, `OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL`, timeout/context 설정) |
| 컬렉션 FTS 검색 | `backend/app/modules/collections/search_service.py` |
| 검색 API | `backend/app/modules/collections/api/public.py` (`/api/v1/collections/search`) |
| AI API | `backend/app/modules/ai/api/public.py`, `backend/app/modules/ai/service.py`, `backend/app/modules/ai/schemas.py` |
| 라우터 등록 | `backend/app/main.py` (`/api/v1/ai`) |
| Next AI 프록시 | `frontend/app/api/frontend/ai/status/route.ts`, `frontend/app/api/frontend/ai/chat/route.ts` |
| 프런트 fetcher/type | `frontend/lib/api.ts`, `frontend/lib/types.ts` |
| AI 화면 | `frontend/app/ai/page.tsx`, `frontend/components/ai/ai-chat-workspace.tsx` |
| 대시보드 카드 | `frontend/app/page.tsx` (`AI` active 카드) |
| deep-link 선택 | `frontend/app/documents/page.tsx`, `frontend/app/reports/civil-aircraft/page.tsx`, `frontend/app/nsa/page.tsx`, `frontend/components/documents/documents-workspace.tsx`, `frontend/components/collections/collection-password-gate.tsx` |
| 배치 기본값 | `setup.bat`, `setup_offline.bat` (`AI_FEATURES_ENABLED=true`, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_DEFAULT_MODEL=gemma4:12b`) |

## 5. 회귀 방지

- 백엔드: `backend/tests/integration/test_collections_api.py` 에 FTS 기본 범위(document/civil), 명시 NSA scope, `_debug`/비HTML 제외, unknown collection 404 를 추가했다. `backend/tests/integration/test_ai_api.py` 는 AI status/chat, 기본 document/civil scope, 명시 NSA scope, unknown collection 검증을 맡는다.
- 프런트: `frontend/tests/components/ai-chat-workspace.test.tsx` 는 AI 상태 표시, 답변 대기 UI, 본문 검색 결과 링크, citation 링크를 검증한다. `frontend/tests/app/api/frontend/ai-route.test.ts` 는 Next AI 프록시가 FastAPI 로만 전달하는지 검증한다. 기존 collection proxy, `DocumentsWorkspace`, NSA gate, home page 테스트를 갱신했다.
- 배치: `backend/tests/unit/shared/test_windows_batch_scripts.py` 가 `setup.bat` 의 AI/Ollama env 기본값 기록을 확인한다.

## 6. 검증 게이트

최종 구현 검증:

- backend: `cmd.exe /c ".venv\\Scripts\\python.exe -m pytest tests -q"` → **137 passed**
- frontend: `npm test -- --run` → **153 passed (39 파일)**
- frontend typecheck/build: `npx tsc --noEmit` → exit 0, `npm run build` → success

## 7. 운영 안내

기본값은 폐쇄망 PC 자신이 실행하는 Ollama 를 가리킨다.

```env
AI_FEATURES_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=gemma4:12b
```

Ollama 가 다른 폐쇄망 PC 에 있다면 `backend/.env` 의 `OLLAMA_BASE_URL` 만 `http://<ollama-ip>:11434` 로 바꾼 뒤 backend 를 재시작한다. 브라우저와 Next frontend 설정에는 Ollama URL 을 넣지 않는다.

## 8. 후속

embedding/semantic search 는 후속 ADR 로 남긴다. 현재 버전은 폐쇄망 기본 보장 모델인 `gemma4:12b` 와 SQLite FTS5 만으로 문서 찾기·본문 검색·기본 대화를 제공한다.
