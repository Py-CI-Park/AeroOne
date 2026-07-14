# AI 에이전트 핸드오프 — `feature/dashboard-enhancements` 워크트리

- 작성일: 2026-07-11
- 작성 워크트리: `D:\Chanil_Park\Project\Programming\AeroOne\.worktrees\dashboard-enhancements`
- 브랜치: `feature/dashboard-enhancements` (신규, 원격 없음)
- 기준 커밋: `034bd0324af9f69268d25ae605d9be0fd5c632fb` (`1.13.0-dev` 당시 HEAD, 1.12.2 안정판 이후 상태)
- 대상 독자: 이 워크트리에서 다음에 이어받는 AI code agent(Claude Code, Codex, GJC 등), 사람 운영자
- 목적: 대시보드 새 기능 구현이 왜 별도 워크트리/브랜치로 분리됐는지, 지금 무엇을 해도 되고 무엇을 하면 안 되는지, 이후 병합 시 무엇을 다시 확인해야 하는지를 한 자리에서 파악하게 한다.

---

## 0. 가장 먼저 읽을 결론

| 질문 | 답 |
|---|---|
| 이 워크트리에서 지금 대시보드 기능 코드를 작성해도 되는가? | 예. 다만 §5 기능 범위는 아직 사용자와 확정되지 않았으므로 구현 전 범위부터 좁힐 것 |
| 이 브랜치를 `1.13.0-dev`에 병합해도 되는가? | 아직 안 됨. `1.13.0-dev`의 Task 10 gate(§2)가 통과하기 전까지 보류 |
| `origin`에 push 되어 있는가? | 아니오. 로컬 전용 브랜치 |
| `.omo/plans/v1-13-0-operator-experience-plan.md`를 이 워크트리에서 고쳐도 되는가? | 아니오. 그 계획은 다른 워크트리(main, `.worktrees/1.12.3-hotfix`)에서 활성 진행 중 |
| 이 워크트리와 `.worktrees/1.12.3-hotfix`는 같은 작업인가? | 아니오. 서로 독립. hotfix는 자격증명/패키지 보안 릴리스, 이 워크트리는 대시보드 UI 기능 |
| 커밋 규칙이 다른가? | 아니오. `AGENTS.md`/`CLAUDE.md` 저장소 규칙은 이 워크트리에도 동일하게 적용 |

---

## 1. 이 워크트리의 위치와 관계

이 저장소는 현재 여러 워크트리가 동시에 존재한다 (`git worktree list` 기준):

| 경로 | 브랜치 | 용도 |
|---|---|---|
| `D:\Chanil_Park\Project\Programming\AeroOne` (main worktree) | `1.13.0-dev` | v1.13.0 운영 경험 계획의 조율/상태 관리 (`.omo/boulder.json`, ledger) |
| `.worktrees/1.12.3-hotfix` | `main` | v1.13.0 계획 Wave 0-1: 자격증명 회전·공개 패키지 보안(Task 1-9), 진행 중 |
| `.worktrees/task3-qa-r3`, `.worktrees/task3-review-r3` | detached | Task 3 (자격증명 회전 도구) 리뷰/QA 전용 임시 워크트리 |
| **`.worktrees/dashboard-enhancements` (여기)** | **`feature/dashboard-enhancements`** | **대시보드 새 기능 구현 — 이 문서의 대상** |

이 워크트리는 `1.13.0-dev`의 당시 HEAD(`034bd03`)에서 분기했지만, **그 브랜치의 활성 계획에는 참여하지 않는다.** 운영자가 명시적으로 "별도 독립 브랜치로 병행"을 선택했다.

---

## 2. 왜 `1.13.0-dev`에 바로 얹지 않았는가

`.omo/boulder.json` 기준 저장소의 활성 작업은 `v1-13-0-operator-experience-plan` (상태 `active`)이며, `.omo/plans/v1-13-0-operator-experience-plan.md`의 TODO 27개 + Final 6개가 순서/의존성으로 묶여 있다. 이 워크트리를 만든 시점 상태:

- Task 1-2 (proven-unsafe 1.12.2 자산 봉쇄, 46개 release 재감사): 완료(`[x]`).
- **Task 3 (DB-aware 자격증명 회전 도구, TDD)**: `.worktrees/1.12.3-hotfix`에서 진행 중이나 **3차 리뷰까지 모두 FAIL** (`.omo/start-work/ledger.jsonl` 참고, 최근 blocking classes: `ordinary-user-acl-privilege`, `recovery-journal-crash-window`, `service-restart-toctou` 등). 워크트리는 현재 dirty(미커밋 수정 중).
- Task 4-9 (자격증명 실제 회전, 공개 패키지 policy/builder, 내부 데이터 bundle, Next.js 패치, 1.12.3 릴리스): 미시작.
- **Task 10** (`1.12.3` hotfix 계보를 `1.13.0-dev`에 병합) — 계획 원문: *"이 gate 이후에만 제품 파일 수정 허용"*.
- Task 11-19 (UI/QA 기반, 인증/활동 흐름): 미시작.
- **Task 20-24 (관리자 backend/frontend — Overview/users/sessions/modules, 즉 "대시보드" 확장)**: Task 10-19에 의존, 미시작.

즉 저장소의 대시보드 확장은 원래 계획상 Task 20-24이고, 그 앞에 보안 릴리스(Task 3-9)와 UI/인증 기반(11-19)이 순서대로 끝나야 한다. 그 순서를 기다리지 않고 지금 바로 대시보드 기능을 만들기 위해, **계획 밖의 독립 브랜치**로 이 워크트리를 분리했다.

---

## 3. 이 워크트리에서 하지 말아야 할 것

| 하지 말 것 | 이유 |
|---|---|
| `.omo/plans/v1-13-0-operator-experience-plan.md`, `.omo/boulder.json`, `.omo/start-work/ledger.jsonl`, `.omo/evidence/v1-13-0/**` 수정 | main worktree에서 활성 관리 중인 상태 파일. 이 워크트리에서 건드리면 다른 워크트리의 상태와 충돌 |
| `.worktrees/1.12.3-hotfix`의 자격증명 회전 코드(`backend/app/commands/credential_rotation_transaction.py`, `scripts/credential_rotation/*`) 이식/참조 | 아직 3차 리뷰 실패 중인 미검증 코드. 이 브랜치 목적과 무관 |
| `feature/dashboard-enhancements`를 지금 `1.13.0-dev`에 병합하거나 `main`으로 병합 | Task 10 gate 통과 전. 병합 판단은 사람 운영자 승인 필요 |
| `1.13.0-dev` 삭제/재작성, 이 브랜치의 강제 rebase | 저장소 전역 규칙(`AGENTS.md` §9, `CLAUDE.md` §2.6) — dev 브랜치 보존 절대 |

---

## 4. 대시보드 관련 코드 진실 원천

| 영역 | 파일 | 무엇을 |
|---|---|---|
| 대시보드 카드/데이터 원천 | `backend/app/modules/admin/api.py` (`service_modules`), `frontend/app/page.tsx` | 대시보드 카드를 `service_modules` DB에서 읽음. active/development/coming_soon, 설명, 링크, 정렬, 외부 링크 조정. DB/table 미준비 시 degraded banner + 내장 fallback |
| 대시보드 개별 카드 컴포넌트 | `frontend/components/dashboard/notebook-link-card.tsx` | 대시보드 카드 패턴 예시 (Open Notebook 링크 카드) |
| App shell/헤더 | `frontend/components/layout/app-shell.tsx` | nav items, active state, 헤더 시계, 계정 메뉴 위치 |
| 버전 배지 | `frontend/components/layout/version-badge.tsx`, `frontend/lib/changelog.ts` | `APP_VERSION = CHANGELOG[0].version` |
| 관리자 콘솔 | `frontend/app/admin/page.tsx`, `frontend/components/admin/admin-console-tabs.tsx`, `frontend/components/admin/sections/*` | 탭형 관리자 콘솔 (Users/Sessions/Modules/Audit 등 기존 탭) |
| 관리자 RBAC/백엔드 | `backend/app/modules/admin/models.py`, `schemas.py`, `api.py`, `backend/app/modules/auth/dependencies.py` | 권한 체크, `service_modules` 테이블, audit 기록 패턴 |
| 프론트 API 프록시 | `frontend/app/api/frontend/admin/`, `frontend/lib/api.ts`, `frontend/lib/types.ts` | same-origin 프록시, fetch helper, 타입 |
| 홈 페이지 테스트 | `frontend/tests/app/home-page.test.tsx` | fallback 대시보드 구성 회귀 계약 |

가장 정확한 최신 지도는 `docs/INDEX.md` §6 "코드 진실 원천"을 참고 (이 워크트리에도 동일 파일 존재, `034bd03` 기준).

---

## 5. 참고: 계획의 Wave 4 대시보드 관련 항목 (구속력 없음, 참고용)

`.omo/plans/v1-13-0-operator-experience-plan.md`의 Task 20-24는 이 워크트리와 **직접 연결되지 않지만**, "대시보드 새 기능"의 범위를 좁힐 때 참고할 기존 설계 의도다:

| Task | 내용 요지 |
|---|---|
| 20-21 | 관리자 backend overview 집계, 실세션 집계 (24시간 current/previous window, 값 위조 금지) |
| 22 | 관리자 frontend Overview 화면 (기존 summary card 확장 + dependency-free SVG chart primitive, 새 chart/icon/animation runtime dependency 금지) |
| 23 | 사용자/세션 화면 (검색/정렬/페이지, 세션 15초 scoped refresh, 실제 카운트) |
| 24 | 모듈 정책 화면 (Document/NSA preset, server-side merged state 검증, 실패 시 mutation/audit 없음) |

**주의**: 이 항목들을 그대로 구현 대상으로 삼을지, 아니면 운영자가 요청한 다른 "새로운 기능"인지는 **아직 확정되지 않았다.** 다음 에이전트는 구현 전에 반드시 운영자와 정확한 기능 범위를 확인해야 한다.

---

## 6. 다음 에이전트 실행 순서

1. `git status`, `git log --oneline -5`로 이 워크트리가 여전히 `034bd03` 기준 clean 상태인지 확인.
2. 운영자에게 "대시보드 새로운 기능"의 구체 범위를 확인 (§5 참고 항목을 제안하되 강제하지 않음).
3. 범위 확정 후 `AGENTS.md`/`CLAUDE.md`의 커밋·PR·검증 규칙에 따라 통상 TDD 흐름(RED→GREEN)으로 구현.
4. 완료 후 병합은 별도로 판단 — `1.13.0-dev`의 Task 10 gate 상태를 다시 확인한 뒤 운영자 승인 하에 병합 전략(그대로 rebase merge할지, 계획에 재편입할지)을 정한다. 이 문서 작성 시점에는 병합 계획이 없다.

---

## 7. 검증 명령 표준 (저장소 공통, 1.12.2 기준 참고값)

| 범위 | 명령 | 기대 |
|---|---|---|
| backend full | `cmd /c ".venv\Scripts\python.exe -m pytest tests -q"` (`backend` cwd) | 회귀 0 |
| frontend typecheck | `cmd /c "npm run typecheck"` (`frontend` cwd) | 성공 |
| frontend tests | `cmd /c "npm test -- --run"` (`frontend` cwd) | 회귀 0 |
| frontend build | `cmd /c "npm run build"` (`frontend` cwd) | 성공 |

---

## 8. 커밋/문서 규칙 요약

| 구분 | 규칙 |
|---|---|
| commit 언어 | 제목/본문 모두 한국어 |
| commit body | Claude Code는 3문단 이상: 배경 / 선택한 접근 / 검토하고 제외한 대안 (`CLAUDE.md` §2.1) |
| Lore trailer | `Constraint`, `Rejected`, `Confidence`, `Scope-risk`, `Directive`, `Tested`, `Not-tested` — `Tested`/`Not-tested`는 실행 명령과 출력 요지 포함 (`CLAUDE.md` §2.2) |
| 문서 갱신 | 새 문서 추가/본문 대폭 변경 시 같은 commit에서 `docs/INDEX.md` 해당 섹션도 갱신 (`CLAUDE.md` §2.5) |
| 브랜치 보존 | `1.13.0-dev` 등 `<버전>-dev` 브랜치 삭제 금지. 이 브랜치(`feature/dashboard-enhancements`)도 운영자 명시 요청 없이 삭제하지 않음 |

이 문서 자체도 §2.5 규칙에 따라 `docs/INDEX.md`에 함께 색인했다.
