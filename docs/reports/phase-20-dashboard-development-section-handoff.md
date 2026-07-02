# 단계 20 — 대시보드 개발중 섹션 재분류 핸드오프

- 분류: patch UI 정리 / 운영자 요청 반영
- 대상 화면: 대시보드 `/`
- 기준 버전: `1.7.1`
- 상태: 개발중 섹션 재분류 완료 + 1.7.1 뉴스레터/사용법 patch 반영

---

## 1. 변경 배경

운영자가 현재 개발 중이거나 별도 앱/실험 성격이 있는 대시보드 항목을 한 곳에서 확인할 수 있도록 `개발중` 카테고리를 요청했다. 대상은 `AeroAI`, `Notebook`, `Viewer`, `Ladder` 이며, 이 네 항목은 아직 개발중 섹션에 있어도 사용 가능한 버튼이므로 `Active` 상태를 유지해야 한다.

기존 `Coming soon` 항목(`Announcement`, `Schedule`)은 별도 섹션으로 분리하지 않고 같은 `개발중` 섹션 안에 남기되, 클릭되지 않는 비활성 카드와 `Coming soon` 배지를 유지하는 것이 요구사항이다.

---

## 2. 구현 요약

`frontend/app/page.tsx` 의 대시보드 카드 데이터에서 섹션을 단일 원천으로 정리했다.

- `SECTION_ORDER = ['Newsletter', 'Document', '개발중']`
- `Viewer`, `AeroAI`, `Notebook`, `Ladder` → `section: '개발중'`, `active: true`
- `Announcement`, `Schedule` → `section: '개발중'`, `active: false`, `badge: 'Coming soon'`
- 별도 `Coming soon` 렌더 블록 제거
- 상단 요약 `8 active · 2 coming soon` 은 계속 `MODULES` 에서 파생

`ServiceCard` 의 기존 비활성 분기(`active:false` → `aria-disabled` div, 링크 미렌더)를 그대로 사용했으므로 새 동작을 위해 클릭 방지 로직을 중복 추가하지 않았다.

---

## 3. 함께 갱신한 문서

운영자 진입점과 폐쇄망 런북이 실제 대시보드 섹션명을 가리키도록 문구를 동기화했다.

- `README.md` — AeroAI / Open Notebook 설명의 대시보드 위치
- `docs/INDEX.md` — Viewer / Ladder / Ollama AI 색인 설명
- `docs/CLOSED_NETWORK_GUIDE.md` — Ladder, AeroAI, Open Notebook 운영 안내
- `docs/runbook/closed-network-install-manual.md` — 확인 체크리스트와 Viewer/Notebook 위치
- `docs/runbook/open-notebook-airgap.md` — co-deploy 결합점 설명
- `frontend/lib/changelog.ts` — 과거 changelog 의 섹션명 오해 소지 제거

---

## 4. 회귀 방지

`frontend/tests/app/home-page.test.tsx` 에서 다음을 직접 검증한다.

- 섹션 순서: `Newsletter` → `Document` → `개발중`
- `AeroAI`, `Notebook`, `Viewer`, `Ladder` 가 `개발중` 이후 active 링크로 노출
- 별도 `Coming soon` heading 없음
- `Announcement`, `Schedule` 은 링크가 아니며 `aria-disabled` 비활성 카드
- 두 비활성 카드가 `Coming soon` 배지를 유지
- 요약 문구 `8 active · 2 coming soon` 유지

---

## 5. 수행 검증

실행 결과:

```text
npm test -- tests/app/home-page.test.tsx tests/components/version-badge.test.tsx
→ 2 files passed, 14 tests passed

npm run typecheck
→ tsc --noEmit exit 0

npm run build
→ next build 성공
```

브라우저 확인:

- `start_offline.bat --no-pause` 기반 production frontend `http://localhost:29501/`
- `v1.7.0` 헤더 표시 확인(초기 대시보드 재분류 검증)
- `개발중` 섹션 표시 확인
- `AeroAI`, `Notebook`, `Viewer`, `Ladder` active 카드 확인
- `Announcement`, `Schedule` 비활성 `Coming soon` 카드 확인
- 별도 `Coming soon` 섹션 미표시 확인
- 대시보드 스크린샷: `.gjc/_session-019f1821-db18-7000-93cd-91f87e60555a/ultragoal/artifacts/dashboard-development-section-production.png`

리뷰/QA:

- Architect review: `CLEAR / CLEAR / CLEAR`, `APPROVE`, blockers 없음
- Executor QA/red-team: `passed`, blockers 없음
- Ultragoal `G001` complete checkpoint 및 aggregate goal complete 완료

---

## 6. 1.7.1 추가 패치

릴리즈 `1.7.1` 에서는 같은 대시보드/뉴스레터 사용성 흐름을 이어 다음을 추가 반영했다.

- 뉴스레터 리딩 뷰의 달력 접힘 상태를 부모 그리드까지 전달해, `달력 접기` 시 왼쪽 날짜 영역의 데스크톱 가로 폭도 `max-content` 로 줄인다.
- 뉴스레터 `HTML 다운로드` 버튼을 accent soft 배경, font-semibold, shadow/ring 으로 강조해 원본 HTML 다운로드 경로를 더 쉽게 찾게 했다.
- 헤더 `사용법` 팝업을 현재 서비스 중(`Newsletter`, `Document`, `Civil Aircraft`, `NSA`)과 개발중(`Viewer`, `AeroAI`, `Notebook`, `Ladder`, Coming soon 카드) 구분에 맞게 갱신했다.
- 헤더 버전 changelog 에 `1.7.1` 항목을 추가하고 README/운영 가이드/설치 매뉴얼의 반입 파일 버전을 `1.7.1` 로 올렸다.

추가 회귀 방지(1.7.1 최종 검증: backend `pytest tests` 175 passed / frontend Vitest 205 passed / 47 파일, `tsc --noEmit`, `next build`, browser smoke):

- `frontend/tests/components/newsletter-date-calendar.test.tsx` — controlled open callback 및 collapsed `w-max` 상태
- `frontend/tests/app/newsletters-layout.test.tsx` — 달력 접기 후 `data-calendar-open=false` 와 `lg:grid-cols-[max-content_minmax(0,1fr)]`
- `frontend/tests/components/html-viewer.test.tsx` — HTML 다운로드 버튼 강조 클래스
- `frontend/tests/components/app-shell.test.tsx` — 사용법 팝업의 개발중/현재 서비스 안내
- `frontend/tests/components/version-badge.test.tsx` — `APP_VERSION = 1.7.1`

---

## 7. 후속 작업자 주의사항

- `개발중` 섹션 안의 active 카드는 기능 자체를 비활성화한 것이 아니다. 단지 운영 상태 분류만 바뀌었다.
- `Notebook` 은 여전히 별도 Open Notebook 앱 `http://<host>:8502` 로 새 탭 이동한다. AeroOne 코드 병합이나 DB/세션 공유는 없다.
- `Announcement`, `Schedule` 의 `href: '#'` 는 데이터상 남아 있지만 `ServiceCard` 가 `active:false` 에서 링크를 렌더하지 않으므로 사용자 이동 경로가 아니다.
- 새 대시보드 카드를 추가할 때는 `MODULES.section` 값이 `SECTION_ORDER` 에 들어 있는지 함께 확인해야 한다. 섹션명이 틀리면 카드는 렌더되지 않지만 카운트에는 포함될 수 있다.
