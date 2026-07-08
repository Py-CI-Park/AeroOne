---
slug: v1-13-0-operator-experience-plan
status: complete
intent: unclear
pending-action: write .omo/plans/v1-13-0-operator-experience-plan.md
approach: v1.13.0-dev 브랜치에서 인증 후 문서/NSA 진입, 계정 메뉴, 일반 사용자 활동, 관리자 통합 대시보드와 모듈/사용자/세션 UX를 하나의 운영자 경험 개선 묶음으로 개발한다.
---

# Draft: v1-13-0-operator-experience-plan

## Components (topology ledger)
| id | outcome | status | evidence path |
| --- | --- | --- | --- |
| C1 | `1.13.0-dev` 작업 브랜치와 디자인 시스템 기준을 먼저 고정한다. | active | `.omo/evidence/task-1-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-2-v1-13-0-operator-experience-plan.md` |
| C2 | 로그인 후 Document/NSA 네비게이션과 계정 메뉴를 세션/권한 기반으로 재구성한다. | active | `.omo/evidence/task-3-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-4-v1-13-0-operator-experience-plan.md` |
| C3 | 일반 사용자가 자기 최근 활동을 볼 수 있는 self-scoped API와 화면을 만든다. | active | `.omo/evidence/task-5-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-6-v1-13-0-operator-experience-plan.md` |
| C4 | 관리자 콘솔에 Overview 기본 탭과 상태 시각화 그래프를 추가한다. | active | `.omo/evidence/task-7-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-8-v1-13-0-operator-experience-plan.md` |
| C5 | 사용자/세션 로드와 모듈 관리 UX를 운영자가 쓰기 쉬운 밀도 높은 화면으로 개선한다. | active | `.omo/evidence/task-9-v1-13-0-operator-experience-plan.md`, `.omo/evidence/task-10-v1-13-0-operator-experience-plan.md` |
| C6 | 문서, 회귀 테스트, 폐쇄망/브라우저 smoke를 v1.13.0 릴리즈 게이트에 맞춘다. | active | `.omo/evidence/task-11-v1-13-0-operator-experience-plan.md`, `.omo/evidence/final-v1-13-0-operator-experience-plan.md` |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
| --- | --- | --- | --- |
| UI/차트 라이브러리 | 새 런타임 의존성을 추가하지 않고 기존 Tailwind/CSS/SVG/로컬 `Icon` 시스템을 확장한다. | 폐쇄망 ZIP 패키징과 node_modules 번들 안정성이 핵심이다. | yes |
| NSA 노출 | 로그인 후에도 `collections.nsa.read` 또는 `collection:nsa` 권한이 있는 사용자에게만 NSA 탭을 보인다. | 백엔드 `can_read_collection` 정책을 약화하면 보안 회귀다. | no for this scope |
| 로그인 성공 이동 | 모든 사용자를 `/admin`으로 보내지 않고 기본 `/`로 보낸 뒤 계정 메뉴에서 관리자 콘솔로 진입한다. | 일반 사용자 활동 화면과 관리자 메뉴 요구를 모두 만족한다. | yes |
| 일반 사용자 최근 작업 | 새 스키마보다 기존 `LoginEvent`, `UserSessionActivity`, `AiRequestLog`, 현재 AI 대화 세션을 self API로 묶는다. | user-scoped 조회가 가능하고 데이터 마이그레이션 위험이 낮다. | yes |
| 디자인 방향 | 사내 운영 콘솔이므로 마케팅 랜딩처럼 만들지 않고, 로그인 화면만 더 풍부한 command-center 스타일로 고도화한다. | 반복 업무 UI는 밀도와 스캔성이 우선이다. | yes |
| 관리자 콘솔 | 기존 탭을 제거하지 않고 `overview` 탭을 첫 탭/기본값으로 추가한다. | 기존 운영 동선을 보존하면서 통합 상황판을 제공한다. | yes |
| 버전 표기 | 개발 초기에 README badge를 `1.13.0`으로 바꾸지 않고 릴리즈 직전 버전 커밋에서만 갱신한다. | 저장소 릴리즈 사이클 규칙과 맞춘다. | yes |

## Findings (cited - path:lines)
- Git: 현재 `main...origin/main`, 최신 태그 `1.12.2`, `1.13.0-dev` 브랜치 없음. 작업 전 `git switch -c 1.13.0-dev origin/main` 필요.
- Dirty worktree risk: 현재 `.omo/`, `_codex_exports/`, `pkg264_082120*`, `pkg264_082225*` 가 untracked. 실행자는 제품 작업 중 이 파일들을 커밋 대상에서 제외해야 한다.
- 디자인 시스템: `DESIGN.md`/`design-system.md`/`design-tokens.md` 검색 결과 없음. UI 구현 전 디자인 시스템 파일 생성 필요.
- `frontend/package.json:6-10`, `frontend/package.json:13-30`: Next 15.2.0 + React 19 + Tailwind 3.4.17 + Vitest, 별도 아이콘/차트 런타임 없음.
- `frontend/components/ui/icons.tsx:1`: 로컬 currentColor SVG 아이콘 시스템 존재. 새 관리자/활동/차트 아이콘은 여기 확장.
- `frontend/components/layout/app-shell.tsx:13-17`, `frontend/components/layout/app-shell.tsx:69-103`: 상단 nav는 Dashboard/Newsletter/Document 고정, NSA active 상태 없음, 우측은 `AdminNavLink`.
- `frontend/components/layout/admin-nav-link.tsx:21-88`: 사용자명, Admin 링크, 로그아웃이 한 줄에 직접 노출됨.
- `frontend/components/auth/login-form.tsx:15-16`: 로그인 성공 후 항상 `/admin` 이동.
- `backend/app/modules/admin/api.py:80`, `backend/app/modules/admin/api.py:353-379`: `document`/`nsa` service module과 권한 필터가 이미 존재.
- `backend/app/modules/collections/policy.py:9-29`: document/civil은 public, nsa는 권한 사용자만 허용.
- `frontend/components/admin/admin-console-tabs.tsx:217-244`, `frontend/components/admin/admin-console-tabs.tsx:513-522`: 관리자 콘솔은 9개 탭이며 기본 탭은 `modules`, 별도 overview 탭 없음.
- `frontend/components/admin/admin-console-tabs.tsx:75`, `frontend/components/admin/sections/admin-modules-section.tsx:174-198`, `backend/app/modules/admin/schemas.py:155-157`: backend는 모듈 권한 필드를 제공하지만 frontend module draft/UI는 `required_permission/resource_type/resource_id`를 노출하지 않음.
- `frontend/components/admin/sections/admin-sessions-section.tsx:25-26`, `frontend/components/admin/sections/admin-sessions-section.tsx:104-139`: 세션/로그인 이벤트 UI는 존재하지만 세로 영역과 시각화가 제한적.
- `backend/app/modules/auth/api.py:79-89`, `backend/app/modules/admin/models.py:87-121`, `backend/app/modules/admin/models.py:148-162`: 자기 활동 API는 로그인 이벤트, 세션 활동, AI 요청 로그를 기반으로 구성 가능.
- `backend/app/modules/ai/models.py:24-40`, `backend/app/modules/ai/repositories.py:21-32`, `backend/app/modules/ai/api/public.py:266-279`: AI 대화는 세션 소유 기반으로 목록화되어 있고, `user_id` 컬럼은 nullable로 준비되어 있음.

## Decisions (with rationale)
- 이 계획은 `intent: unclear` 로 유지한다. 사용자가 "잘 생각해서 고도화"를 요청했으므로 추가 질문 대신 저장소 제약과 운영 UI 모범값을 채택한다.
- 서브에이전트 Metis/Momus 리뷰는 현재 도구 정책상 사용자가 명시적으로 "서브에이전트/병렬 에이전트"를 요청하지 않아 실행하지 않는다. 대신 계획 자체에 F1-F4 최종 검증과 실행자 QA 증거를 강제한다.
- 새 dependency는 금지 기본값으로 둔다. Lucide/차트 라이브러리는 사용자가 별도 승인할 때만 도입한다.
- self activity는 관리자 audit 전체를 일반 사용자에게 노출하지 않는다. 일반 사용자는 자기 로그인/세션/AI 요청/현재 AI 대화/접근 가능 모듈만 본다.
- Newsletter read tracking은 IP 기반이므로 "내 최근 작업"으로 표시하지 않는다. 향후 user_id 기반 read tracking을 별도 기능으로 확장할 수 있다.
- 관리자 콘솔 Overview는 기존 9개 탭 위에 추가되는 10번째 구조가 아니라 첫 번째 `overview` 탭이다. 숫자 단축키는 `1=Overview`부터 다시 매핑하고 10번째 탭은 `0` 또는 단축키 없음 중 구현 시 하나로 고정한다.

## Scope IN
- `1.13.0-dev` 브랜치 생성.
- `DESIGN.md` 추가.
- 로그인 UI 고도화와 깨진 한글 문구 정리.
- 세션/권한 기반 Document/NSA nav 노출.
- 계정 메뉴 컴포넌트: 내 활동, 관리자 콘솔, 로그아웃.
- 일반 사용자 최근 활동 API/프론트 화면.
- 관리자 Overview 탭과 SVG/CSS 기반 그래프.
- 사용자/세션 로드 시각화와 세로 패널 확장.
- 모듈 관리 탭의 권한형 모듈 필드/프리셋/미리보기 UX.
- 테스트, 문서, 폐쇄망 smoke 가이드 갱신.

## Scope OUT (Must NOT have)
- NSA 권한 우회, 공개화, 비밀번호식 가림막 회귀.
- 새 런타임 UI/차트 dependency 추가.
- README 버전 badge를 릴리즈 전 조기 변경.
- `.env`, 관리자 비밀번호, JWT secret, `_database/`, `dist/`, ZIP 산출물 커밋.
- 관리자 감사 로그 원문 또는 AI prompt/answer/snippet을 일반 사용자 화면에 노출.
- 랜딩 페이지식 hero/마케팅 화면.

## Open questions
- 없음. 승인된 기본값으로 계획을 작성한다.

## Approval gate
status: approved
approved-by-user: "승인"
approved-action: write `.omo/plans/v1-13-0-operator-experience-plan.md`
