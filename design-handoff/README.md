# AeroOne 디자인 핸드오프 패키지

이 폴더는 **AeroOne 의 UI/UX 를 처음부터 다시 디자인하기 위한 단일 입구** 입니다. 디자이너 1 명이 이 폴더만 읽어도 "왜 이 프로그램이 존재하는지 / 누가 어떤 흐름으로 쓰는지 / 화면이 몇 장 있는지 / 무엇은 절대 바꿀 수 없는지" 가 한 자리에서 잡히도록 묶었습니다.

- 작성 기준 commit: `1183fce` (릴리스 1.0.8 직후)
- 작성일: 2026-05-23
- 대상 독자: AeroOne 의 시각 언어를 새로 설계할 디자이너 (사내·외 무관)
- **요청자용 입구**: [`PROMPT.md`](PROMPT.md) — 디자이너에게 보낼 추천 프롬프트 3 종 (전체 / 부분 / 시각언어만)

---

## 읽는 순서

다음 5 단계를 순서대로 30 분이면 끝납니다.

| 순서 | 문서 | 분량 | 목적 |
|---|---|---|---|
| 1 | [`01-design-brief.md`](01-design-brief.md) | 5 분 | **왜 이 프로그램이 존재하는가** — 정체성·타겟·핵심 가치 |
| 2 | [`02-user-journeys.md`](02-user-journeys.md) | 7 분 | **누가 어떤 흐름으로 쓰는가** — 4 가지 핵심 사용자 여정 |
| 3 | [`03-screen-inventory.md`](03-screen-inventory.md) | 8 분 | **무엇을 그려야 하는가** — 8 페이지 + 18 컴포넌트 인벤토리 |
| 4 | [`04-design-constraints.md`](04-design-constraints.md) | 7 분 | **무엇은 바꿀 수 없는가** — 기술·운영·시각 제약 |
| 5 | [현재 스크린샷 3 장](../docs/images/) | 3 분 | 현재 화면 (`list.png`, `preview.png`, `admin.png`) |

---

## 본 패키지가 다루지 않는 것

- **코드 변경** — 본 패키지는 디자인 요청을 위한 입구입니다. 구현 가이드는 [`AGENTS.md`](../AGENTS.md), [`docs/runbook/local-dev.md`](../docs/runbook/local-dev.md) 를 참고하세요.
- **과거 디자인 결정의 세부 이력** — `docs/superpowers/specs/` 에 14 건의 design spec 이 이미 있습니다 (2026-04 의 theme / navigation / layout 결정). 본 패키지는 그 결정들을 **요약 + 색인** 만 제공합니다 (`04-design-constraints.md` §5).
- **운영자 매뉴얼** — 폐쇄망 설치·운영은 [`docs/CLOSED_NETWORK_GUIDE.md`](../docs/CLOSED_NETWORK_GUIDE.md) 가 진실 원천입니다.

---

## 디자이너에게 드리는 부탁

1. **결과물 형식 자유** — Figma / 정적 이미지 / HTML 목업 / 마크다운 어떤 형식이든 환영합니다. 단, 본 패키지에 나열된 8 페이지가 모두 한 번 이상 그려져 있어야 합니다.
2. **제약 위반은 사전 협의** — `04-design-constraints.md` 의 "절대 피해야 할 것" 항목을 깨야 한다면 디자인 제출 전에 운영자에게 한 줄 메모로 동의를 받아주세요. 폐쇄망 운영이 깨지면 시스템 자체가 안 돕니다.
3. **라이트 / 다크 양 모드 동시 제출** — 본 시스템은 두 테마를 동시에 운영합니다 (`04-design-constraints.md` §3). 한 모드만 디자인하면 다른 모드가 미정의 상태로 출시됩니다.

---

## 진입점 색인

| 더 깊이 들어가려면 | 자리 |
|---|---|
| 저장소 첫 화면 | [`../README.md`](../README.md) |
| 폐쇄망 운영 가이드 | [`../docs/CLOSED_NETWORK_GUIDE.md`](../docs/CLOSED_NETWORK_GUIDE.md) |
| 전체 문서 색인 | [`../docs/INDEX.md`](../docs/INDEX.md) |
| 과거 디자인 결정 (14 건) | [`../docs/superpowers/specs/`](../docs/superpowers/specs/) |
| 현재 스크린샷 | [`../docs/images/`](../docs/images/) |
