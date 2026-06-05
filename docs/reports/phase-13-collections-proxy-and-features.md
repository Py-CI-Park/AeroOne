# 단계 13 — 컬렉션 same-origin 프록시 + Civil/NSA 목록화 + 사다리 게임

- 분류: **minor (`1.4.0`)** — 외부접속 버그 수정 + 신규 모듈/페이지 다수
- dev 브랜치: `1.4.0-dev`
- 진입점: 대시보드 카드(Civil / NSA / Ladder), 헤더 네비는 Dashboard/Newsletter/Document 3개 유지

---

## 1. 배경

운영자 보고: **다른 PC 에서 접속하면 Document 본문이 "failed to fetch" 로 안 열린다**(본인 PC 에서는 정상). 추가로 (1) Document 목록을 기본 접힌 상태로, (2) Civil 카탈로그도 Document 처럼 여러 HTML 을 목록으로, (3) 뉴스레터 달력을 접으면 더 작게, (4) 비밀번호로 가린 NSA 탭, (5) 커피 내기용 사다리 게임, (6) 상단 탭은 Dashboard/Newsletter/Document 3개만 유지 — 7가지를 한 사이클에 요청.

근본 원인: `fetchDocumentContent` 가 **브라우저에서** `NEXT_PUBLIC_API_BASE_URL`(=`http://localhost:18437`)로 백엔드를 직접 호출했다. 방문자 브라우저에서 `localhost` 는 방문자 자기 PC 라 백엔드가 없어 실패한다. 목록은 SSR(서버가 loopback 으로 호출)이라 정상이어서 "목록은 보이는데 본문만 실패" 증상이 나왔다. 뉴스레터 본문은 same-origin BFF 프록시(`/api/frontend/newsletters/...`)를 거쳐 외부에서도 동작하는데, Document 만 그 프록시를 안 거치는 것이 유일한 차이였다.

## 2. 선택한 접근

**(#2) same-origin BFF 프록시로 통일.** 뉴스레터와 동일하게 컬렉션 본문을 Next 라우트(`/api/frontend/collections/[...segments]`)로 프록시한다. 브라우저는 same-origin 상대경로를 호출하고, Next 서버가 `SERVER_API_BASE_URL`(항상 loopback)로 업스트림한다 → 페이지가 열리는 모든 방문자에게 동작(CORS/`NEXT_PUBLIC`/LAN 모드 무관). 본문은 백엔드가 JSON `{content_html}` 으로 주고 프런트가 `srcDoc` 으로 주입하므로 프록시는 `content-type` 만 전달하면 된다(CSP 헤더는 iframe 렌더에 불필요). 경로 세그먼트는 per-segment `encodeURIComponent` 를 유지해 `../` 업스트림 경로 주입을 차단하고, 쿼리스트링만 verbatim 전달한다(`?path=한글/문서.html` 이중 인코딩 404 방지).

**(DRY) 컬렉션 공유 서비스.** Document/Civil/NSA 는 같은 "HTML 컬렉션" 동작이라 백엔드에 `HtmlCollectionService`(`discover_list` + `render_one`, `.html`/`_debug` 가드 + `ensure_within_root` path-guard)를 두고, `/api/v1/collections/{collection}` 라우터가 화이트리스트(`{document, civil, nsa}` → config 해석 루트, 미등록은 FS 접근 전 404)로 분기한다. 기존 `documents`/`reports` 라우터는 이 서비스에 **위임**(병렬 복제 제거)하고 `reports` 는 "최신 단일 보고서" 선택 정책(`_latest_report`)만 보존한다. 프런트는 `DocumentsWorkspace` 를 `collection` prop + 기본 접힘(`defaultSidebarOpen`/`defaultFoldersOpen` 기본 false)으로 일반화해 Document/Civil/NSA 가 한 컴포넌트를 재사용한다.

**(#5 NSA) 클라이언트 가림막.** `CollectionPasswordGate`(비번 `0000`)가 정답 입력 후에만 `fetchCollectionList('nsa')` 를 호출해 `DocumentsWorkspace` 에 목록을 prop 주입한다(언락 전 네트워크 요청 0건). 이는 실인증이 아니라 가벼운 가림막이다 — 백엔드는 폐쇄망 내 무인증이고 비번은 번들에 노출되므로 민감자료는 두지 않는다. **(#6 사다리)** 순수 프론트 `computeLadderMapping(participants, prizes, rng=Math.random)`(Fisher–Yates 전단사). **(#7)** 신규 항목은 모두 대시보드 카드로만 노출하고 상단 네비는 3개 그대로 둔다.

## 3. 검토하고 제외한 대안

- **(a) LAN 모드 재설정(`setup_offline --allow-host`)으로 `NEXT_PUBLIC_API_BASE_URL` 을 LAN IP 로** — `NEXT_PUBLIC_*` 은 빌드타임 인라인이라 재빌드가 필요하고 IP 가 바뀌면 또 깨진다. 운영자가 5자리 정합을 매번 맞춰야 하는, 이미 실패한 경로라 거부.
- **(b) 브라우저 직접호출 + CORS 와일드카드** — 폐쇄망 순도 정책(정확한 origin만 허용) 위반이라 거부. read-beacon 만은 reader LAN IP 가 필요해 의도적으로 직접호출 유지.
- **(c) Civil 단일 보고서 계약 보존** — 운영자가 "여러 카탈로그 목록"을 명시 요청해 list 로 전환(accepted tradeoff). 단일-report 컴포넌트/엔드포인트는 1릴리즈 removal-deferred(롤백은 `page.tsx` revert 로만).
- **(d) `DocumentsWorkspace` 에 `fetchListClientSide` 플래그 추가** — 워크스페이스가 게이트/비동기 모드를 알게 되어 god-component 화. 게이트 래퍼가 목록을 받아 prop 주입하는 쪽으로 단순화.

## 4. 코드 (진실 원천)

| 영역 | 위치 |
|---|---|
| 컬렉션 공유 서비스 | `backend/app/modules/collections/service.py` (`HtmlCollectionService.discover_list/render_one`) |
| 컬렉션 라우터(화이트리스트) | `backend/app/modules/collections/api/public.py` (`/{collection}/list`, `/content/html`, 미등록 404) |
| nsa 설정 | `backend/app/core/config.py` (`nsa_root='./_database/nsa'`, `nsa_root_path`) |
| 위임 리팩터 | `backend/app/modules/documents/api/public.py`, `backend/app/modules/reports/api/public.py` (공유 서비스 위임) |
| same-origin 프록시 | `frontend/app/api/frontend/collections/[...segments]/route.ts`, `frontend/lib/collection-proxy.ts`(세그먼트 인코딩/쿼리 verbatim/화이트리스트) |
| 프런트 fetcher | `frontend/lib/api.ts` (`fetchCollectionContent`/`fetchCollectionList`/`fetchCollectionListServer`, `fetchDocumentContent` 위임) |
| 워크스페이스 일반화 | `frontend/components/documents/documents-workspace.tsx` (`collection`/기본 접힘) |
| Civil 목록 | `frontend/app/reports/civil-aircraft/page.tsx` (SSR list → 워크스페이스) |
| NSA 탭/게이트 | `frontend/app/nsa/page.tsx`, `frontend/components/collections/collection-password-gate.tsx` |
| 사다리 | `frontend/app/games/ladder/page.tsx`, `frontend/components/games/ladder-game.tsx` |
| 대시보드 카드 | `frontend/app/page.tsx` (NSA/Ladder active 카드; 상단 네비 불변) |
| 달력 컴팩트 | `frontend/components/newsletter/newsletter-date-calendar.tsx` (접힘 시 `p-2` 슬림 바) |

## 5. 회귀 방지

- 백엔드: `backend/tests/integration/test_collections_api.py` (list/content/미등록 404/traversal 400/.html·_debug 가드/빈 루트 — 3 컬렉션), 기존 `test_documents_api.py`/`test_reports_api.py` 위임 후 green 유지.
- 프런트: `collections-route.test.ts`(verbatim 쿼리 + 세그먼트 인코딩 + 화이트리스트 404 + 502), `api.test.ts`(**C1 회귀가드** — same-origin 상대경로 + localhost 미부착), `documents-workspace.test.tsx`(기본 접힘 + collection fetch), `civil-aircraft-report-page.test.tsx`(list UI), `collection-password-gate.test.tsx`(언락 전 요청 0건), `nsa-page.test.tsx`, `ladder-game.test.tsx`(결정적 + 전단사 불변식), `home-page.test.tsx`(active 5/coming 2 파생), `app-shell.test.tsx`(네비 3개 가드), `newsletter-date-calendar.test.tsx`(접힘 compact).

## 6. 검증 게이트

- backend `pytest tests` (`.venv`): **120 passed**
- frontend Vitest: **120 passed (37 파일)**
- `tsc --noEmit`: exit 0
- 리뷰: ralplan 합의(Architect SOUND-WITH-CHANGES → Critic APPROVE) + 구현 후 architect THOROUGH 검증 APPROVED.
- **미검증(환경 제약):** #2 의 "다른 PC 실측"(외부 호스트에서 본문 렌더)은 LAN 접속이 필요해 운영자 게이트로 남긴다 — 설계(상대경로 same-origin 프록시)와 단위/통합(localhost 미부착·verbatim 포워딩)으로는 확정.

## 7. 후속 / 연관

- NSA 실인증(필요 시), civil 단일-report 엔드포인트 차기 제거, 컬렉션 메타(설명/정렬) 확장.
- 설계 산출물: [`docs/superpowers/plans/2026-06-05-multi-feature-collections-proxy.md`](../superpowers/plans/2026-06-05-multi-feature-collections-proxy.md) (ralplan APPROVE 본). 프록시 패턴은 뉴스레터([단계 11](phase-11-civil-aircraft-report.md))·문서([단계 12](phase-12-document-module.md))와 같은 sanitize/iframe 한 자리에 모인다.
