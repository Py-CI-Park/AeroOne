# Superpowers 디렉토리 색인

본 디렉토리는 OMC `superpowers` 형식으로 작성된 **기능별 plan / spec 한 쌍**을 모은 자리입니다. plan 은 구현 단계와 수용 기준, spec 은 같은 기능의 인터페이스·내부 구조 설계를 담습니다.

- `plans/` — 15건
- `specs/` — 14건
- 기준 commit: `bb94269`

---

## 매칭 표 (plan ↔ spec)

| 날짜 | 기능 | plan | spec |
|---|---|---|---|
| 2026-03-31 | Windows start 런처 readiness | [windows-start-launcher-readiness.md](plans/2026-03-31-windows-start-launcher-readiness.md) | [windows-start-launcher-readiness-design.md](specs/2026-03-31-windows-start-launcher-readiness-design.md) |
| 2026-04-03 | frontend 뉴스레터 요청 로깅 | [frontend-newsletter-request-logging.md](plans/2026-04-03-frontend-newsletter-request-logging.md) | [frontend-log-pattern-design.md](specs/2026-04-03-frontend-log-pattern-design.md) |
| 2026-04-04 | 홈 hero 제거 | [home-hero-removal.md](plans/2026-04-04-home-hero-removal.md) | [home-hero-removal-design.md](specs/2026-04-04-home-hero-removal-design.md) |
| 2026-04-04 | Windows frontend 런처 신뢰성 | [windows-frontend-launcher-reliability.md](plans/2026-04-04-windows-frontend-launcher-reliability.md) | [windows-frontend-launcher-reliability-design.md](specs/2026-04-04-windows-frontend-launcher-reliability-design.md) |
| 2026-04-05 | 뉴스레터 미리보기 레이아웃 | [newsletters-preview-layout.md](plans/2026-04-05-newsletters-preview-layout.md) | [newsletters-preview-layout-design.md](specs/2026-04-05-newsletters-preview-layout-design.md) |
| 2026-04-05 | (보충) 미리보기 페이지 셸 재설계 | — | [newsletters-preview-layout-page-shell-redesign.md](specs/2026-04-05-newsletters-preview-layout-page-shell-redesign.md) |
| 2026-04-12 | 뉴스레터 런타임 테마 | [newsletters-runtime-theme.md](plans/2026-04-12-newsletters-runtime-theme.md) | [newsletters-runtime-theme-design.md](specs/2026-04-12-newsletters-runtime-theme-design.md) |
| 2026-04-13 | 뉴스레터 nav 테마 아이콘 | [newsletters-nav-theme-icons.md](plans/2026-04-13-newsletters-nav-theme-icons.md) | [newsletters-nav-theme-icons-design.md](specs/2026-04-13-newsletters-nav-theme-icons-design.md) |
| 2026-04-13 | 뉴스레터 단일 테마 토글 | [newsletters-single-theme-toggle.md](plans/2026-04-13-newsletters-single-theme-toggle.md) | [newsletters-single-theme-toggle-design.md](specs/2026-04-13-newsletters-single-theme-toggle-design.md) |
| 2026-04-13 | 뉴스레터 테마 선택기 | [newsletters-theme-selector.md](plans/2026-04-13-newsletters-theme-selector.md) | [newsletters-theme-selector-design.md](specs/2026-04-13-newsletters-theme-selector-design.md) |
| 2026-04-16 | AppShell 글로벌 테마 | [appshell-global-theme.md](plans/2026-04-16-appshell-global-theme.md) | [appshell-global-theme-design.md](specs/2026-04-16-appshell-global-theme-design.md) |
| 2026-04-16 | 글로벌 테마 쿠키 | [global-theme-cookie.md](plans/2026-04-16-global-theme-cookie.md) | [global-theme-cookie-design.md](specs/2026-04-16-global-theme-cookie-design.md) |
| 2026-04-18 | 뉴스레터 미리보기 네비 정리 | [newsletter-preview-navigation-cleanup.md](plans/2026-04-18-newsletter-preview-navigation-cleanup.md) | [newsletter-preview-navigation-cleanup-design.md](specs/2026-04-18-newsletter-preview-navigation-cleanup-design.md) |
| 2026-04-19 | 홈 nav 달력 정리 | [home-nav-calendar-cleanup.md](plans/2026-04-19-home-nav-calendar-cleanup.md) | [home-nav-calendar-cleanup-design.md](specs/2026-04-19-home-nav-calendar-cleanup-design.md) |
| 2026-06-04 | 대시보드 외부 서비스/포트 패널 (계획만, 미구현) | [dashboard-external-service-panel.md](plans/2026-06-04-dashboard-external-service-panel.md) | — (구현 시 작성) |
| 2026-06-05 | 컬렉션 same-origin 프록시 + Civil/NSA·사다리 (1.4.0, ralplan) | [2026-06-05-multi-feature-collections-proxy.md](plans/2026-06-05-multi-feature-collections-proxy.md) | — ([단계 13 보고서](../reports/phase-13-collections-proxy-and-features.md)) |

---

## 새 기능 추가 시

신규 기능을 작업할 때는 같은 날짜 prefix 의 plan + spec 한 쌍을 함께 추가하고, 본 INDEX.md 의 매칭 표에 한 줄을 더해 주세요. 그래야 다음 독자가 어떤 기능이 어떤 commit 에 속해 있었는지 같은 자리에서 추적할 수 있습니다.

상세 추가 절차: [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §4 코드 컨벤션 요약의 "설계 산출물 동기화" 항목.
