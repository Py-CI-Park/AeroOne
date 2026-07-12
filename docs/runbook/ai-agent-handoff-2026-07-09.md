# AI 에이전트 핸드오프 — 1.12.2 안정판과 1.13.0 운영 경험 계획

> **Superseded:** 이 문서는 2026-07-09 당시의 계획 전 상태를 보존한다. 현재 v1.13.0 재개에는 [`ai-agent-handoff-2026-07-11.md`](ai-agent-handoff-2026-07-11.md)와 [`v1-13-0-development-status-2026-07-11.md`](../reports/v1-13-0-development-status-2026-07-11.md)를 사용한다.

- 작성일: 2026-07-09
- 작성 브랜치: `1.13.0-dev`
- 기준 안정판: `1.12.2`
- 기준 main commit: `2f592c4` (`대시보드 시간과 로그인 UI 정리 1.12.2를 병합한다`)
- 대상 독자: Codex, Claude Code, GJC, 기타 AI code agent, 사람 운영자/검토자
- 목적: 새 에이전트가 이전 작업 흐름, 완료된 릴리즈, 원격 브랜치 상태, 진행 중 계획, 다음 실행 순서, 검증 기준, 금지 사항을 한 번에 파악하고 안전하게 이어받도록 한다.

---

## 0. 가장 먼저 읽을 결론

| 질문 | 답 |
|---|---|
| 현재 배포 가능한 최신 안정판은? | `1.12.2` GitHub Release |
| 현재 `main` 은 원격과 동기화되어 있는가? | 예. `main...origin/main`, 추가 원격 main 변경 없음 |
| 열린 PR 이 있는가? | 없음 |
| 새 작업 브랜치가 있는가? | 있음. `origin/1.13.0-dev` |
| `1.13.0-dev` 에 제품 코드가 들어갔는가? | 아직 없음. 현재는 `.omo/` 계획/증거/ledger 파일만 있음 |
| `1.13.0-dev` 를 main 에 병합해도 되는가? | 아직 안 됨. 제품 기능 구현과 검증이 없고, `.omo` 계획만 있는 blocked 상태 |
| 다음 에이전트의 첫 실제 작업은? | `1.13.0-dev` 에서 `DESIGN.md` 를 먼저 작성하고 커밋한 뒤 UI/백엔드 구현을 시작 |
| README 버전을 1.13.0 으로 올려도 되는가? | 아직 안 됨. release-final commit 전까지 `1.12.2` 유지 |

---

## 1. 저장소 현재 진실 원천

| 구분 | 값 | 확인/근거 |
|---|---|---|
| 원격 | `origin` = `https://github.com/Py-CI-Park/AeroOne.git` | `git remote -v` |
| 안정 브랜치 | `main` | `git branch --show-current` 기준은 현재 이 문서를 쓰기 전 `main`, 문서는 `1.13.0-dev` 에서 작성 |
| 최신 안정 main | `2f592c4` | `origin/main`, tag `1.12.2` |
| 최신 안정 tag | `1.12.2` | `git tag --sort=-creatordate --list "1.*"` |
| 최신 안정 Release | https://github.com/Py-CI-Park/AeroOne/releases/tag/1.12.2 | `gh release view` |
| 최신 dev 브랜치 | `origin/1.13.0-dev` | `git branch -vv --all` |
| 1.13.0-dev 최신 commit | `2bac795` | `v1.13.0 운영 경험 계획과 실행 상태를 보존한다` |
| 열린 PR | 없음 | `gh pr list --state open` 결과 `[]` |
| 로컬 작업 상태 | 이 문서 작성 전 `main` clean, 이후 `1.13.0-dev` 에서 문서 변경 | `git status --short --branch` |

---

## 2. 1.12.2 릴리즈 완료 상태

| 항목 | 값 |
|---|---|
| PR | #21 merged |
| PR URL | https://github.com/Py-CI-Park/AeroOne/pull/21 |
| main merge commit | `2f592c4` |
| tag | `1.12.2` |
| GitHub Release | https://github.com/Py-CI-Park/AeroOne/releases/tag/1.12.2 |
| Release 이름 | `1.12.2 — 대시보드 시간과 로그인 UI 정리` |
| 오프라인 ZIP | `AeroOne-offline-1.12.2-20260708-081654.zip` |
| ZIP SHA256 | `b67f595f0b33896015dfe1651f74d1f883de157094bf347bdf81f1d7d0c2e4cd` |
| SHA256 파일 | `AeroOne-offline-1.12.2-20260708-081654.zip.sha256` |
| Release 상태 | draft 아님, prerelease 아님, ZIP/sha256 asset 업로드 완료 |

### 2.1 1.12.2 사용자-visible 변경

| 화면/영역 | 1.12.1 이전/직후 상태 | 1.12.2 결과 |
|---|---|---|
| 헤더 버전 배지 | `v1.12.1 · 날짜` 식으로 날짜가 즉시 보일 수 있음 | 헤더에는 `v1.12.2` 만 즉시 표시 |
| 업데이트 날짜 | 대시보드에서 운영 날짜로 오해될 수 있음 | 버전 클릭 모달에서만 표시 |
| 대시보드 상단 | 현재 한국 시간 표시 없음 | 한국 시간(KST) 실시간 표시 |
| 로그인 제목 | `관리자 로그인` 제목 노출 | 제목 제거, 중앙 카드형 `계정 접속` 화면 |
| 로그인 후 헤더 | `로그인: admin` | `admin` 처럼 아이디만 표시 |
| 관리자 세션 탭 | 세션/로그인 이벤트 영역이 상대적으로 짧음 | 세로 영역과 목록 가독성 보강 |

### 2.2 1.12.2 검증 기록

| 검증 | 명령/방식 | 결과 |
|---|---|---|
| backend 전체 테스트 | `backend\.venv\Scripts\python.exe -m pytest tests -q` | `268 passed, 3 warnings` |
| frontend typecheck | `npm run typecheck` | 성공 |
| frontend 전체 테스트 | `npm test -- --run` | `313 passed / 66 files` |
| frontend build | `npm run build` | 성공 |
| offline package | `offline_package.bat` | ZIP 생성 성공 |
| release asset | `gh release view 1.12.2` | ZIP + sha256 업로드 확인 |
| health smoke | backend/frontend HTTP | `200 / 200` 확인 |
| browser smoke | 대시보드 | `v1.12.2`, 한국 시간, 날짜 즉시 노출 없음 확인 |

---

## 3. 원격 1.13.0-dev 브랜치 상태

| 항목 | 상태 |
|---|---|
| 브랜치 | `origin/1.13.0-dev` |
| HEAD | `2bac795` |
| 현재 변경 성격 | 계획/증거 메타데이터만 있음 |
| 제품 코드 변경 | 없음 |
| backend/frontend/doc 실제 제품 문서 변경 | 없음. 단, 이 핸드오프 문서 commit 이후에는 docs 변경이 추가됨 |
| 현재 `.omo/boulder.json` 상태 | `blocked` 로 기록됨 |
| 병합 가능 여부 | 지금은 main 병합 금지. 구현/검증 없이 계획만 들어 있음 |

### 3.1 `origin/main..origin/1.13.0-dev` 변경 파일

| 파일 | 상태 | 의미 | 다음 에이전트 판단 |
|---|---|---|---|
| `.omo/boulder.json` | 추가 | OMO 작업 상태. `blocked` 포함 | GJC 표준 상태가 아니므로 참고 정보로만 사용 |
| `.omo/drafts/v1-13-0-operator-experience-plan.md` | 추가 | 1.13.0 계획 초안 | 계획 이력 확인용 |
| `.omo/plans/v1-13-0-operator-experience-plan.md` | 추가 | 상세 실행 계획 | 다음 작업의 주된 입력 |
| `.omo/evidence/task-1-v1-13-0-operator-experience-plan.md` | 추가 | Task 1 QA 증거 | 브랜치 생성 검증 참고 |
| `.omo/start-work/ledger.jsonl` | 추가 | 작업 시작/차단 ledger | repeated worker timeout 이력 확인 |

### 3.2 `.omo` 와 `.gjc` 해석 주의

| 항목 | 설명 |
|---|---|
| `.omo` | 다른 에이전트/도구가 만든 계획·ledger·증거 디렉토리. 현재 1.13.0-dev 의 유일한 변경 묶음이다. |
| `.gjc` | GJC 기본 workflow 런타임 상태 디렉토리. 본 저장소의 AGENTS 문서가 안내하는 현재 GJC 표준이다. |
| 병합 판단 | `.omo` 계획이 존재한다고 해서 GJC 승인/실행 완료를 뜻하지 않는다. 제품 구현 완료 증거로 취급하면 안 된다. |
| 다음 작업 | `.omo/plans/...` 는 강한 참고 계획으로 삼되, 실제 구현은 현재 repo 규칙(`AGENTS.md`, `CLAUDE.md`, `docs/CLOSED_NETWORK_GUIDE.md`)을 우선한다. |

---

## 4. 1.13.0 계획의 의도와 범위

| 구분 | 내용 |
|---|---|
| 목표 | 로그인 후 문서/NSA 진입을 권한 기반으로 자연스럽게 만들고, 계정 메뉴·내 활동·관리자 Overview 상황판·세션/모듈 UX 를 강화 |
| 성격 | minor 후보 (`1.13.0`) — 사용자/관리자 운영 경험 개선 범위가 넓음 |
| 위험도 | Medium — 인증/권한, 관리자 콘솔, 시각화, 일반 사용자 활동 API 가 함께 움직임 |
| 구현 규모 | Large — 여러 파일/모듈/테스트/브라우저 QA 필요 |
| 가장 중요한 guardrail | NSA 권한/ResourceGrant/collection policy 를 절대 약화하지 않음 |
| 의존성 정책 | 새 chart/icon/animation runtime dependency 금지. 기존 Next/Tailwind/SVG 로 구현 |
| 릴리즈 정책 | 개발 중에는 README badge 와 release line 을 `1.13.0` 으로 올리지 않음. release-final commit 에서만 갱신 |

### 4.1 1.13.0 Must have 요약

| 번호 | 요구 | 핵심 파일/영역 | 검증 초점 |
|---:|---|---|---|
| 1 | `1.13.0-dev` 브랜치 보호 | git/worktree | branch/upstream/divergence, dirty path 제외 |
| 2 | `DESIGN.md` 선작성 | root `DESIGN.md` | UI 구현 전 디자인 기준 존재 |
| 3 | 계정 메뉴 | `AdminNavLink`, `Icon`, AppShell | admin-only item, 내 활동, 로그아웃, keyboard/a11y |
| 4 | Document/NSA session-aware nav | AppShell, session route, nsa/doc pages | NSA는 권한자만, 서버 권한 유지 |
| 5 | self activity backend API | auth/admin/AI models and schemas | 본인 데이터만, prompt/answer/snippet 원문 미노출 |
| 6 | normal-user activity UI/login redirect | login form, activity route/API/types | safe `next`, 기본 `/`, error/loading |
| 7 | chart primitives/helpers | admin components/helpers | dependency-free, NaN/empty 방지 |
| 8 | admin Overview default tab | admin tabs/sections | 첫 탭 Overview, 기존 탭 보존 |
| 9 | user/session load visualization | users/sessions sections | 검색/정렬/페이지/autorefresh/purge 유지 |
| 10 | permission-aware module management | module forms/API types | NSA preset, invalid submit 차단 |
| 11 | docs/full regression | README/docs/reports/tests/browser | release badge premature bump 금지 |

---

## 5. 현재 진행 상태 테이블

| 작업 | 상태 | 현재 증거 | 다음 행동 |
|---|---|---|---|
| 1. 브랜치 생성/보호 | 부분 완료 | `.omo/evidence/task-1-...md` 존재, branch `1.13.0-dev` 생성됨 | 현재 작업공간에서 다시 `git status`, upstream, divergence 확인 후 계획 체크박스 갱신 여부 결정 |
| 2. `DESIGN.md` | 미완료 | 파일 없음 | 제품 UI 수정 전 가장 먼저 작성/커밋 |
| 3. 계정 메뉴 | 미완료 | 1.12.2 는 아직 헤더에 아이디 pill + 로그아웃 버튼 | DESIGN.md 후 구현 |
| 4. 권한 기반 nav | 미완료 | 1.12.2 AppShell nav 는 Dashboard/Newsletter/Document 중심 | 계정 메뉴와 함께 구현 |
| 5. self activity backend | 미완료 | API 없음 | backend 테스트 선작성 후 구현 |
| 6. self activity UI/login routing | 미완료 | 1.12.2 로그인 성공은 `/admin` 중심 | backend contract 후 구현 |
| 7. chart primitives/helpers | 미완료 | 별도 chart primitive 없음 | dependency-free component/helper 작성 |
| 8. admin Overview | 미완료 | 1.12.2 관리자 콘솔은 기존 탭 구조 | Overview 기본 탭 추가 |
| 9. user/session load UX | 미완료 | 1.12.2 세션 탭은 세로 보강까지만 완료 | 차트/분포/로드 indicator 추가 |
| 10. module management UX | 미완료 | 권한형 module 필드 UI 부족 | `required_permission/resource_*` 폼 확장 |
| 11. docs/regression | 미완료 | 1.12.2 docs만 최신 | 1.13 구현 후 문서/검증 업데이트 |
| Final wave | 미완료 | 없음 | plan compliance, code review, browser QA, scope fidelity 수행 |

---

## 6. 다음 에이전트 실행 순서

### 6.1 안전 시작 체크리스트

| 순서 | 해야 할 일 | 명령/확인 | 판단 기준 |
|---:|---|---|---|
| 1 | 현재 브랜치 확인 | `git branch --show-current` | `1.13.0-dev` 에서 작업 |
| 2 | 원격 최신화 | `git fetch --all --tags --prune` | fetch 성공 |
| 3 | 동기화 확인 | `git status --short --branch` | `## 1.13.0-dev...origin/1.13.0-dev` clean 또는 의도 변경만 |
| 4 | main 기준 확인 | `git rev-list --left-right --count 1.13.0-dev...origin/main` | 초기 계획 commit 때문에 `0 1` 이상이 정상일 수 있음. 제품 구현 전 차이를 파일 단위로 확인 |
| 5 | 변경 범위 확인 | `git diff --name-status origin/main..HEAD` | `.omo/` + 이 핸드오프 문서/INDEX/CLOSED_NETWORK_GUIDE 정도만 있어야 함 |
| 6 | guardrail 확인 | `AGENTS.md`, `CLAUDE.md`, `docs/CLOSED_NETWORK_GUIDE.md` §14 | 한국어 commit, 보안/배치 위험 신호 숙지 |

### 6.2 권장 첫 커밋

| 단계 | 내용 | 이유 |
|---|---|---|
| A | `DESIGN.md` 작성 | 1.13 계획이 모든 UI 구현 전에 디자인 기준을 요구함 |
| B | `docs/runbook/ai-agent-handoff-2026-07-09.md` 를 참고해 작업 흐름 재확인 | 이 문서가 여러 AI agent 사이의 공통 문맥 역할 |
| C | `DESIGN.md` + 필요한 evidence 만 commit | UI 코드 변경 전 기준 commit을 분리하면 이후 review가 쉬움 |
| D | 계정 메뉴/권한 nav 작업으로 이동 | 사용자-facing 흐름의 기반 |

추천 commit 제목:

```text
v1.13.0 운영 UI 기준을 먼저 고정
```

---

## 7. AI agent 유형별 인수인계 지침

| Agent | 우선 읽기 | 실행 방식 | 주의 |
|---|---|---|---|
| GJC | `AGENTS.md`, `docs/CLOSED_NETWORK_GUIDE.md` §14, 이 문서, `.omo/plans/...` | 명확한 구현 요청이면 직접/역할 agent로 진행. 대규모라면 executor/architect/critic 또는 workflow 사용 | `.omo` 를 GJC runtime state 로 오해하지 말 것. `.gjc` workflow를 새로 쓰면 별도 ledger 관리 |
| Claude Code | `CLAUDE.md`, `AGENTS.md`, 이 문서 | 한국어 commit body + Lore trailer 엄수 | main 직접 release commit 금지, dev branch 유지 |
| Codex | 이 문서, `.omo/plans/...`, `.omo/evidence/...` | `1.13.0-dev` 에서 계획 task 단위 구현 | 기존 `.omo` blocked 상태를 완료로 간주하지 말 것 |
| 사람 운영자 | README, CLOSED_NETWORK_GUIDE, 이 문서 §0-§5 | 1.12.2 안정판 사용, 1.13 계획 승인/범위 조정 | 1.13.0-dev는 아직 배포판 아님 |

---

## 8. 반드시 지켜야 할 금지/위험 신호

| 범주 | 금지/주의 | 이유 |
|---|---|---|
| NSA 권한 | `can_read_collection`, `collections.nsa.read`, `search.nsa.read`, `collection:nsa` ResourceGrant 의미 약화 금지 | 보안 경계 |
| NSA nav | anonymous/plain user 에게 NSA top-level nav 표시 금지 | UI는 힌트일 뿐, 서버 권한도 유지해야 함 |
| dependency | chart/icon/animation runtime dependency 추가 금지 | 폐쇄망 번들 안정성과 크기 |
| UI icon | emoji icon 금지, local SVG icon 사용 | 운영 콘솔 일관성 |
| release version | release-final 전 README badge `1.13.0` 변경 금지 | dev 중 안정판 오인 방지 |
| secrets | `.env`, secret, JWT key, admin password commit 금지 | 보안 |
| generated artifacts | `dist/`, ZIP, `_database/`, `node_modules/`, `.venv/` commit 금지 | 저장소 오염/대용량 |
| batch risk | `setup_offline.bat`, `start_offline.bat`, `offline_package.bat` 위험 신호는 즉시 확인 | 폐쇄망 운영 회귀 방지 |
| audit privacy | normal user 에게 admin audit/global AI 원문 노출 금지 | 권한/개인정보 |
| product scope | 계획 파일만으로 PR merge/release 금지 | 기능 미구현 상태 방지 |

---

## 9. 구현 시 권장 분해

| Wave | 목표 | 권장 산출물 | 검증 |
|---|---|---|---|
| Wave 0 | 기준 고정 | `DESIGN.md`, encoding/copy inventory, evidence | 문서 존재/섹션 grep, product UI 변경 없음 |
| Wave 1 | 계정/네비게이션 | account menu, permission-aware nav, icons | frontend component tests, typecheck |
| Wave 2 | 일반 사용자 활동 | backend `GET /api/v1/auth/activity`, frontend activity UI, login redirect | backend focused tests, frontend tests, browser login |
| Wave 3 | 관리자 상황판 기반 | chart primitives, overview helpers, Overview tab | helper/component tests, admin smoke |
| Wave 4 | 세션/모듈 UX | session/user load charts, module permission presets | Vitest + browser responsive checks |
| Wave 5 | 문서/회귀 | README/docs/report updates, full tests, screenshots/evidence | backend full, frontend typecheck/test/build, browser smoke |

---

## 10. 코드 진실 원천 빠른 지도

| 영역 | 파일/디렉토리 | 확인할 내용 |
|---|---|---|
| App shell/header | `frontend/components/layout/app-shell.tsx` | nav items, active state, Korean clock, account component 위치 |
| Account/login | `frontend/components/layout/admin-nav-link.tsx`, `frontend/components/auth/login-form.tsx` | 현재 1.12.2 헤더/로그인 구조 |
| Version/changelog | `frontend/components/layout/version-badge.tsx`, `frontend/lib/changelog.ts` | `APP_VERSION = CHANGELOG[0].version` |
| Session proxy | `frontend/app/api/frontend/session/route.ts` | frontend session hints |
| Frontend API/types | `frontend/lib/api.ts`, `frontend/lib/types.ts` | fetch helpers, response types |
| Auth backend | `backend/app/modules/auth/api.py`, `schemas.py`, `dependencies.py` | login/logout/me, session cookie, current user |
| Admin models | `backend/app/modules/admin/models.py`, `schemas.py`, `api.py` | users, login events, session activity, service modules |
| Collection policy | `backend/app/modules/collections/policy.py` | NSA access decision |
| AI metadata | `backend/app/modules/ai/models.py`, `api/public.py` | AI request/conversation ownership and metadata |
| Admin UI | `frontend/components/admin/admin-console-tabs.tsx`, `frontend/components/admin/sections/*` | tabs, users, sessions, modules |
| Tests | `backend/tests`, `frontend/tests` | regression contracts |

---

## 11. 검증 명령 표준

| 범위 | 명령 | 기대 |
|---|---|---|
| backend full | `cmd /c ".venv\Scripts\python.exe -m pytest tests -q"` (`backend` cwd) | 1.12.2 기준 `268 passed` |
| frontend typecheck | `cmd /c "npm run typecheck"` (`frontend` cwd) | 성공 |
| frontend tests | `cmd /c "npm test -- --run"` (`frontend` cwd) | 1.12.2 기준 `313 passed / 66 files` |
| frontend build | `cmd /c "npm run build"` (`frontend` cwd) | 성공 |
| local run stop | `cmd /c "scripts\stop_all.bat"` | 기존 window/process 정리 |
| local run start | `cmd /c "start_offline.bat --local --no-pause"` | backend 18437, frontend 29501 ready |
| health | backend `/api/v1/health`, frontend `/` | HTTP 200 |
| release package | `cmd /c "offline_package.bat"` | release-final 때만, `dist/` 는 commit 금지 |

---

## 12. 문서/커밋/PR 규칙 요약

| 구분 | 규칙 |
|---|---|
| commit 언어 | 제목/본문 모두 한국어 |
| commit body | 배경, 접근, 제약, 제외 대안, Lore trailer 포함 |
| Lore trailer | `Constraint`, `Rejected`, `Confidence`, `Scope-risk`, `Directive`, `Tested`, `Not-tested` |
| dev branch | `<버전>-dev` 보존. `1.13.0-dev` 삭제 금지 |
| main merge | release 때 no-ff/merge commit. squash 금지 |
| release badge | release-final 전에는 `README.md` badge 를 `1.13.0` 으로 올리지 않음 |
| docs sync | 사용자/운영자 동작이 바뀌면 README, docs/INDEX, CLOSED_NETWORK_GUIDE, windows-offline, phase report 동기화 |
| evidence | 작업별 `.omo/evidence/task-...md` 또는 GJC 사용 시 `.gjc` ledger를 명확히 분리 |

---

## 13. 추천 다음 작업 상세

| 우선순위 | 작업 | 이유 | 완료 기준 |
|---:|---|---|---|
| 1 | `DESIGN.md` 작성 | UI 구현 전 기준 고정이 계획의 hard gate | root `DESIGN.md` 존재, tokens/charts/accessibility/debt 섹션 포함 |
| 2 | 계정 메뉴 설계/테스트 | 이후 내 활동/관리자 콘솔 진입의 기반 | admin/normal/anon 테스트 통과 |
| 3 | Document/NSA nav 권한화 | NSA 보안과 사용성의 핵심 | NSA 권한자만 nav 표시, 직접 접근 서버 권한 유지 |
| 4 | self activity backend TDD | UI보다 먼저 contract 확정 | 401/본인 데이터/타인 데이터 제외/원문 미노출 테스트 통과 |
| 5 | login redirect 정리 | 1.12.2는 로그인 UI만 개선됐고 routing은 1.13 요구와 다름 | safe next, unsafe external next 차단, 기본 `/` 테스트 |
| 6 | admin Overview/chart primitive | 관리자 콘솔 1.13 핵심 화면 | dependency-free chart + overview default tab |
| 7 | sessions/modules UX | 운영자 체감 개선 | 기존 CRUD/autorefresh/purge 유지 + 새 graph/preview 검증 |
| 8 | full docs/regression | release-ready 판단 | backend/frontend/browser evidence complete |

---

## 14. 사람에게 확인해야 하는 의사결정

| 결정 | 기본 추천 | 사용자 확인이 필요한 이유 |
|---|---|---|
| 1.13.0 전체 계획 실행 여부 | 계획은 타당하지만 Large/Medium이므로 승인 후 진행 | 인증/권한/관리자 콘솔 범위가 넓음 |
| Activity 화면 위치 | `/activity` 단독 route + dashboard summary 추천 | 사용자 동선 선호 차이 |
| Admin Overview 구성 | 기존 summary card 확장 + SVG chart primitive | 화면 밀도/우선순위 결정 필요 가능 |
| Normal user 문서 nav | Document는 로그인 후 표시, NSA는 권한자만 표시 | 사용자에게 Document가 public인지 login-only인지 정책 확인 가능 |
| Release cadence | 1.13.0은 minor release로 진행 | 새 기능/API/UI 포함 |

사용자가 별도 결정을 주지 않으면 계획서의 기본 결정값을 따른다. 단, 보안 경계/의존성 추가/release badge 변경처럼 위험 신호는 임의로 넘기지 않는다.

---

## 15. 다음 에이전트에게 넘기는 짧은 실행 프롬프트

```text
현재 브랜치 `1.13.0-dev` 에서 `docs/runbook/ai-agent-handoff-2026-07-09.md` 와 `.omo/plans/v1-13-0-operator-experience-plan.md` 를 읽고, 제품 UI 수정 전에 root `DESIGN.md` 를 먼저 작성/검증/커밋하세요. 1.12.2는 안정 릴리즈이며 `main`/Release 상태는 완료됐습니다. 1.13.0-dev는 현재 계획/증거만 있고 제품 구현은 없습니다. README 버전 badge는 release-final 전까지 1.12.2로 유지하고, NSA 권한 정책과 ResourceGrant 의미는 절대 약화하지 마세요. 각 작업은 테스트와 evidence를 함께 남기고 한국어 Lore trailer commit 규칙을 지키세요.
```

---

## 16. 최종 상태 판정

| 항목 | 판정 |
|---|---|
| 1.12.2 안정판 | 완료/배포 가능 |
| 1.13.0-dev | 계획 시작됨, 구현 미시작 |
| 현재 핸드오프 문서 | 이 commit 이후 1.13.0-dev 에 존재 |
| 다음 merge/release | 아직 불가 |
| 다음 안전 실행 | `DESIGN.md` 작성 후 task 3-11 순차/병렬 진행 |
