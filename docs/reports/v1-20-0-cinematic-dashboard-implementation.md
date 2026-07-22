# 1.20.0 시네마틱 항공 대시보드 구현 결과

- 분류: minor (`1.20.0`) UX/UI 고도화
- 기준 브랜치: `1.20.0-dev`
- 기능 브랜치: `feature/cinematic-dashboard`
- 시작 시각: `2026-07-22T22:20:15.9469460+09:00`
- 시작 기준 commit: `6efea8a9c5f51b5c9b444cb1a8dcafa045acab1d` (`시네마틱 항공 대시보드 연구 브랜치를 병합한다`)
- 종료 시각: `2026-07-22T23:19:29.2039917+09:00`
- 경과 시간: 약 59분 13초
- 구현 commit: `53028f7` (`항공 정체성과 업무 진입을 결합한 Flight Deck 대시보드를 구현한다`)
- 최종 병합 commit: `1.20.0-dev` no-ff 병합 후 Git 이력과 최종 결과 안내에 기록

## 1. 목표

1. 기존 Server Component, RBAC, degraded fallback 계약을 보존한다.
2. 홈 상단에 AeroOne의 항공 정체성을 전달하는 컴팩트 히어로를 추가한다.
3. 실제 권한을 통과한 핵심 모듈만 Featured 진입점으로 표시한다.
4. 영상·WebGL·신규 런타임 dependency 없이 포스터와 CSS 2.5D로 구현한다.
5. 모션 감소, 키보드 탐색, 저사양 환경에서도 업무 기능을 유지한다.
6. 기존 Recent Reads와 전체 모듈 그리드를 그대로 보존한다.

## 2. 기준 연구

- [`v1-20-0-cinematic-dashboard-research.md`](v1-20-0-cinematic-dashboard-research.md)
- 연구 결론: TravelX·Avora 계열 날개/구름 구도를 시각 언어로 사용하되, 실제 DOM 모듈과 기존 권한 경계를 유지하고 홈 Three.js·GSAP·가상 기능 카드는 제외한다.

## 3. 구현 변경

### 3.1 화면과 정보 구조

- 기존 `/` Server Component가 쿠키·테마·신원·서비스 모듈을 병렬 조회하는 구조를 유지했다.
- `DashboardAuth` resolver를 추가해 `/auth/me` 1회로 익명·일반 사용자·관리자와 username을 fail-closed 판정한다.
- 홈 제목 블록 대신 컴팩트 `CinematicHero`를 추가하고 본문 폭을 `max-w-7xl`로 확장했다.
- 히어로 아래의 degraded 경고, `RecentReadsStrip`, 전체 섹션별 `ServiceCard`·`ExternalLauncherCard`는 보존했다.
- 기존 active/coming-soon 수치를 히어로 안에 실제 필터 결과로 표시했다.

### 3.2 권한 기반 Featured

Featured 우선순위는 `civil-aircraft` → `ai` → `aero-work` → `newsletter`이며 다음 조건을 모두 만족한 항목만 최대 4개 표시한다.

1. 백엔드 또는 보수적 fallback 필터를 이미 통과했다.
2. `is_enabled=true`다.
3. 외부 런처가 아닌 내부 DOM 링크다.
4. 실제 결과에 존재한다.

따라서 익명 실데이터 화면에서는 Civil Aircraft와 Newsletter 두 개만 표시됐고, 테스트의 관리자 fixture에서는 Civil Aircraft·AeroAI·Aero Work·Newsletter 네 개가 순서대로 표시됐다. 미구현 Digital Twin·Composite Wiki·범용 AI Command와 가짜 시스템 상태는 추가하지 않았다.

### 3.3 로그인별 UX

| 상태 | 표시 |
|---|---|
| 익명 | 플랫폼 소개, `AeroOne 로그인` CTA, 공개 Featured |
| 일반 사용자 | `{username}님, 업무를 이어가세요.`, 로그인 CTA 제거, 권한 모듈 |
| 관리자 | `{username}님, 서비스 운영 현황을 확인하세요.`, 관리자에게 반환된 권한 모듈 |
| 인증·백엔드 실패 | 익명으로 fail closed, fallback의 permission-gated 항목 제거 |

### 3.4 시각·접근성

- 오리지널 generic twin-engine civil-airliner 포스터를 생성하고 1599×900 WebP 31,616 bytes로 최적화했다.
- 자산 SHA-256 `ada5e0b7330cff0d7e5ef67153ebbbc2e6423a381de1eefe45c7c91d3de91732`, 생성 provenance와 비인증 공학 참고 제한을 자산 옆 TXT에 기록했다.
- 밝은 하늘에서도 흰 글자가 유지되도록 선형·방사형·하단 오버레이를 겹쳤다.
- Featured 카드는 132px 이상, hover/focus에서 최대 `translateY(-4px) rotateX(2deg) rotateY(-2deg)`만 적용했다.
- 모든 빠른 실행을 실제 `Link` DOM으로 유지하고 기능별 한국어 접근성 이름과 3px focus outline을 제공했다.
- `prefers-reduced-motion: reduce`에서 애니메이션·transition·transform을 제거했다.
- 영상, Canvas, WebGL, Motion, GSAP, Three.js 등 신규 runtime dependency는 0개다.

### 3.5 변경 파일

| 영역 | 파일 |
|---|---|
| 홈 조립 | `frontend/app/page.tsx` |
| 히어로 | `frontend/components/dashboard/cinematic-hero.tsx` |
| 신원 판정 | `frontend/lib/server-auth.ts` |
| 스타일 | `frontend/app/globals.css` |
| 자산 | `frontend/public/media/aeroone-flight-deck.webp`, `AEROONE-FLIGHT-DECK-ASSET.txt` |
| 버전 안내 | `frontend/lib/changelog.ts` |
| 테스트 | `frontend/tests/app/home-page.test.tsx`, `frontend/tests/lib/server-auth.test.ts`, `frontend/tests/components/version-badge.test.tsx` |

## 4. 1.19.1 대비 UX/UI 변화

| 항목 | 1.19.1 | 1.20.0 구현 결과 |
|---|---|---|
| 첫인상 | 단색 제목과 동일 크기 카드 그리드 | 항공기 날개·구름 Flight Deck 히어로 |
| 빠른 진입 | 섹션에서 카드를 찾아 이동 | 권한 기반 Featured 최대 4개 |
| 로그인 표현 | 헤더 계정 메뉴 중심 | 히어로 카피와 CTA도 익명·사용자·관리자로 분기 |
| 카드 계층 | 전체 카드가 같은 시각 무게 | 소형 Featured + 기존 전체 그리드의 2계층 |
| 항공 정체성 | Civil 카드 외에는 시각적 표현 없음 | generic civil-airliner 포스터와 flight deck 언어 |
| 모션 | 얕은 hover shadow | 제한적 CSS 2.5D, reduced-motion에서 완전 제거 |
| 정보 보존 | 최근 열람·전체 섹션 | 그대로 보존 |
| 장애 대응 | 보수적 fallback | 히어로도 동일 결과만 사용하며 permission gate를 fail closed |
| 신규 JS | 해당 없음 | 애니메이션·3D dependency 증가 0 |
| `/` First Load JS | 예산 주석 기준 약 132kB | 실측 136kB, 160kB 예산 통과 |

## 5. 검증 결과

### 5.1 테스트와 타입

- 변경 집중: `npm test -- tests/lib/server-auth.test.ts tests/app/home-page.test.tsx` → **28 passed / 2 files**.
- 최초 전체 실행에서 기존 비동기 파일 첨부 테스트 1건이 타이밍으로 실패했으나 단독 재실행 **5/5 passed**로 환경 플레이크임을 확인했다.
- changelog 날짜를 2026-07-22로 바꾼 뒤 stale 날짜 단언 1건을 함께 갱신했다.
- 최종 frontend 전체: `npm test` → **671 passed / 104 files / 0 failed**.
- `npm run typecheck` → **통과**.

### 5.2 production build와 예산

dirty tree를 금지하는 deterministic build 계약 때문에 최초 build가 의도대로 `git worktree is dirty`로 중단됐다. 구현 commit 후 clean tree에서 다시 실행했다.

- `npm run build` → **exit 0**.
- `node scripts/qa/release_budget_gate.mjs --build-log artifacts/qa/release-budget/1.20.0-cinematic-build.log --version 1.20.0 --out artifacts/qa/release-budget/1.20.0-cinematic.json`
  - `/`: **136 / 160kB PASS**
  - `/newsletters`: **143 / 170kB PASS**
  - `/reports/civil-aircraft`: **134 / 160kB PASS**

홈은 기존 예산 주석의 약 132kB 대비 약 4kB 증가했지만 24kB 여유를 유지했다. 포스터는 31,616 bytes라 ZIP 증가도 제한적이다.

### 5.3 브라우저 실측

1. production frontend `next start -p 29501` 실행.
2. 초기 로컬 DB가 빈 파일이라 backend가 `no such table: users`로 중단되는 것을 확인했다.
3. 검증용 로컬 DB에 `alembic upgrade head`와 `scripts/seed.py`를 실행하고 backend 18437을 재시작했다.
4. frontend를 `SERVER_API_BASE_URL=http://127.0.0.1:18437`로 재시작했다.
5. `http://127.0.0.1:29501/` → **HTTP 200**.
6. Chromium 1440×1000에서 다음을 확인했다.
   - `v1.20.0`
   - 항공 포스터와 오버레이
   - 익명 카피와 별도 `AeroOne 로그인` CTA
   - Civil Aircraft·Newsletter Featured
   - backend 정상 연결 후 degraded 경고 없음
   - 기존 Newsletter·Document 전체 서비스 카드 유지
   - 전체 페이지 높이 1164px, 첫 viewport에서 히어로와 업무 영역 시작점 확인

브라우저 증적: `artifacts/qa/cinematic-dashboard-live/dashboard-anonymous-full.webp`. 검토를 위해 backend 18437과 frontend 29501은 작업 종료 시점에도 실행 상태로 유지했다.

## 6. 제외 범위와 후속 후보

### 이번 구현에서 제외

- 자동 재생 영상과 영상 제어
- Motion·GSAP
- Three.js·R3F·GLB
- 전체 화면 100svh 인트로
- scroll hijacking
- 가짜 AI Command·System Online 상태
- 미구현 Digital Twin·Composite Wiki 카드

### 후속 후보

- 실제 사용권과 성능 예산을 통과한 구름 영상 1개를 포스터 위 조건부 레이어로 검증
- Civil Aircraft 상세 화면의 실제 기체·hotspot 요구사항을 먼저 정의한 뒤 별도 3D feature branch 검토
- 로그인 계정별 Featured 사용 빈도 측정 후 우선순위 조정

후속 후보는 1.20.0 릴리스 필수조건이 아니다. 이번 결과만으로 항공 정체성, 빠른 업무 진입, 권한별 UX, 폐쇄망·저사양 안정성 목표를 충족했다.
