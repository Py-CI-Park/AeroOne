# 단계 17 — Markdown/HTML 뷰어-에디터 + 런처·AeroAI·HTML 스크롤 수정 (1.6 증분)

- 분류: **minor (`1.6.0`) / 뷰어 모듈 신설 + 운영 결함 3종 수정**
- 합의 계획: [`.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`](../../.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md) (deliberate 모드 — Architect pass2 CLEAR/APPROVE, Critic pass2 OKAY)
- 실행 원장: `.gjc/ultragoal/` (G001–G005, 스토리별 architect + executor QA 게이트 + 체크포인트)
- 선행 단계: [`phase-16-ai-conversation-and-document-grounding.md`](phase-16-ai-conversation-and-document-grounding.md)

---

## 1. 요약

단계 16(1.5.0) 직후 운영자가 보고한 결함 3종과 신규 요구 1건을 한 증분으로 묶었다.

1. **런처 행(hang)** — `scripts/run_all.bat`가 묶음 기동 후 종료하지 못하고 멈춤.
2. **AeroAI 무응답("죄송")** — 일반 지식 질문에도 모델이 답을 거부.
3. **HTML 뷰어 스크롤 튐 / TOC 미스크롤** — content-fit 높이 재계산이 스크롤 위치를 깨뜨림.
4. **(신규) Markdown/HTML 뷰어-에디터 탭** — 로컬 `.md`/`.html` 파일을 폐쇄망에서 안전하게 열람·편집·미리보기.

신규 `render` 모듈과 `/viewer` 페이지가 추가되므로 §9.6 규약상 minor(`1.6.0`)로 분류한다. 모든 변경은 가산적이며 기존 분기 의미를 바꾸지 않는다.

---

## 2. 구현 단위 (G001–G005)

| 스토리 | 내용 | 핵심 파일 |
|---|---|---|
| G001 | 런처 de-hang — `--no-pause` 플래그 + `AEROONE_NO_PAUSE` env, 3개 pause 지점을 `if not defined NO_PAUSE pause`로 가드, `run_all.bat`이 `--no-pause` 전달 | `start_offline.bat`, `scripts/run_all.bat` |
| G002 | AeroAI 죄송 근본 원인 = 무관한 문서 컨텍스트에서 거부하던 과잉제약 프롬프트. 일반지식 허용·anti-refusal 프롬프트 개정 + `_strip_think_blocks`(`<think>`/`<thinking>` 제거) + 신규 `OllamaEmptyResponse`(빈응답≠연결끊김, 502) | `backend/app/modules/ai/service.py`, `backend/app/modules/ai/api/public.py`, `backend/tests/integration/test_ai_api.py` |
| G003 | HTML 뷰어 content-mode 스크롤 보존 — threshold-gated setHeight(±8px 무시), 높이 기록 시 `window.scrollY` rAF 복원, poll early-exit. `showFitToggle` viewport-fit escape hatch(스크롤형 TOC) | `frontend/components/newsletter/html-viewer.tsx`, `frontend/components/newsletter/newsletter-detail-client.tsx`, `frontend/tests/components/html-viewer.test.tsx` |
| G004 | 무상태 렌더 엔드포인트 — `sanitize_html` 본문을 모듈레벨 `sanitize_html_fragment(html)`로 추출(동작 동일), 신규 `POST /api/v1/render` `{type:'markdown'\|'html', text}` → `{html}`(StorageService/path 미사용, `extra='forbid'`, text max 1_000_000) | `backend/app/modules/newsletter/services/html_render_service.py`, `backend/app/modules/render/{__init__,schemas,api}.py`, `backend/app/main.py`, `backend/tests/integration/test_render_api.py` |
| G005 | 뷰어-에디터 탭 — File API `.md`/`.html` 로드+드래그드롭, textarea 편집, 동일출처 프록시 `POST /api/frontend/render`, **`<iframe sandbox="">`(빈 샌드박스) 미리보기**(스크립트 미실행 경계), Blob 다운로드. 대시보드 Document 섹션 Viewer 카드(active 8) | `frontend/app/api/frontend/render/route.ts`, `frontend/components/viewer/viewer-editor.tsx`, `frontend/app/viewer/page.tsx`, `frontend/app/page.tsx`, `frontend/tests/components/viewer-editor.test.tsx`, `frontend/tests/app/home-page.test.tsx` |

---

## 3. 핵심 설계 결정

- **뷰어 렌더 = 무상태 same-origin.** 브라우저는 로컬 파일을 File API로만 읽고, 렌더/세니타이즈는 동일출처 `POST /api/v1/render`(경로 인자 없음, StorageService 미접촉)가 `markdown.markdown` + `sanitize_html_fragment`를 재사용한다. 외부 CDN/자산 0.
- **미리보기 스크립트 경계 = 빈 샌드박스.** `<iframe sandbox="" srcDoc={html}>`로 `allow-scripts`/`allow-same-origin` 미부여. 신뢰불가 HTML의 `<script>`/`on*`/`javascript:`는 백엔드 세니타이즈에서 제거되고, 설령 남아도 불투명 origin 샌드박스에서 실행되지 않는다(AC5 고정).
- **AeroAI 거부 원인 = 프롬프트, 모델/think 태그 아님.** gemma4:12b는 thinking 모델이나 `think:false`로 동작한다. 빈 응답은 `OllamaEmptyResponse`(502)로 연결단절(`OllamaUnavailable` 503)과 구분한다.
- **HTML 뷰어 스크롤 보존 > viewport 강제전환.** content-mode 스크롤 튐은 scrollY 보존+threshold+poll로 해결하고, TOC 스크롤은 content-mode 본질이므로 `showFitToggle` escape hatch만 추가(기본 viewport 전환 금지).
- **런처 행 = `start_offline.bat`의 pause.** 묶음 기동 시 마지막 pause가 종료를 막던 것이 근본 원인. `--no-pause` 가드로 자동화 경로만 면제하고 수동 실행은 pause 유지.

---

## 4. 검증 게이트에서 잡은 결함

| 스토리 | 결함 | 조치 |
|---|---|---|
| G002 | 빈 응답을 연결단절(503)로 오분류 | `OllamaEmptyResponse(OllamaError)` 신설 + `public.py`에서 502 매핑, 회귀테스트 추가 |
| G005(QA) | 프록시 local-first(127.0.0.1:18437)가 dual-backend QA 환경의 OLD 백엔드(렌더 미탑재)에 닿아 404·fall-through 없음 | QA 환경 아티팩트로 판정(not_applicable). 단일 백엔드 운영에서는 정상 — 본 단계 라이브 검증에서 프록시→백엔드 e2e 200 확인 |
| 배포 | 이전 QA의 `next dev`가 prod `.next`를 손상 | clean `next build` 재생성으로 거짓통과 차단 |

---

## 5. 검증 결과

- backend: `pytest tests` → **171 passed**(162→+9: AI 3 + render 6, 회귀 0).
- frontend: `vitest run` → **188 passed / 47 files**(179→+9: viewer-scroll 3 + viewer-editor 5 + home-page 1).
- `npx tsc --noEmit` clean, `npx next build` clean(`/viewer` + render 프록시 라우트 컴파일).
- 실브라우저 라이브 검증: `/viewer`에서 Markdown 렌더(제목·목록·강조) + 주입 `<script>` 제거 확인, `iframe sandbox=""`·`window.__pwn` undefined(미실행). 대시보드 8 active + Viewer 카드. 프록시→백엔드 렌더 e2e 200(md `<h1>제목</h1>`, html `<script>` 제거) — `docs/images/viewer-preview-qa.png`.
- 런처: 18437 점유 시 무행 EXIT1, 음성 대조군(pause 유지) timeout-kill 124로 가드 동작 확인.

---

## 6. 명시적 비범위(후속)

- 서버측 파일 쓰기(뷰어 저장을 서버 경로에) — 현재는 Blob 클라이언트 다운로드만.
- 렌더 프록시 4xx/5xx fall-through 강화(AI 프록시와 동일 한계, 단일 백엔드 운영엔 불필요).
- PDF/이미지 뷰어 확장, 뷰어 내 협업/버전관리.

---

## 7. AGENTS.md §6 위험신호 점검

APP_ENV Literal·validate_runtime_security·setup_offline LAN 바인딩·`ensure_db_state` 종료코드·`offline_package.bat` `/XD` 제외목록·firewall `remoteip=LocalSubnet` 모두 미접촉. 신규는 가산적(render 모듈 + 뷰어 페이지 + 런처 옵트인 플래그)이며 기존 분기 의미를 바꾸지 않는다.
