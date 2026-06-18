# 단계 18 — 1.6.1 폐쇄망 smoke 수정 (1.6.2 패치)

- 분류: **patch (`1.6.2`) / 폐쇄망 실사용 smoke 결함 보강**
- 합의 계획: [`.gjc/plans/ralplan/2026-06-17-0734-closed-network-smoke/pending-approval.md`](../../.gjc/plans/ralplan/2026-06-17-0734-closed-network-smoke/pending-approval.md)
- 실행 원장: `.gjc/ultragoal/` (G001–G004)
- 선행 단계: [`phase-17-viewer-editor-and-launcher-ai-fixes.md`](phase-17-viewer-editor-and-launcher-ai-fixes.md)

---

## 1. 요약

폐쇄망 PC 에서 1.6.1 릴리즈 ZIP 을 빠르게 점검하며 확인된 실제 운영 결함을 1.6.2 패치로 묶었다. 범위는 기존 기능의 smoke 안정화이며, 신규 모듈이나 검색 기본값 변경은 포함하지 않는다.

1. **Document/HTML 뷰어 크기와 스크롤** — 창 높이 보기 iframe 이 작고, 전체 높이 보기에서 부모 스크롤·목차 스크롤·넓은 표 스크롤이 충돌했다.
2. **Document 목록 URL 파싱 실패** — 환경 변수 값 끝의 공백/줄바꿈이 서버 API URL 에 섞이면 `Failed to parse URL` 로 목록이 비었다.
3. **AeroAI 무응답 진단 부족** — Ollama 가 reasoning-only/빈 본문을 돌려도 운영자가 원인을 구분하기 어려웠다.
4. **통합 런처 READY 오판** — `run_all.bat` 가 Open Notebook process 반환만 보고 충분한 readiness 를 확인하지 못했다.
5. **Open Notebook API 연결 실패** — airgap adapter 의 API bind / browser-facing `API_URL` / CORS / `--local`·LAN 옵션이 폐쇄망 운영 방식과 어긋날 수 있었다.
   - Open Notebook adapter 변경은 sibling fork `Py-CI-Park/open-notebook` 의 `3b283b2` (`AeroOne 폐쇄망 airgap 어댑터를 보강한다`) 로 별도 반영했다.

---

## 2. 구현 단위 (G001–G004)

| 스토리 | 내용 | 핵심 파일 |
|---|---|---|
| G001 | 문서 뷰어 viewport 높이를 `calc(100dvh - 96px)` + `minHeight 680` 으로 확대. 전체 높이 보기에서는 목차/sidebar 의 max-height 를 부모 브라우저 viewport 기준으로 계산하고, 목차·표 같은 scrollable descendant 가 wheel 을 먼저 소비하도록 처리. 해시 이동은 부모 문서 경계로 clamp. Document 트리도 독립 스크롤. | `frontend/components/newsletter/html-viewer.tsx`, `frontend/components/documents/documents-workspace.tsx`, 관련 Vitest |
| G002 | Ollama 성공 응답이 `<think>` 제거 후 빈 답이면 한 번만 최종 답변을 재요청. 그래도 빈 답이면 `OllamaEmptyResponse` 로 502 계열을 유지하고, base_url/model/reason 을 안전하게 노출. | `backend/app/modules/ai/service.py`, `backend/tests/integration/test_ai_api.py` |
| G003 | `scripts/run_all.bat` 가 AeroOne backend health 후 Open Notebook API `:5055/health`, Frontend `:8502`, runtime `/config` 를 확인해야 READY 를 표시. `--local`/`--allow-host` 는 Open Notebook launcher 로도 전달. Open Notebook airgap `3-run.bat` 는 LAN 기본, loopback opt-out, `API_HOST`/`API_URL`/`CORS_ORIGINS` child env 명시, HTTP 200 readiness, 비대화형 대기, `--allow-host=<ip>` 를 지원한다. Sibling fork 반영 commit: `Py-CI-Park/open-notebook@3b283b2`. | `scripts/run_all.bat`, `../open-notebook/airgap/3-run.bat`, `../open-notebook/airgap/write_env.ps1`, 배치 테스트/문서 |
| G004 | 버전 표기와 운영 문서/보고서/검증 통계를 1.6.2 기준으로 갱신하고, 릴리즈 ZIP 에 GJC workflow state 와 QA artifact/scratch 파일이 섞이지 않도록 기존 `node_modules` 등 보호 제외목록을 유지하면서 `.gjc`, `artifacts`, `.ug-*` 를 packaging 제외 목록에 추가한 뒤 전체 테스트·브라우저 smoke·Open Notebook smoke 를 수행. | `README.md`, `frontend/lib/changelog.ts`, `offline_package.bat`, `docs/*` |

---

## 3. 핵심 설계 결정

- **FTS5 기본 검색 유지.** 이번 패치는 turbovec/vector 검색과 무관하며 제품 검색 경로를 바꾸지 않는다.
- **Open Notebook core 미수정.** 폐쇄망 차이는 `airgap/` adapter 에서 흡수한다. core 변경은 adapter 로 해결 불가능할 때만 별도 승인 대상으로 둔다.
- **READY 는 실제 HTTP 200 surface 기준.** 프로세스가 뜬 것과 사용자 브라우저가 API 에 연결되는 것은 다르므로 API health, frontend, `/config` 를 모두 확인하고, 4xx 응답은 준비 완료로 보지 않는다.
- **뷰어 전체 높이 모드는 부모 viewport 기준으로 목차 높이를 제한.** iframe 자체가 긴 문서 전체 높이가 되면 iframe 내부 `100vh` 는 실제 화면 높이가 아니므로, 부모 window height 를 CSS 변수/inline style 로 주입한다.
- **AeroAI 빈 답변은 1회만 재시도.** 무한 재시도나 가짜 fallback 답변은 금지하고, 실패 시 운영자가 원인을 볼 수 있게 진단만 개선한다.

---

## 4. 검증 결과

| 구분 | 명령/증거 | 결과 |
|---|---|---|
| backend 전체 | `cmd /c ".venv\\Scripts\\python.exe -m pytest tests -q"` | **175 passed**, 3 warnings(기존 Pydantic/pytest-asyncio deprecation) |
| frontend 전체 | `npm test` | **193 passed / 47 files** |
| frontend 타입 | `npm run typecheck` | `tsc --noEmit` 성공 |
| frontend 빌드 | `npm run build` | Next.js production build 성공 |
| run_all dry-run | `scripts\\run_all.bat --dry-run --on-bundle ..\\AeroOne-bundle --local` | AeroOne health → ON API health → ON frontend → `/config` 순서 출력, `3-run.bat --local` 전달 확인 |
| run_all LAN dry-run | `scripts\\run_all.bat --dry-run --on-bundle ..\\AeroOne-bundle --allow-host=10.0.0.5` | `3-run.bat --allow-host 10.0.0.5` 전달 확인 |
| Open Notebook adapter dry-run | `D:\\AeroOne-bundle\\3-run.bat --dry-run --allow-host=10.0.0.5` | API/Frontend `0.0.0.0`, `API_URL=http://10.0.0.5:5055`, CORS origin 출력 |
| Document 브라우저 smoke | `http://127.0.0.1:29501/documents` | 문서 3건 로드, URL parse/fetch failure 없음, viewport iframe 약 804px, 전체 높이 모드 TOC max-height 816px |
| Open Notebook 브라우저 smoke | `http://127.0.0.1:8502/notebooks` + `/config` | `Unable to Connect to API Server` 없음, `/config` 의 `apiUrl=http://127.0.0.1:5055`, API health 200 |
| 패키징 dry-run | `offline_package.bat --dry-run` | `/XD adds: .gjc artifacts vendor`, `/XF adds: .git .ug-*` 출력 및 script guard로 `.git` 파일·`node_modules` 포함 보호 제외목록 보존 확인 |
| 최종 문서 freshness review | `agent://83-DocsFreshnessFinal` | `CLEAR/CLEAR/CLEAR`, `APPROVE`, stale count/ZIP/LAN-default pattern blocker 0 |

브라우저 증거는 `.gjc/ultragoal/artifacts/G001/documents-current-smoke.png` 및 `.gjc/ultragoal/artifacts/G003/open-notebook-page-smoke.png` 에 보존했다.

---

## 5. 명시적 비범위

- Open Notebook upstream/core 코드 변경.
- AeroAI 모델 자동 다운로드 또는 Ollama 자체 설치 변경.
- turbovec/vector 검색 제품 통합.
- 인증/권한/APP_ENV 의미 변경.

---

## 6. AGENTS.md §6 위험신호 점검

`APP_ENV` Literal, `validate_runtime_security`, `setup_offline.bat` 기본 LAN 바인딩, `start_offline.bat` `--local` opt-out, `scripts/allow_lan_firewall.cmd` LocalSubnet scope, `backend/scripts/ensure_db_state.py` 종료 코드는 미접촉이다. `offline_package.bat` 제외 목록은 기존 보호 항목(`.git`, `node_modules` 등)을 제거하지 않고 `.gjc`, `artifacts`, `.ug-*` 만 추가해 릴리즈 ZIP 에 workflow/QA state 가 섞이지 않도록 했다. 변경은 viewer, AI 진단, 통합 런처 readiness, Open Notebook airgap adapter, 릴리즈 패키징 위생으로 한정된다.
