# 04. 디자인 제약 — 무엇은 바꿀 수 없는가

본 시스템은 폐쇄망 운영을 일차 목적으로 합니다. 일부 제약은 **위반 시 시스템 자체가 안 돕니다**. 디자인 제출 전에 본 문서를 한 번 더 점검해주세요.

---

## 1. 절대 제약 (위반 시 시스템 안 돔)

### 1.1 외부 의존 0

폐쇄망 PC 는 인터넷이 차단되어 있습니다. 따라서 다음 자리는 **모두 로컬 자산** 만 참조해야 합니다.

| 자리 | 금지 | 허용 |
|---|---|---|
| 폰트 | Google Fonts, Adobe Fonts, 외부 CDN | 시스템 폰트, 패키지에 묶인 로컬 폰트 |
| 아이콘 | 외부 CDN 아이콘 (예: 외부 호스트의 SVG) | npm 패키지로 묶이는 아이콘 라이브러리, 로컬 SVG |
| 이미지 | 외부 호스트 이미지 | `public/`, `storage/thumbnails/` 의 로컬 이미지 |
| 분석 / 추적 | Google Analytics, 외부 픽셀 | 없음 (수집 자체가 정책상 금지) |
| 스크립트 | 외부 CDN JS | 번들에 포함된 JS 만 |

**디자인에 외부 URL 이 한 줄이라도 들어가면 폐쇄망 PC 에서 깨집니다.** 이 제약은 협상 대상이 아닙니다.

### 1.2 HTML / PDF / Markdown 3 포맷 동시 지원

이 시스템의 정체성입니다 ([`01-design-brief.md`](01-design-brief.md) §3.1). 한 이슈 = 하나의 카드. 자산 전환은 같은 페이지 안에서 일어남.

### 1.3 단일 시드 관리자

관리자는 1 명만 존재합니다 (`backend/.env` 의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`). 멀티 유저 권한 UI 를 그리지 마세요. "내 프로필" / "팀원 초대" 같은 기능은 본 시스템의 범위 밖입니다.

---

## 2. 기술 스택 제약

| 항목 | 제약 |
|---|---|
| **CSS 프레임워크** | Tailwind CSS (`frontend/tailwind.config.ts`). 현재 `theme: { extend: {} }` 로 기본 팔레트만 사용 — 디자인이 새 토큰을 추가하려면 `extend` 에 명시. |
| **컴포넌트 라이브러리** | 없음 (모든 컴포넌트가 직접 작성). shadcn/ui 같은 외부 시스템을 도입하려면 사전 협의. |
| **프레임워크** | Next.js 15 App Router, React 18, TypeScript 5. 클라이언트 / 서버 컴포넌트 분리됨. |
| **브라우저** | Chrome / Edge 최신 2 버전. 사내 PC 기준. IE 지원 불필요. |
| **이미지 포맷** | PNG, JPG, WebP, SVG. AVIF 는 Edge 일부 버전에서 부분 지원이라 회피 권장. |

---

## 3. 라이트 / 다크 양 모드 동시 운영

### 3.1 현재 시각 언어 (참고용)

`AppShell` (`components/layout/app-shell.tsx`) 의 현재 팔레트:

| 모드 | 배경 | 헤더 배경 | 헤더 보더 | 본문 텍스트 | 부제 텍스트 |
|---|---|---|---|---|---|
| Light | `bg-slate-100` | `bg-white` | `border-slate-200` | `text-slate-900` | `text-slate-500` |
| Dark | `bg-slate-950` | `bg-slate-950` | `border-slate-800` | `text-slate-100` | `text-slate-400` |

이 팔레트는 **현재 상태이지 정답이 아닙니다**. 디자인이 새 팔레트를 제안하면 양 모드 모두 함께 제출해주세요.

### 3.2 테마 전환

- 토글 위치: 헤더 우상단 (`NewsletterThemeSelector`)
- 저장 방식: `aeroone_theme` 쿠키 (`frontend/lib/theme.ts`)
- 초기값: 환경변수 `NEWSLETTERS_THEME` 또는 light
- 전환 즉시 반영 (페이지 리로드 없음)

### 3.3 한 모드만 디자인하면 다른 모드가 미정의 상태로 출시됩니다

이것은 가장 흔한 실수입니다. **두 모드를 동시에 제출** 해주세요.

---

## 4. 운영 제약 (디자인에 영향 있음)

### 4.1 LAN 모드

`setup_offline.bat --allow-host=<IP>` 옵션으로 LAN 의 다른 PC 가 같은 인스턴스에 접속할 수 있습니다 (`docs/reports/phase-7-lan-mode.md`). 이때 사용자 PC 의 IP 가 도메인이 됩니다 (`http://192.168.1.10:29501`). 디자인은 **도메인 가정 없이** 동작해야 합니다 (절대 URL 하드코딩 금지).

### 4.2 포트 고정

- Backend: `18437`
- Frontend: `29501`

디자인에 포트 번호가 보이는 자리 (예: 시스템 정보 패널) 가 있다면 위 두 값으로.

### 4.3 콘텐츠 분기 — sandbox iframe

HTML 본문은 **sandbox iframe + CSP + sanitize** 로 격리됩니다. 즉 본문의 CSS 는 외부 wrapper 와 분리됨. 디자이너 입장에서:

- iframe 본문의 디자인은 발행자 책임 (디자이너 범위 밖).
- 외부 wrapper 의 디자인이 iframe 본문에 침투하지 않음 (CSS 격리).
- iframe 의 **테두리 · 배경 · 여백** 만 디자인 대상.

---

## 5. 기존 디자인 결정 색인 (이미 합의된 자리)

`docs/superpowers/specs/` 에 2026-04 의 디자인 결정 14 건이 있습니다. 새 디자인이 다음 결정을 **번복** 하려면 사전 협의가 필요합니다.

| 결정 | spec 문서 |
|---|---|
| 홈의 hero 영역 제거 (대시보드 카드로 대체) | [`2026-04-04-home-hero-removal-design.md`](../docs/superpowers/specs/2026-04-04-home-hero-removal-design.md) |
| 뉴스레터 미리보기 페이지 셸 재설계 | [`2026-04-05-newsletters-preview-layout-page-shell-redesign.md`](../docs/superpowers/specs/2026-04-05-newsletters-preview-layout-page-shell-redesign.md) |
| 뉴스레터 런타임 테마 (쿠키 기반) | [`2026-04-12-newsletters-runtime-theme-design.md`](../docs/superpowers/specs/2026-04-12-newsletters-runtime-theme-design.md) |
| 단일 테마 토글 (drop-down → 토글) | [`2026-04-13-newsletters-single-theme-toggle-design.md`](../docs/superpowers/specs/2026-04-13-newsletters-single-theme-toggle-design.md) |
| 네비게이션 테마 아이콘 | [`2026-04-13-newsletters-nav-theme-icons-design.md`](../docs/superpowers/specs/2026-04-13-newsletters-nav-theme-icons-design.md) |
| AppShell 전역 테마 적용 | [`2026-04-16-appshell-global-theme-design.md`](../docs/superpowers/specs/2026-04-16-appshell-global-theme-design.md) |
| 글로벌 테마 쿠키 | [`2026-04-16-global-theme-cookie-design.md`](../docs/superpowers/specs/2026-04-16-global-theme-cookie-design.md) |
| 미리보기 네비게이션 정리 | [`2026-04-18-newsletter-preview-navigation-cleanup-design.md`](../docs/superpowers/specs/2026-04-18-newsletter-preview-navigation-cleanup-design.md) |
| 홈 네비/달력 정리 (달력 기본 접힘) | [`2026-04-19-home-nav-calendar-cleanup-design.md`](../docs/superpowers/specs/2026-04-19-home-nav-calendar-cleanup-design.md) |

나머지 5 건은 windows-launcher / frontend-log / theme-selector 관련 세부.

---

## 6. 절대 피해야 할 것 (체크리스트)

- [ ] 외부 폰트 / 외부 CDN / 외부 이미지 참조
- [ ] 한 모드만 (라이트 또는 다크) 디자인
- [ ] 한 이슈를 자산별로 (HTML 카드 / PDF 카드 / Markdown 카드) 분리 표시
- [ ] 멀티 유저 권한 UI (관리자는 1 명)
- [ ] 마케팅 톤 (큰 hero, 일러스트레이션, 감성 카피)
- [ ] 본문을 가리는 큰 UI 장식
- [ ] 절대 URL 하드코딩 (LAN 모드에서 깨짐)
- [ ] 5 % 관리자 화면을 별도 디자인 시스템으로

---

## 7. 협상 가능한 자리 (디자이너 재량)

- 색 팔레트 전체 (`slate-*` 위주의 현재 팔레트는 권장값일 뿐)
- 폰트 (시스템 폰트 또는 번들 가능한 로컬 폰트 한도 안에서)
- 타이포 스케일
- 카드 / 버튼 / 입력의 모양 (radius, shadow, hover 상태)
- 달력 위치 / 펼침 방식 (기본 접힘 결정은 유지)
- 검색·필터·태그의 배치 (3 경로 동등 무게 결정은 유지)

---

본 패키지 끝. 디자인 시안 제출 시 [`README.md`](README.md) 의 "디자이너에게 드리는 부탁" 3 가지를 한 번 더 확인 부탁드립니다.
