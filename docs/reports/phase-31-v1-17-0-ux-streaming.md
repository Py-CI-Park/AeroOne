# 단계 31 — 1.17.0 사용자 체감 릴리스: 대화형 차트 컴포저 · AeroAI 스트리밍/첨부 · 상태 배지/최근 열람

- 분류: **minor (`1.17.0`)** — 1.16.3 전수 검사([`v1-16-3-full-audit-2026-07-16.md`](v1-16-3-full-audit-2026-07-16.md))의 P0-3/P1-1/P1-2/P1-3 을 한 사이클로 구현
- dev 브랜치: `1.17.0-dev`
- 기준 계획: [`v1-17-0-improvement-plan-2026-07-16.md`](v1-17-0-improvement-plan-2026-07-16.md)
- 진입점: 대시보드(`/`) 상태 배지·최근 열람, Office Studio 차트 탭, `/ai`

---

## 1. 배경

1.16.3 전수 검사에서 사용자 체감 축의 3대 결핍이 확정됐다 — (a) 차트 스튜디오 첫 화면에 결정 요소 8개+가 동시 노출되어 "입력란이 복잡해 보인다"(§7, 74/100), (b) AI 채팅이 비스트리밍이라 로컬 LLM 의 긴 침묵 후 일괄 출력(§6), (c) 외부 앱 카드(Notebook/OpenWebUI)가 무배지라 죽은 링크를 눌러봐야 아는 비대칭(§14). 부수적으로 개발 PC 의 node_modules 드리프트(§13)가 tsc 게이트를 로컬에서만 깨뜨리는 문제가 실측됐다.

## 2. 구현 (스토리 단위)

### G001 — npm ci 일원화 (P0-3, commit `8d5dadb`)

`setup.bat` frontend 설치를 `npm ci` 로 전환하고 README/런북/Dockerfile 의 재도입 경로 5곳을 함께 정리, 오프라인 설치(node_modules ZIP 반입) 경계는 테스트 부정 단언으로 고정.

### G002 — 대화형 차트 컴포저 (P1-1, commit `fe80c2d`)

단일 컴포저(멀티라인 입력=목적 문장·CSV 붙여넣기 겸용 + 표 형식 감지 제안 + 클립/드래그 첨부 + 자동 inspect 열 칩) + 후속 명령 refine. 백엔드 `POST /charts/generate` 에 `previous_spec_json` 추가 — 우선순위 manual > previous+명령(LLM refine, 실패 시 규칙 폴백) > LLM 신규 > 규칙 신규. 규칙 refine 은 한국어 키워드(유형/가로·세로/정렬/상위 N/누적/제목)를 결정적으로 패치하고 부분 문자열 오탐('우선'의 '선', '온라인'의 '라인')을 복합어 제한·마스킹으로 차단. 고급 manualSpec 패널·예제 원클릭·reopen/duplicate 흐름은 접힘 보존.

### G003 — AeroAI SSE 스트리밍 + 파일 첨부 (P1-2, commit `7191d3d`)

`POST /api/v1/ai/chat/stream` — SSE(citations 0~1→delta N→done|error), think 블록은 공백/대소문자 변형·1자 청크 분할까지 차단하는 문자 단위 상태기계로 절대 미노출, 영속화/요청 로그는 완결 시점 1회(실패 시 `done{persisted:false, persist_error}`+PersistFailed, 중단 시 aborted, 가시 delta 0 빈 응답은 1회 재시도). 첨부(.md/.txt/.csv ≤5개·합계 20만자)는 청크마다 untrusted 프레이밍을 반복해 1회성 주입하고 원문은 미저장('[첨부: 이름]' 접미만). openai_compatible 은 egress_transport 보안 계약 보존을 위해 단일 delta 래핑(실 토큰 스트리밍은 Ollama). 41KB `ai-chat-workspace` 를 8개 컴포넌트로 분해.

**치명 결함 실측·근절:** 라이브 검증(실 gemma4:12b) 중 스트리밍 마크다운 파서가 `## `(제목 텍스트 도착 전 접두사)에서 무한 루프해 브라우저 메인 스레드를 영구 잠금 — heading `(.*)` 허용 + 문단 폴백 최소 1줄 소비 진행 불변식으로 수정하고 전 접두사 렌더 회귀 테스트로 고정.

### G004 — 상태 배지·최근 열람 + 릴리스 준비 (P1-3)

`GET /api/v1/launchers/{kind}/health`(open_notebook/open_webui, 127.0.0.1 loopback TCP+HTTP 프로브 — Leantime 프로브를 `app/core/http_probe.py` 로 승격 공유) + ExternalLauncherCard 상태 배지(ready 일 때만 링크 활성). `GET /api/v1/newsletters/read-events/mine`(read 비콘과 동일한 IP 스코프·직접호출 예외 패턴) + 대시보드 "최근 본 뉴스레터" 스트립(빈/실패 시 무렌더). changelog 1.17.0·README 버전 표기·본 보고서.

## 3. 검토하고 제외한 대안

- 차트: 채팅 로그형 다중 턴 UI(작업 이력과 중복), 클라이언트 측 스펙 패치(서버 검증 단일 원천 훼손).
- AI: WebSocket(BFF 릴레이 복잡도 대비 무이득), EventSource(POST 본문 불가), compatible 실 토큰 스트리밍(egress SSRF-핀닝 우회 위험).
- 최근 열람: localStorage 방식(문서까지 커버되나 read_tracking 재사용 지시와 어긋남) 대신 비콘과 동일한 IP 스코프 서버 조회 채택.

## 4. 코드 (진실 원천)

| 영역 | 위치 |
|---|---|
| 차트 refine 엔진 | `backend/app/modules/office_tools/services/chart/refine.py`, `service.py`(`_resolve_spec` 우선순위), `api/charts.py`(`previous_spec_json`) |
| 차트 컴포저 | `frontend/components/office-tools/chart-composer.tsx`, `chart-form.tsx`(재편) |
| AI 스트리밍 | `backend/app/modules/ai/service.py`(`ThinkBlockStreamFilter`/`chat_stream`), `api/public.py`(`/chat/stream`, `_persist_turn`), `schemas.py`(`AiAttachment`) |
| AI 프런트 | `frontend/components/ai/`(composer/message-list/markdown/citation-panel 등 분해), `lib/api.ts`(`streamAiChat`/`parseSseBuffer`), `app/api/frontend/ai/chat/stream/route.ts` |
| 런처 배지 | `backend/app/core/http_probe.py`, `backend/app/modules/launchers/`, `frontend/components/dashboard/notebook-link-card.tsx` |
| 최근 열람 | `backend/app/modules/read_tracking/`(`recent_for_ip`, `/read-events/mine`), `frontend/components/dashboard/recent-reads-strip.tsx`, `app/page.tsx` |

## 5. 회귀 방지

- 차트: `test_office_tools_chart_refine.py`(23·오탐 회귀 포함), `test_office_tools_charts.py`(84), `office-tools-chart-page.test.tsx`(17), `chart-composer.test.tsx`(15), adversarial 매트릭스 14/14(`artifacts/qa/ultragoal/G002/`).
- AI: `test_ai_stream_api.py`(16 — 프레임 순서/think 변형/영속화·중단·재시도·PersistFailed·404), `test_think_stream_filter.py`(13), `test_attachment_context.py`(5), `test_ollama_ndjson_stream.py`(7), 프런트 `ai-stream.test.ts`(11)/`ai-markdown.test.tsx`(접두사 전수 3)/AI 스위트 11파일 56, adversarial 19+1(`artifacts/qa/ultragoal/G003/`).
- 배지/열람: `test_launchers_health.py`(13), read_tracking 20, `external-launcher-card.test.tsx`(19), `recent-reads-strip.test.tsx`, `home-page.test.tsx`(20, 비동기 배지 반영).

## 6. 검증 게이트

- backend `pytest tests` 전체 / frontend Vitest 전체 / `tsc --noEmit` / `next build` — 수치는 본 문서 하단 "최종 게이트 실측"에 기록.
- 각 스토리는 2-pass architect 리뷰(최종 CLEAR/APPROVE)와 executor QA/red-team 레인 + 라이브 브라우저 실측(차트: CSV 붙여넣기→열 칩→생성→"가로 막대로" 재렌더 스크린샷, AI: 실 gemma4:12b 스트리밍 완결·미드스트림 커서·에러 프레임)을 통과했다. 증거: `artifacts/qa/ultragoal/G00{1,2,3,4}/`, ultragoal ledger.

## 7. 최종 게이트 실측 (병합 직전 갱신)

- backend 전체: (기록 위치 — 병합 직전 실행 결과)
- frontend 전체 + tsc + next build: (기록 위치 — 병합 직전 실행 결과)

## 8. 후속 / 연관

- 1.17.x: P2-3 컬렉션 품질(NSA 권한 게이트 승격 등), P2-5 부채 소품.
- 1.18.0: P2-1 Civil v1.8(SVG 상호작용·내보내기·lazy), P2-2 관리자 콘솔 리모델링, P2-4 성능 예산.
- openai_compatible 실 토큰 스트리밍은 egress_transport 에 스트리밍 계약을 추가하는 별도 사이클 안건.
