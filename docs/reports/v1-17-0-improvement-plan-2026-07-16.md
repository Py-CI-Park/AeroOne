# AeroOne 1.17.0 개선 계획 보고서 (2026-07-16)

- 근거: [`v1-16-3-full-audit-2026-07-16.md`](v1-16-3-full-audit-2026-07-16.md) 전수 검사
- 원칙: 폐쇄망 순도(외부 요청 0)·sanitize 단일 원천·fail-closed 경계를 깨지 않는 범위에서 **사용자 체감 품질** 우선

---

## P0 — 즉시 (hotfix 사이클, 코드 대부분 완료)

### P0-1. Leantime 스택 hotfix 게시 (1.16.4)
- [x] 파스 사망·비밀번호 `!` 훼손·localhost APP_URL 수정 (`678440a`)
- [x] 배치 회귀 테스트 7건, 스택 ZIP 재빌드 (`AeroOne-Leantime-Stack-v3.9.8-20260716-212615.zip`, sha256 `2667088d94f1…`)
- [x] `/leantime` 페이지 IIS 안내 → 포터블 스택 안내 교정, 런북 갱신
- [ ] **운영자 액션**: 폐쇄망 실 PC 에서 새 ZIP 반입 재검증 → `1.16.4` hotfix 릴리스에 새 스택 asset 게시 + README 반입 절 digest 갱신 (기존 1.16.3 asset 은 immutable 이라 교체 불가, 새 릴리스 필요)

### P0-2. 빨간 스위트 정상화 + 릴리스 게이트 의무화 (프로세스)
- [x] 1.16.3 이 남긴 backend 28건 실패(발급 계정 전체 접근 정책 미반영 스테일 테스트)를 새 정책 기준으로 전량 수리 — 권한 없는 인증 주체의 403 경로는 `pending` 계정으로 재현, 발급 계정 기본 보유 + `admin.*` 관리 권한 admin 전용 단언으로 갱신. 수리 후 **backend 1,179 passed / 0 failed**.
- 릴리스 체크리스트에 추가: *병합 전 backend 전체 pytest + frontend vitest/tsc 전량 실행*(부분 실행·"여유 PC에서 추후" 금지), *스택/번들류 반입물은 게시 전 본 PC 에서 setup→start→로그인 E2E 1회 필수*. "⚠ 운영자 검증 필요" 주석은 게시 차단 사유로 승격.
- `AGENTS.md` §9.3 검증 게이트에 반입물 E2E 행 추가 + §8 테스트 수치를 1,179/540 으로 현행화.

### P0-3. 개발 환경 드리프트 방지
- `setup.bat`/문서에 frontend 의존성 복원을 `npm ci`(lockfile 고정)로 명시. tsc 게이트 실행 전 node_modules 검증 한 줄 추가.

---

## P1 — 다음 minor (1.17.0) : 사용자 체감 3대 개선

### P1-1. Office 차트 "대화형 컴포저" (감사 §7 — 사용자 지정 최우선 과제)
현재 8+ 결정 요소가 펼쳐진 폼을, LLM 챗 멘탈모델의 **단일 컴포저**로 재편한다.

**목표 UX**
```
┌──────────────────────────────────────────────┐
│ [📎 파일 첨부·드롭]  region,sales… (또는 붙여넣기) │
│ "지역별 매출을 크기순 가로 막대로"                │
│                                    [보내기 ▶] │
└──────────────────────────────────────────────┘
  ↓ 생성 결과(차트) 아래에 후속 입력창 유지
  "상위 5개만" → 같은 데이터로 재생성 (대화형 반복)
```
- 컴포저 1개 = 멀티라인 textarea + 첨부 버튼 + 드래그앤드롭 + 붙여넣기 감지(현행 파일/텍스트 모드 토글 제거). 첨부·텍스트 감지 시 자동 inspect 하여 칩(열 이름·타입)으로 표시 — 별도 "데이터 미리보기" 버튼 제거.
- 후속 명령은 동일 데이터 + 이전 spec 을 컨텍스트로 서버에 전달(신규 `refine` 파라미터: 이전 ChartSpec + 사용자 문장 → 규칙/LLM 이 spec 패치). LLM 부재 시 규칙 기반 패치(정렬/방향/limit/유형 키워드)로 동작 — 폐쇄망 무 LLM 환경에서도 성립.
- 고급 설정 패널·예제 피커·차트 유형 select 는 컴포저 아래 접힘으로 보존(파워유저·결정적 재현 경로 유지, 기존 manualSpec 계약 불변).
- 서버 계약 변경 최소: `POST /charts/generate` 에 `previous_spec`(옵션) 추가만. 검증·한도·산출물 경로 계약 그대로.
- 회귀: 기존 chart-page 테스트 14건 유지 + 컴포저/refine 신규 테스트. 동일 패턴을 다이어그램 폼에 2차 적용.

### P1-2. AeroAI 스트리밍 + 파일 첨부 질문
- Ollama/OpenAI 호환 모두 스트리밍 지원 — 백엔드 `stream: True` + SSE 프록시(`StreamingResponse`), same-origin BFF 경유 유지. 첫 토큰까지의 침묵 제거가 목적.
- "파일 첨부해서 질문": 업로드 파일(텍스트/CSV/md)을 대화 컨텍스트로 1회성 주입(저장소 미기록, office upload 한도 재사용). P1-1 컴포저와 UI 패턴 공유.
- `ai-chat-workspace.tsx`(41KB) 를 composer/messages/citations/scope 로 분해하면서 진행.

### P1-3. 상태 가시성 통일
- Notebook/OpenWebUI 카드에 Leantime 식 경량 헬스 배지(백엔드 loopback probe, 폐쇄망 순도 유지). 죽은 링크 클릭 제거.
- 대시보드에 "최근 본 문서/뉴스레터" 스트립(read_tracking 데이터 재사용, 신규 테이블 불필요).

---

## P2 — 1.17.x ~ 1.18.0

### P2-1. Civil v1.8 — SVG·로딩 개선 (감사 §5 집중 연구 후속)
1. **상호작용**: 문자열 SVG 를 유지하되 위임 이벤트(iframe 내 스크립트)로 hover 치수 툴팁 + overlay 기체 강조 + 클릭→백과 딥링크.
2. **내보내기**: 비교 시트/overlay PNG·SVG 다운로드 버튼(Office 차트와 동일한 canvas 직렬화 패턴).
3. **형상 충실도**: 제조사·세대별 실루엣 프리셋 8~10종(파라메트릭 위에 패밀리 경로 오버라이드). "not a controlled drawing" 면책 유지, 비추정 원칙 불변.
4. **로딩**: 데이터 번들(330KB JS + 485KB JSON) lazy 분리 — 포털 첫 화면은 메타만, 백과/비교 진입 시 로드.
5. side view 날개 스윕 반영, 엔진 파일런 형상 보정.

### P2-2. 관리자 콘솔 리모델링
- IA 재편: `개요 / 계정(사용자·RBAC·세션) / 콘텐츠(모듈·분류·검색) / 시스템(상태·설정) / AI / 감사·백업` 5~6 그룹. 딥링크(`?tab=`) 하위호환 유지.
- **탭 진입 시 lazy fetch** 로 전환(마운트 시 17종 일괄 fetch 제거). 개요 위젯에서 해당 그룹 딥링크.
- `admin-console-tabs.tsx` 컨테이너를 그룹 단위 파일로 분해(진행 중인 sections/ 분해 완결). 기존 28건 콘솔 테스트 그린 유지가 완료 조건.

### P2-3. 컬렉션 품질
- NSA `0000` 가림막 → `collections.nsa.read` 권한 게이트로 승격(1.8+ RBAC 존재하므로 장식 제거). 기존 gate 컴포넌트는 권한 없는 계정 안내로 전환.
- 문서 목록 메타(수정일) 표시 + 트리 펼침 상태 sessionStorage 보존 + 뉴스레터 이전/다음 내비.

### P2-4. 성능 예산 도입
- v1.13 Lighthouse 러너를 릴리스 게이트로 승격: 대시보드/뉴스레터/Civil 3 경로에 예산(예: FCP<1.5s LAN, JS<500KB/route) 기록을 phase 보고서에 첨부.
- Leantime PHP built-in server 단일 워커 한계를 런북에 명시(동시 5인+ 필요 시 Caddy+FastCGI 반입 검토 항목으로).

### P2-5. 부채 정리 (기회 있을 때)
- pydantic class-config 3건 → ConfigDict, pytest-asyncio loop_scope 설정, AccountMenu act() 경고 정리.
- `office_tools/api/jobs.py`(2,355줄)·`admin/api.py`(50.9KB) 서비스 계층 분해 — 1.13 collection policy 리팩터와 같은 characterization-first 방식.
- passlib+bcrypt 핀 장기 대체 검토(pwdlib 등) — major 사이클 안건.

---

## 사이클 배치 제안

| 릴리스 | 내용 | 분류 |
|---|---|---|
| **1.16.4** | P0-1 Leantime hotfix asset 게시 (+P0-2/3 문서) | hotfix |
| **1.17.0** | P1-1 차트 컴포저, P1-2 AI 스트리밍·첨부, P1-3 상태 배지 | minor |
| **1.17.x** | P2-3 컬렉션 품질, P2-5 부채 일부 | patch |
| **1.18.0** | P2-1 Civil v1.8, P2-2 관리자 리모델링, P2-4 성능 예산 | minor |

각 minor 는 AGENTS §9.6 에 따라 정식 PR + phase 보고서 1건 이상과 함께 진행한다.
