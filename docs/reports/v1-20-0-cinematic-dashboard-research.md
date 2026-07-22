# 1.20.0 시네마틱 항공 대시보드 연구 기록

- 분류: **research / 1.20.0 후보** — 제품 코드는 변경하지 않은 UX·기술 타당성 검토
- 기준 브랜치: `1.20.0-dev`
- 검토일: 2026-07-22
- 검토 범위: `frontend/app/page.tsx`, `frontend/components/layout/app-shell.tsx`, `frontend/components/dashboard/service-card.tsx`, `frontend/app/globals.css`, `frontend/package.json`, `scripts/qa/release_budget_gate.mjs`, `packaging/installer-policy.json`
- 검증 범위: 정적 코드·정책 대조. 로컬 실행, production build, 영상·3D 자산 실측은 수행하지 않음.

## 1. 결론

AeroOne에는 **항공 영상 또는 정적 포스터를 사용한 컴팩트 히어로와 DOM 기반 업무 카드**가 적합하다. 첫 화면 전체를 WebGL로 바꾸거나 존재하지 않는 기능을 홍보 카드로 만드는 것은 적합하지 않다.

권장 구조는 다음과 같다.

> 실제 권한으로 필터링된 모듈 → 로컬 포스터/선택적 영상 히어로 → CSS 2.5D Featured 카드 → 기존 Recent Reads와 전체 업무 그리드

기획 자체의 방향은 좋지만 현재 저장소에 직접 적용하려면 기능 진실성, 폐쇄망 자산, 접근성, JS 성능 예산을 우선해야 한다.

## 2. 현재 AeroOne의 변경 불가 계약

현재 `/`는 Server Component이며 다음 계약을 이미 지킨다.

1. 쿠키, 테마, 관리자 여부, 서비스 모듈을 서버에서 조회한다.
2. 정상 경로에서는 백엔드가 사용자별 `visibility`, `required_permission`, resource policy를 필터링한다.
3. API 장애 시 fallback 목록을 사용하되 비관리자에게 관리자·권한 필요 카드를 보수적으로 숨긴다.
4. 실제 모듈을 정렬한 뒤 섹션별 카드 그리드로 렌더링한다.

시각 개편은 이 서버 로딩과 권한 경계를 그대로 유지하고, 이미 필터링된 `sortedModules`를 표현 컴포넌트에 전달해야 한다. 클라이언트에서 원본 모듈 목록을 다시 만들거나 숨김만으로 권한을 표현해서는 안 된다.

## 3. 실제 기능과 랜딩 문구의 정합성

현재 확인되는 주요 모듈은 Newsletter, Civil Aircraft, Document, NSA, Viewer, AeroAI, Aero Work, Notebook, OpenWebUI, Office Studio 등이다. 다음 이름은 완성된 현재 기능으로 오인될 수 있으므로 홈의 활성 카드로 하드코딩하지 않는다.

- Digital Twin
- Composite Wiki
- 독립 LLM Gateway
- 범용 AI Command 실행기
- 실측 근거가 없는 데이터 소스·보고서·서비스 상태 수치

Featured 영역은 서버가 반환한 실제 모듈 중 Civil Aircraft, AeroAI, Aero Work, Newsletter 등을 우선 선택하되, 해당 사용자의 결과에 존재할 때만 표시해야 한다. 범용 실행 API가 없는 동안 `AI Command`는 `기능 또는 문서 찾기` 수준의 탐색 UI로 한정한다.

## 4. 권장 시각 구조

### 4.1 홈 상단

- 항공기 날개와 구름을 사용한 정적 포스터 또는 느린 로컬 영상
- 텍스트 가독성을 위한 어두운 그라디언트와 비네팅
- AeroOne의 실제 목적을 설명하는 짧은 제목과 설명
- 권한 필터를 통과한 Featured 모듈 3~4개
- 영상 재생·정지 제어
- 포스터와 DOM UI를 영상보다 먼저 표시

### 4.2 업무 영역

- 기존 `RecentReadsStrip` 보존
- 기존 전체 모듈과 external launcher 보존
- 섹션별 정보 구조 보존
- 영상·패럴랙스는 업무 영역에서 약화 또는 중단

랜딩은 감성적이어도 되지만 업무 영역은 읽기 속도와 상태 파악을 우선한다. 매 방문마다 긴 인트로나 스크롤 연출을 강제하지 않는다.

## 5. 로그인·장치 조건별 동작

| 조건 | 권장 표현 |
|---|---|
| 비로그인 | 정적 포스터, 서비스 소개, 로그인 진입, 공개 모듈만 표시 |
| 일반 사용자 | 컴팩트 히어로, 최근 열람, 권한 있는 모듈 |
| 관리자 | 일반 사용자 구성에 관리자 전용 모듈·운영 상태 추가 |
| `prefers-reduced-motion` | 영상 엘리먼트를 마운트하지 않고 포스터 사용, tilt·parallax 제거 |
| 저사양·영상 오류 | 포스터와 일반 DOM 카드 유지 |
| 재방문 사용자 | 히어로 축소 상태 또는 간단히 보기 설정을 보존할 수 있음 |

CSS `display: none`만으로는 영상 다운로드를 확실히 막지 못하므로 모션 감소·데이터 절약 조건에서는 영상 소스를 조건부 마운트해야 한다.

## 6. 기술 선택

현재 production dependency는 Next.js, React, ECharts, Mermaid 중심이며 Motion, GSAP, Three.js, React Three Fiber, Zustand, TanStack Query, shadcn/ui, Lucide는 없다. 기존 `globals.css`와 Tailwind 설정에는 라이트·다크 색상, 반경, 그림자, 모션 시간이 이미 정의되어 있다.

### 1.20.0에 적합

- 기존 Next.js Server Component와 React
- 기존 Tailwind·디자인 토큰·Icon·UI primitives
- HTML5 video 또는 정적 포스터
- CSS gradient, perspective, transform, transition
- 영상 제어를 위한 작은 Client Component

### 보류 또는 제외

| 기술 | 판단 | 이유 |
|---|---|---|
| shadcn/ui·Lucide | 제외 | 기존 디자인 시스템과 중복 |
| Zustand·TanStack Query | 제외 | 홈 서버 데이터와 소규모 UI 상태에 불필요 |
| Motion | 조건부 보류 | CSS로 충족하지 못하는 검증된 상호작용이 있을 때만 재평가 |
| GSAP | 보류 | 일상 업무 포털에서 긴 스크롤 타임라인은 우선순위가 낮음 |
| Three.js/R3F/Drei | 홈에서 제외 | JS·GPU·자산·유지보수 비용이 큼 |
| 전체 WebGL 랜딩 | 제외 | 접근성·복구성·업무 진입 속도에 불리 |

## 7. 성능 예산

`scripts/qa/release_budget_gate.mjs`는 `/`의 First Load JS 상한을 160kB로 강제하고, 주석에 현재 실측을 약 132kB로 기록한다. 여유는 약 28kB이므로 무거운 애니메이션·3D dependency를 홈에 추가하기 어렵다.

영상은 JS 예산과 별개지만 LCP, 네트워크 전송, 오프라인 ZIP 크기를 증가시킨다. 포스터 우선 표시, 영상 오류 fallback, 탭 비활성 시 정지, 오디오 트랙 제거, 저용량 재인코딩이 필요하다.

## 8. 폐쇄망 자산 계약

`packaging/installer-policy.json`은 `frontend`를 허용된 최상위 항목으로 관리하므로 Git에 추적된 `frontend/public` 자산은 빌더 선택 경로와 manifest 검증을 통과하면 ZIP에 포함될 수 있다. 이는 무제한 반입 허가가 아니다.

영상·이미지·향후 모델을 추가할 때 확인할 항목은 다음과 같다.

- 원본과 파생물의 사용권·재배포권
- 출처, 취득일, 라이선스 원문 또는 내부 생성 기록
- 파일 SHA-256과 패키지 manifest 포함 여부
- ZIP 증가량
- 런타임 외부 CDN·폰트·decoder 요청 0건
- production build와 exact-tag 패키징 통과

기업 내부 서비스라도 타사 항공사 로고와 식별 가능한 기체 도장을 피하고, 자체 제작 또는 권리를 확보한 generic civil aircraft 자산을 사용한다.

## 9. 접근성·복구성 계약

- 실제 제목, 설명, 링크, 버튼은 Canvas가 아닌 HTML DOM으로 유지한다.
- 모든 Featured 카드가 Tab과 Enter로 동작해야 한다.
- 영상에는 명시적인 재생·정지 버튼을 제공한다.
- `prefers-reduced-motion`에서는 비필수 움직임을 제거한다.
- 영상·WebGL 오류가 모듈 진입을 가리지 않아야 한다.
- 텍스트 대비는 영상의 가장 밝은 프레임에서도 유지해야 한다.
- 자동재생 영상은 무음이어야 하며 포스터만으로도 정보 손실이 없어야 한다.

## 10. 권장 컴포넌트 경계

별도 `aeroone-landing` 앱을 만들지 않고 기존 구조를 확장한다.

```text
frontend/
├─ app/page.tsx
├─ components/dashboard/
│  ├─ cinematic-hero.tsx
│  ├─ hero-media.tsx
│  ├─ featured-module-dock.tsx
│  ├─ featured-module-card.tsx
│  └─ dashboard-sections.tsx
└─ public/media/
   ├─ aeroone-sky-poster.webp
   ├─ aeroone-sky.webm
   └─ LICENSE.txt
```

`page.tsx`는 서버 컴포넌트로 유지하고 권한 필터링이 끝난 모듈만 하위 표현 컴포넌트에 전달한다. `AppShell`은 복제하지 않고 필요할 때만 기본값 `standard`를 보존하는 제한적 variant를 검토한다.

## 11. 1.20.0 후보 범위

| 항목 | 판단 |
|---|---|
| 전체 UX/UI 명암·밀도·키보드 감사 | 필수 |
| 실제 모듈 기반 컴팩트 항공 히어로 | 권장 |
| 정적 포스터·CSS 하늘 배경 | 우선 구현 후보 |
| CSS 2.5D 카드 | 권장 |
| 로컬 배경 영상 | 라이선스·용량·성능 검증 후 조건부 |
| 범용 AI Command 실행 | 제외 |
| 홈 Three.js | 제외 |
| Digital Twin 3D | 후속 독립 기능 |

## 12. 검증 계획

- Vitest: RBAC 결과, fallback, Featured 선택, external launcher, 영상 오류, reduced-motion
- Testing Library/Axe: 키보드, 역할·이름, 대체 상태, 대비
- Playwright: 로그인·비로그인·관리자 화면, 영상 실패, 라이트·다크, 저해상도
- `tsc --noEmit`, `next build`
- 릴리스 예산 게이트: `/` First Load JS 160kB 이하
- Lighthouse: performance 90 이상, FCP 2,000ms 이하라는 기존 manifest 계약
- 오프라인 ZIP: 자산 manifest, 외부 요청 0건, 설치→실행→종료 스모크

## 13. 결정

1.20.0의 현실적인 시각 개선안은 **기존 서버·RBAC 계약을 보존한 컴팩트 항공 히어로 + 포스터 우선 + 선택적 로컬 영상 + CSS 2.5D DOM 카드**다. Three.js와 Digital Twin은 실제 형상 탐색 요구사항과 모델 자산 파이프라인이 확정된 뒤 Civil Aircraft의 독립 기능으로 다룬다.

## 14. 2차 연구안 대조 결과

사용자가 추가로 제시한 `TravelX·Avora 날개/구름 히어로 + DOM 대시보드 + 제한적 2.5D + Civil Aircraft 전용 3D` 제안을 저장소와 공식 기술 문서에 다시 대조했다.

### 14.1 확인된 사실

- `/`의 서버 조회·RBAC·degraded fallback을 그대로 두고 표현 계층만 교체할 수 있다는 분석은 맞다.
- `AppShell`에는 60px sticky header, 버전, 주요 내비게이션, 시계, 테마, 도움말, 계정 메뉴가 있다.
- 현재 `ServiceCard`는 `min-h-[200px]`, 단색 표면, 얕은 hover shadow 중심이라 별도의 작은 Featured 카드가 필요하다는 분석은 합리적이다.
- Motion은 React 18.2 이상과 Next.js App Router를 지원하므로 React 19에서 기술적으로 사용할 수 있다.
- React Three Fiber 공식 문서는 React 19와 `@react-three/fiber@9`의 major pairing을 안내한다.
- Next.js 공식 문서는 `ssr: false`가 Client Component 안에서만 유효하다고 명시한다. 향후 WebGL을 도입하면 Client 경계 안에서 동적 import해야 한다.
- 영상·3D 버튼과 본문을 DOM에 유지하고 Canvas를 장식 배경으로만 사용하는 원칙은 접근성과 복구성 측면에서 타당하다.

### 14.2 보정이 필요한 주장

| 2차 연구안 | 보정 결론 |
|---|---|
| `npm install motion`을 가장 먼저 수행 | 기술 호환성은 확인됐지만 도입 승인은 아니다. 먼저 dependency 없는 정적/CSS 프로토타입을 만들고 JS 예산 실측 뒤 결정한다. |
| 최초 방문 100svh, 재방문 60~70vh | 업무 카드가 첫 viewport 아래로 밀릴 수 있다. 1.20.0 기본은 컴팩트 히어로로 하고, 전체 화면은 향후 명시적 전시 모드 후보로 둔다. |
| AI Command/Search | 범용 명령 실행은 현재 기능이 아니다. 1차는 모듈·문서 탐색 또는 명확한 이동 CTA만 허용한다. |
| System Online·AI Ready·Document Status | 실시간 API와 실패 의미가 정의된 값만 표시한다. 장식용 가짜 상태는 금지한다. |
| 구름 영상 + GLB 날개 | 홈 GLB는 1.20.0 범위에서 제외한다. 정적 투명 날개 레이어만으로 먼저 검증한다. |
| Motion 후 GSAP 추가 | 두 런타임을 누적하기 전에 CSS/Motion 한 가지로 충족 가능한지 판정한다. scroll hijacking, pin, snap은 기본 업무 홈에서 사용하지 않는다. |
| Draco·KTX2 로컬 decoder | Civil 3D 단계의 후보일 뿐 현재 패키지에 선반입하지 않는다. 실제 모델과 압축 비교 뒤 선택한다. |
| 영상·GLB 권장 크기 표 | 표준이 아닌 내부 가설이다. 현재 ZIP 약 240MB와 설치 시간·LCP 실측으로 최종 예산을 정한다. |
| CSS에서 reduced-motion 영상 `display:none` | 다운로드 방지 계약으로 부족하다. 미디어 질의와 Client 조건으로 `<source>` 자체를 마운트하지 않아야 한다. |
| `frontend` 아래면 자동 패키징 | tracked allow-list, stage build, manifest, pre/post ZIP verifier를 모두 통과해야 한다. 단순 디렉터리 위치만으로 포함을 보장하지 않는다. |

### 14.3 레퍼런스 사용 경계

TravelX·Avora·Boom·Awwwards·Webflow는 시각 방향 또는 상호작용 사례로만 사용한다. AeroOne의 기능·접근성·성능 표준으로 간주하지 않는다. 이 검토 세션에는 2600×1463 원본 이미지 파일이 제공되지 않았으므로 구도 평가는 사용자가 전달한 2차 연구 서술을 근거로 하며, “직접 내려받아 확인했다”는 선행 연구의 관찰 기록을 이번 검토가 독립 재현한 것으로 표시하지 않는다.

레퍼런스 화면이나 스톡·AI 생성 결과를 그대로 복제하지 않는다. 오리지널 자산을 만들고 항공기 날개 형상의 프레임 간 안정성, 상표·도장·기체 식별 요소, 재배포권을 별도로 검수한다.

## 15. 확정된 제품 명세 후보

### 15.1 화면 구조

```text
기존 AppShell(기능 보존, 홈에서만 제한적 immersive 표현 후보)
└─ 컴팩트 Cinematic Hero
   ├─ 정적 포스터 즉시 표시
   ├─ 조건을 통과한 경우에만 로컬 구름 영상
   ├─ 정적 generic civil-aircraft wing 레이어
   ├─ 실제 서비스 설명과 명시적 CTA
   └─ 권한 필터를 통과한 Featured 모듈 최대 4개
└─ 기존 RecentReadsStrip
└─ 기존 전체 섹션·ServiceCard·ExternalLauncherCard
```

Featured 우선순위는 Civil Aircraft, AeroAI, Aero Work, Newsletter를 후보로 하되 **서버 결과에 실제 존재하는 항목만** 사용한다. Featured로 올린 모듈도 아래 전체 그리드에서 찾을 수 있도록 하여 익숙한 탐색 경로를 보존한다.

### 15.2 시각·모션 상한

- Featured 카드 높이 후보: 96~128px
- 카드 tilt: 최대 2~4도
- 배경·날개 parallax: 최대 4~8px
- 지속적으로 움직이는 텍스트 금지
- 인트로 대기와 스크롤 강제 금지
- 헤더 variant는 홈에만 적용하고 기본 `standard`를 불변 기본값으로 유지
- light/dark 양쪽에서 영상 위 텍스트 대비를 실제 프레임으로 측정
- 업무 영역 진입 뒤 영상은 일시 정지하거나 시각 영향이 없는 상태로 약화

### 15.3 자산 도입 순서

1. 텍스트 없는 오리지널 정적 포스터와 분리된 날개 레이어 제작
2. 라이선스·생성 provenance·SHA-256 기록
3. CSS만으로 구도와 DOM 카드 프로토타입
4. production build와 `/` JS 예산 측정
5. 포스터 LCP·명암·저사양 브라우저 검증
6. 구름 영상 1개를 조건부로 추가하고 ZIP·LCP 증가량 비교
7. 효과 대비 이득이 확인될 때만 Motion 도입 검토
8. 홈 3D가 아닌 Civil Aircraft의 별도 요구사항으로 GLB 파이프라인 검토

정적 이미지 생성 프롬프트는 설계 입력으로 사용할 수 있지만 산출물은 항공 구조 검수와 권리 검수를 통과해야 한다. AI 생성이라는 사실만으로 재배포권이나 형상 정확성이 보장되지는 않는다.

## 16. 버전·릴리스 정합성 재점검

2026-07-22의 `1.20.0-dev` 작업 트리에서 확인한 상태는 다음과 같다.

| 진실 원천 | 확인값 | 판단 |
|---|---|---|
| `backend/app/core/config.py` | `1.20.0` | 개발 버전과 일치 |
| `frontend/lib/changelog.ts` | `1.20.0`, 1.19.1 hotfix 승계 기록 | 개발 이력과 일치 |
| GitHub Release | immutable `1.19.1`, `AeroOne-offline-1.19.1.zip` | 최신 게시본 |
| `README.md` 배지 | `1.19.0` | 1.20.0 릴리스 직전 갱신 필요 |
| `offline_package.bat` | builder `-Version 1.19.0` | 1.20.0 릴리스 직전 갱신 필요 |
| `README.md` 운영 반입물 본문 | `1.16.3` 중심 | 현재 latest 1.19.1 기준으로 정리 필요 |

따라서 2차 연구안의 “현재 main README와 wrapper가 1.19.1”이라는 표현을 `1.20.0-dev`에도 그대로 적용할 수 없다. 최신 게시 릴리스는 1.19.1이지만 현재 개발 브랜치의 README 배지와 wrapper는 1.19.0이고, 운영 반입물 본문은 더 오래된 1.16.3을 가리킨다.

이 정합성 수정은 연구 문서 커밋에서 임의로 수행하지 않는다. AGENTS.md의 릴리스 절차에 따라 1.20.0 정식 릴리스 직전 버전 표기, 검증 수치, 실제 ZIP digest와 함께 한 번에 갱신한다.

## 17. 2차 결정

2차 연구의 핵심 조합은 채택한다.

> TravelX·Avora 계열의 날개/구름 구도 + 실제 권한 기반 DOM 대시보드 + 제한적 CSS 2.5D + Civil Aircraft로 분리한 후속 3D

다만 1.20.0 구현 기본값은 **컴팩트·포스터 우선·dependency 없음**으로 더 좁힌다. Motion은 CSS 프로토타입이 요구를 충족하지 못하고 160kB JS 예산과 Lighthouse 계약을 통과할 때만 추가한다. GSAP와 홈 Three.js는 1.20.0 범위에서 제외한다.

## 18. 외부 참고 자료

아래 자료는 2026-07-22에 기술 주장 확인 또는 시각 참고 경계 설정에 사용했다.

- Avora Aviation 소개: <https://www.avora.aero/about>
- Boom XB-1 interactive experience 소개: <https://boomsupersonic.com/flyby/meet-xb-1-in-this-fully-interactive-digital-experience>
- Next.js lazy loading: <https://nextjs.org/docs/app/guides/lazy-loading>
- Motion for React 설치·Next.js 안내: <https://motion.dev/docs/react-installation>
- React Three Fiber 설치·React major pairing: <https://r3f.docs.pmnd.rs/getting-started/installation>
- Three.js GLTFLoader: <https://threejs.org/docs/pages/GLTFLoader.html>
- Three.js DRACOLoader: <https://threejs.org/docs/pages/DRACOLoader.html>
- Three.js KTX2Loader: <https://threejs.org/docs/pages/KTX2Loader.html>
- MDN `<video>`: <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video>
- MDN autoplay: <https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay>
- MDN `prefers-reduced-motion`: <https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion>
