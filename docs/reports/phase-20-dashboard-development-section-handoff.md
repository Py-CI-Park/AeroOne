# 단계 20 — 대시보드 개발중 섹션 재분류 핸드오프

- 분류: patch UI 정리 / 운영자 요청 반영
- 대상 화면: 대시보드 `/`
- 기준 버전: `1.7.0`
- 상태: 구현·검증 완료, 커밋 포함

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
- `v1.7.0` 헤더 표시 확인
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

## 6. 후속 작업자 주의사항

- `개발중` 섹션 안의 active 카드는 기능 자체를 비활성화한 것이 아니다. 단지 운영 상태 분류만 바뀌었다.
- `Notebook` 은 여전히 별도 Open Notebook 앱 `http://<host>:8502` 로 새 탭 이동한다. AeroOne 코드 병합이나 DB/세션 공유는 없다.
- `Announcement`, `Schedule` 의 `href: '#'` 는 데이터상 남아 있지만 `ServiceCard` 가 `active:false` 에서 링크를 렌더하지 않으므로 사용자 이동 경로가 아니다.
- 새 대시보드 카드를 추가할 때는 `MODULES.section` 값이 `SECTION_ORDER` 에 들어 있는지 함께 확인해야 한다. 섹션명이 틀리면 카드는 렌더되지 않지만 카운트에는 포함될 수 있다.
