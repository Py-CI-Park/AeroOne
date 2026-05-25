# 02. 사용자 여정 — 누가 어떤 흐름으로 쓰는가

핵심 사용자 여정 4 가지. 디자인은 이 4 흐름이 각 단계마다 **3 초 안에 다음 행동이 명확** 해야 합니다.

---

## 여정 A. 뷰어 — 오늘의 이슈를 읽는다 (가장 흔함, 95 %)

```
[홈] → [뉴스레터 목록] → [미리보기]
```

| 단계 | 사용자 행동 | 사용자 기대 | 화면 |
|---|---|---|---|
| 1 | 브라우저에서 `http://localhost:29501` 진입 | "오늘 새 이슈가 있나" 즉시 확인 | [`/`](../frontend/app/page.tsx) (대시보드) |
| 2 | "Newsletter" 카드 클릭 | 최근 이슈가 위에서부터 보임 | [`/newsletters`](../frontend/app/newsletters/page.tsx) (목록) |
| 3 | 가장 위 이슈 카드 클릭 | 본문이 곧바로 열림 (3 초 이내) | [`/newsletters/[slug]`](../frontend/app/newsletters/[slug]/page.tsx) |
| 4 | 본문을 다 읽고 뒤로 | 목록의 그 자리로 돌아옴 (스크롤 위치 보존) | 목록 |

**디자인 결정 포인트:**
- 카드 hover / focus 상태가 명확해야 함 (마우스 이동만으로 "어떤 카드를 누를지" 가 보임).
- 본문 화면에서 "이전 이슈 / 다음 이슈" 가 항상 보여야 함 (현재 `newsletter-preview-panel.tsx` 가 담당).

---

## 여정 B. 뷰어 — 지난주 어떤 이슈를 찾는다

```
[목록] → [달력 펼침] → [날짜 클릭] → [미리보기]
또는
[목록] → [검색창에 키워드] → [필터된 목록] → [미리보기]
또는
[목록] → [태그 클릭] → [태그 필터된 목록] → [미리보기]
```

| 경로 | 사용자 기대 | 현재 컴포넌트 |
|---|---|---|
| 달력 경로 | 발행일 단위로 빠르게 점프 | `newsletter-date-calendar.tsx` (기본 접힘, 클릭 시 펼침) |
| 검색 경로 | 제목·본문 키워드로 매칭 | `newsletter-list.tsx` 의 검색 입력 |
| 태그 경로 | "Aerospace Daily" 같은 카테고리로 좁힘 | `newsletter-list.tsx` 의 태그/카테고리 필터 |

**디자인 결정 포인트:**
- 세 경로 (달력·검색·태그) 가 **같은 시각적 무게** 로 첫 화면에 노출되어야 함 ([`01-design-brief.md`](01-design-brief.md) §3.3).
- 달력은 기본 접힘 상태가 의도된 결정 — 펼쳤을 때 목록을 가리지 않도록 폭/위치 설계 필요.

---

## 여정 C. 뷰어 — 한 이슈를 여러 포맷으로 본다

```
[미리보기 (HTML)] → [PDF 탭 클릭] → [PDF 본문]
                  → [Markdown 탭 클릭] → [Markdown 본문]
```

한 이슈가 다음 3 자산을 동시에 가질 수 있습니다.

| 포맷 | 컴포넌트 | 특이사항 |
|---|---|---|
| HTML | `html-viewer.tsx` | sandbox iframe + sanitize + CSP. 가장 흔한 포맷. |
| PDF | `pdf-viewer.tsx` | 브라우저 native PDF 렌더링. 다운로드 가능. |
| Markdown | `markdown-viewer.tsx` | 서버 렌더. 가장 짧고 가벼움. |

자산 전환은 `newsletter-asset-selector.tsx` 가 담당합니다.

**디자인 결정 포인트:**
- 자산 전환 UI 는 **"같은 이슈의 다른 모습"** 임을 강조해야 함. 별도 페이지로 이동하는 듯한 느낌은 금지.
- HTML iframe 본문은 **본문 디자인은 발행자가 책임지는 영역**. 외부 wrapper UI 가 본문 폰트 · 색을 덮어쓰지 않아야 함.

---

## 여정 D. 관리자 — 새 뉴스레터를 등록한다 (매일)

```
[운영자가 Newsletter/output/ 에 파일 추가]
   ↓
[브라우저에서 /login → 관리자 로그인]
   ↓
[/admin/imports → Import / Sync 버튼 클릭]
   ↓
[/admin/newsletters → 자동 등록된 항목 메타데이터 정리 (제목 · 카테고리 · 태그)]
   ↓
[필요 시 /admin/newsletters/[id]/edit → 썸네일 업로드]
   ↓
[뷰어 화면에서 활성화 확인]
```

| 단계 | 화면 | 컴포넌트 |
|---|---|---|
| 로그인 | [`/login`](../frontend/app/login/page.tsx) | `login-form.tsx` |
| Import / Sync | [`/admin/imports`](../frontend/app/admin/imports/page.tsx) | `import-panel.tsx` |
| 목록 + 활성/비활성 토글 | [`/admin/newsletters`](../frontend/app/admin/newsletters/page.tsx) | `admin-newsletter-list.tsx` |
| 메타데이터 편집 | [`/admin/newsletters/[id]/edit`](../frontend/app/admin/newsletters/[id]/edit/page.tsx) | `newsletter-edit-client.tsx`, `newsletter-form.tsx` |
| 신규 수동 등록 (예외) | [`/admin/newsletters/new`](../frontend/app/admin/newsletters/new/page.tsx) | `newsletter-form.tsx` |

**디자인 결정 포인트:**
- 관리자 화면도 뷰어와 **같은 시각 언어** ([`01-design-brief.md`](01-design-brief.md) §3.4). 관리자만 별도 admin 디자인 시스템 금지.
- Import / Sync 는 **결과를 즉시 보여줘야** 함 ("3 건 추가, 1 건 업데이트" 식). 백그라운드 작업이지만 사용자는 동기 동작으로 느껴야 함.
- 활성 / 비활성 토글은 한 클릭으로 즉시 반영 (모달 확인 단계 없음).

---

## 보조 여정 — 운영자 (분기당 1~2 회)

운영자는 UI 를 거의 보지 않습니다. 디자인 대상이 아니지만, **batch 콘솔 출력의 톤** 이 시각 언어와 어긋나지 않아야 합니다. (예: 콘솔의 에러 메시지 톤과 웹 화면의 에러 메시지 톤이 같은 어휘를 사용.)

자세한 운영자 흐름: [`../docs/CLOSED_NETWORK_GUIDE.md`](../docs/CLOSED_NETWORK_GUIDE.md).

---

다음 문서: [`03-screen-inventory.md`](03-screen-inventory.md) — 무엇을 그려야 하는가, 화면 단위 인벤토리.
