# 03. 화면 인벤토리 — 무엇을 그려야 하는가

총 **8 페이지 + 18 컴포넌트**. 각 페이지마다 라이트 / 다크 양 모드를 동시에 디자인해야 합니다 ([`04-design-constraints.md`](04-design-constraints.md) §3).

---

## A. 페이지 인벤토리 (8 개)

### 공개 영역 (뷰어용)

| # | 경로 | 역할 | 핵심 컴포넌트 | 현재 스크린샷 |
|---|---|---|---|---|
| 1 | `/` | **서비스 대시보드** — Newsletter 카드 1 개 (앞으로 모듈 늘어남). 첫 진입점. | `service-card.tsx`, `app-shell.tsx` | — |
| 2 | `/newsletters` | **공개 목록 + 달력 + 검색 + 필터** — 가장 자주 보는 화면. | `newsletters-workspace.tsx`, `newsletter-list.tsx`, `newsletter-card.tsx`, `newsletter-date-calendar.tsx` | [`docs/images/list.png`](../docs/images/list.png) |
| 3 | `/newsletters/[slug]` | **미리보기** — HTML / PDF / Markdown 분기 + 이전/다음 이동. | `newsletter-detail-client.tsx`, `newsletter-preview-panel.tsx`, `newsletter-asset-selector.tsx`, `html-viewer.tsx`, `pdf-viewer.tsx`, `markdown-viewer.tsx` | [`docs/images/preview.png`](../docs/images/preview.png) |

### 관리자 영역

| # | 경로 | 역할 | 핵심 컴포넌트 | 현재 스크린샷 |
|---|---|---|---|---|
| 4 | `/login` | **관리자 로그인** — 단일 시드 관리자. CSRF 토큰 + signed cookie. | `login-form.tsx` | — |
| 5 | `/admin/newsletters` | **관리자 뉴스레터 목록** — 메타데이터 + 활성/비활성 토글. | `admin-newsletter-list.tsx` | [`docs/images/admin.png`](../docs/images/admin.png) |
| 6 | `/admin/newsletters/new` | **수동 신규 등록** — 예외 케이스 (보통은 import 사용). | `newsletter-form.tsx` | — |
| 7 | `/admin/newsletters/[id]/edit` | **메타데이터 편집** — 제목 / 카테고리 / 태그 / 썸네일 / 자산 페어링. | `newsletter-edit-client.tsx`, `newsletter-form.tsx` | — |
| 8 | `/admin/imports` | **Import / Sync** — `Newsletter/output/` 폴더 스캔 → DB 동기화. | `import-panel.tsx` | — |

**스크린샷이 비어 있는 5 페이지** — 디자인 후 운영자가 채울 예정입니다. 현재 모습은 코드 직접 실행으로만 확인 가능 ([`../docs/runbook/local-dev.md`](../docs/runbook/local-dev.md)).

---

## B. 컴포넌트 인벤토리 (18 개)

### 전역 / 레이아웃 (1)

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `AppShell` | `components/layout/app-shell.tsx` | 모든 페이지의 외피 — 헤더 (로고 + 부제 + 대시보드 링크 + 테마 토글), 메인 영역. **전 화면 공통**. |

### 대시보드 (1)

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `ServiceCard` | `components/dashboard/service-card.tsx` | 대시보드의 모듈 카드. 현재는 "Newsletter" 1 개. 앞으로 announcement / schedule / document 등 카드가 늘어날 예정. |

### 인증 (1)

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `LoginForm` | `components/auth/login-form.tsx` | 단일 시드 관리자 로그인 폼. |

### 뉴스레터 — 공개 (11)

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `NewslettersWorkspace` | `components/newsletter/newsletters-workspace.tsx` | `/newsletters` 페이지의 최상위 워크스페이스. 검색·필터·달력·목록을 한 자리에 조율. |
| `NewsletterList` | `components/newsletter/newsletter-list.tsx` | 카드 그리드. 검색·태그 필터링 결과. |
| `NewsletterCard` | `components/newsletter/newsletter-card.tsx` | 단일 이슈 카드 — 썸네일 + 제목 + 발행일 + 태그 + 카테고리. |
| `NewsletterDateCalendar` | `components/newsletter/newsletter-date-calendar.tsx` | 달력 네비게이션. **기본 접힘 상태가 의도된 결정**. |
| `NewsletterDetailClient` | `components/newsletter/newsletter-detail-client.tsx` | `/newsletters/[slug]` 의 클라이언트 본체. |
| `NewsletterPreviewPanel` | `components/newsletter/newsletter-preview-panel.tsx` | 미리보기 본문 영역의 컨테이너. 이전/다음 이동 포함. |
| `NewsletterAssetSelector` | `components/newsletter/newsletter-asset-selector.tsx` | 한 이슈의 HTML / PDF / Markdown 자산 전환. |
| `HtmlViewer` | `components/newsletter/html-viewer.tsx` | sandbox iframe + sanitize + CSP. 본문은 발행자 책임 영역. |
| `PdfViewer` | `components/newsletter/pdf-viewer.tsx` | 브라우저 native PDF. |
| `MarkdownViewer` | `components/newsletter/markdown-viewer.tsx` | 서버 렌더 Markdown. |
| `NewsletterThemeSelector` | `components/newsletter/newsletter-theme-selector.tsx` | 라이트 / 다크 테마 토글. **전 페이지의 헤더 우상단**. |

### 관리자 (4)

| 컴포넌트 | 경로 | 역할 |
|---|---|---|
| `AdminNewsletterList` | `components/admin/admin-newsletter-list.tsx` | 관리자 목록 + 활성/비활성 토글. |
| `NewsletterForm` | `components/admin/newsletter-form.tsx` | 메타데이터 입력 폼 (신규/편집 공유). |
| `NewsletterEditClient` | `components/admin/newsletter-edit-client.tsx` | 편집 페이지의 클라이언트 본체. |
| `ImportPanel` | `components/admin/import-panel.tsx` | Import / Sync 실행 + 결과 출력. |

---

## C. 디자인 우선순위

5 페이지를 새로 그릴 수 있다면 이 순서로 추천합니다.

| 우선순위 | 페이지 | 이유 |
|---|---|---|
| 1 | `/newsletters` 목록 | 사용 빈도 1 위. 검색·달력·태그 3 경로의 시각 균형이 핵심. |
| 2 | `/newsletters/[slug]` 미리보기 | 사용 빈도 2 위. 자산 전환 UX 가 핵심. 본문이 주인공이고 UI 가 보조. |
| 3 | `/` 대시보드 | 첫 진입점. 향후 카드가 늘어날 확장성 고려. |
| 4 | `/admin/newsletters` 관리자 목록 | 매일 들어가는 화면. 뷰어와 같은 시각 언어. |
| 5 | `/admin/imports` Import | 결과 피드백 UX 가 핵심. |
| 6+ | 나머지 폼 / 로그인 / 신규 등록 | 표준 폼 패턴 적용으로 충분. |

---

다음 문서: [`04-design-constraints.md`](04-design-constraints.md) — 무엇은 절대 바꿀 수 없는가.
