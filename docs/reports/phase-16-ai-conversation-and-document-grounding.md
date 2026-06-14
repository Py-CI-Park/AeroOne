# 단계 16 — AI 대화 영속화 + 문서 근거 연결 강화 (1.5 2차 증분)

- 분류: **minor 후보 (`1.5.0`) / AI 모듈 2차 증분**
- 합의 계획: [`.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`](../../.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md) (Architect CLEAR/APPROVE, Critic OKAY)
- 선행 연구: [`phase-15-openwebui-reference-research.md`](phase-15-openwebui-reference-research.md)
- 실행 원장: `.gjc/ultragoal/` (G001–G008, 스토리별 architect+executor QA 게이트 + 체크포인트)

---

## 1. 요약

단계 14의 폐쇄망 Ollama 채팅(`/ai`)은 대화가 화면 상태에만 머물러 새로고침 시 사라졌고, 답변 근거 문서를 사용자가 지정할 수 없었다. 본 증분은 Open WebUI 참조 연구(단계 15)의 권고대로 **대화 이력화 + 운영형 문서 근거 연결**을 추가한다. 단, Open WebUI 전체 복제가 아니라 AeroOne 폐쇄망 원칙(same-origin 프록시·backend 전용 Ollama·FTS5·path-guard·collection whitelist)을 그대로 재사용하는 경량 증분이다.

신원은 **세션쿠키(`owner_session_id`) 단독 권위**의 하이브리드 1단계로, 무로그인 사용자도 본인 대화만 보고 이어갈 수 있다. 계정 기반(2단계)은 명시적 비범위로 분리했다.

---

## 2. 구현 단위 (G001–G008)

| 스토리 | 내용 | 핵심 파일 |
|---|---|---|
| G001 | 대화 영속화 3테이블(`ai_conversations`/`ai_messages`/`ai_message_citations`) + Alembic `20260613_0003` | `backend/app/modules/ai/models.py`, `backend/alembic/versions/20260613_0003_ai_conversations.py` |
| G002 | 대화 CRUD API + 세션쿠키 단독 스코프(owner_ip 메타 전용) | `backend/app/modules/ai/repositories.py`, `api/public.py`, `schemas.py` |
| G003 | `/ai` 3분할 UI(대화목록·채팅·근거) + 프록시 Cookie/Set-Cookie 중계 | `frontend/components/ai/ai-chat-workspace.tsx`, `app/api/frontend/ai/*` |
| G004 | copy / regenerate / stop(AbortController) + 중지 의미론 카피 | `ai-chat-workspace.tsx` |
| G005 | 검색결과 선택 후 질문(`selected_refs`, collections 위임 load_refs) | `collections/search_service.py`, `ai/service.py` |
| G006 | citation 우측 패널: 새 탭 deep-link + sandboxed iframe 인앱 미리보기 | `ai-chat-workspace.tsx` |
| G007 | 근거 범위 프리셋 토글(document/civil/nsa-gated), collections 하드코딩 제거 | `ai-chat-workspace.tsx` |
| G008 | 보고서 검토 프롬프트 preset 6종 + 문서/검증 마무리 | `ai-chat-workspace.tsx`, 본 문서 |

---

## 3. 핵심 설계 결정

- **신원 = 세션쿠키 단독 권위.** 초기 안의 "IP 폴백"은 공용 PC/NAT 환경에서 남의 대화가 노출되는 누수 벡터였다. 조회는 `owner_session_id` 단독, `owner_ip`는 감사/2단계 claim 보조 메타 컬럼(WHERE 미참여), 쿠키 부재=빈 이력+신규 세션. 동일 IP·상이 쿠키 두 클라이언트 상호 404 통합테스트로 고정.
- **검색/path 정책 단일 원천.** `selected_refs` 본문 로드는 `HtmlCollectionSearchService.load_refs`가 `resolve_download_path`(.html, _debug 제외, path-guard)를 강제 경유한다. AI 서비스는 경로 해석/본문 추출을 직접 하지 않는다. traversal/없는/미허용 ref는 silent drop.
- **nsa 현상유지.** nsa unlock은 frontend localStorage 가림막(실인증 아님)이고 백엔드는 기존 `/search`와 동일하게 nsa를 자유 수용한다. 본 증분은 nsa 거부 게이트를 추가하지 않는다(백엔드 nsa 인증 게이트는 별도 스코프).
- **영속화 feature flag.** `ai_persistence_enabled`(기본 OFF). 임시 대화/플래그 OFF는 미저장.
- **same-origin 유지.** 브라우저는 `/api/frontend/ai/*` 프록시만 호출하고, 프록시가 Cookie/Set-Cookie(host-only+Path=/)를 투명 중계한다.

---

## 4. 검증 게이트에서 잡은 결함

| 스토리 | 결함 | 조치 |
|---|---|---|
| G002 | 운영 SQLite 엔진이 `PRAGMA foreign_keys=ON`을 켜지 않아(테스트 픽스처에만 존재) 대화 삭제 시 메시지/citation 고아 잔존 + rowid 재사용 교차노출 가능 | 두 운영 엔진 경로(`Database`/`get_engine`)에 connect 리스너로 PRAGMA 적용 + `delete_conversation`을 ORM 삭제(cascade)로 전환 + 고아 0 회귀테스트 추가. 전역 FK 강제가 기존 newsletter/read_tracking 흐름을 깨지 않음을 full suite로 확인 |
| G003 | 이전 세션 dev 서버가 `.next`를 점유해 prod 빌드 손상(`./638.js`) | stale 서버 종료 + clean rebuild 로 거짓 통과 차단 |
| G005/G006(QA) | 세션 환경의 `SERVER_API_BASE_URL=http://backend:18437`(Docker leak)가 collections 프록시를 깨뜨림 | QA 환경 변수 교정으로 해소(코드 무관). AI 프록시는 127.0.0.1 local-first fallback 으로 이미 견딤 |

---

## 5. 검증 결과

- backend: `pytest tests` → **162 passed**(신규 `test_ai_migration`/`test_ai_conversations`/`test_ai_chat_refs` 포함, 회귀 0).
- frontend: `vitest run` → **176 passed / 46 files**(신규 ai-conversations/-controls/-selected-refs/-citation-panel/-scope/-presets + conversations-route).
- `npx tsc --noEmit` clean, `npx next build` clean(`/ai` + AI 프록시 4라우트 컴파일).
- alembic `upgrade head → downgrade -1 → upgrade head` 왕복 동일성, `ensure_db_state` 종료코드 0/1/2/3 불변(ai 테이블은 CORE_TABLES 아님).
- 실브라우저 E2E(Next prod + 실 backend + 실 Ollama gemma4:12b + 실 `_database`): 3분할/대화목록/선택 후 질문/문서근거 답변/citation 미리보기/근거 범위 토글 스크린샷 — `docs/images/ai-3pane*.png`, `ai-chat-controls.png`, `ai-selected-refs.png`, `ai-citation-preview.png`, `ai-scope.png`.

---

## 6. 명시적 비범위(후속)

- 계정 기반 신원(admin/user 2역할, 로그인 UI, user_id claim) — 하이브리드 2단계.
- nsa 백엔드 unlock 게이트(실인증), 관리자 AI DB override, vector RAG/embedding, 서버측 streaming/취소, 공유/export, 사용량 통계 대시보드, ai_presets DB seed.

---

## 7. AGENTS.md §6 위험신호 점검

APP_ENV Literal·validate_runtime_security·setup_offline LAN 바인딩·`ensure_db_state` 종료코드·offline_package `/XD` 제외목록 모두 미접촉. 신규는 가산적(테이블 3개 + feature flag + 프론트 UI)이며 기존 분기 의미를 바꾸지 않는다.
