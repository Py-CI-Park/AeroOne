# RALPLAN — AeroOne 다중 기능 (document/civil/NSA/ladder/calendar) + 외부접속 fetch 버그

> 상태: **APPROVED & 구현 완료** (1.4.0, 단계 13). ralplan 합의 본 — 이 자리는 설계 산출물 아카이브.
> 합의: Architect = SOUND-WITH-CHANGES(전부 반영) → Critic = **APPROVE** (iteration 1). 모든 블로커(C1·C2·M1·M2·M3·B1·B2·B3) 해소.
> 기준 commit: 1.3.2 (`19110d3`). 릴리즈: **1.4.0**. 구현 보고서: [`docs/reports/phase-13-collections-proxy-and-features.md`](../../reports/phase-13-collections-proxy-and-features.md).

## 0. 요청 요약 (7건)
1. Document 목록을 기본 **접힌** 상태로.
2. Document 본문이 **외부 PC 접속 시 "failed to fetch"** → HTML 안 읽힘. 해결.
3. **Civil 카탈로그**도 document처럼 **목록 UI**(여러 카탈로그), 목록 기본 접힘.
4. 뉴스레터 **달력 접으면 더 작게**.
5. 새 **NSA 탭**(비번 `0000` 입력해야 HTML 표시, 구성은 document와 동일).
6. **사다리 게임** 탭(커피 내기용).
7. **상단 탭은 대시보드/뉴스레터/다큐먼트만** 지금처럼 유지.

---

## 1. RALPLAN-DR 요약

### 원칙 (Principles)
- **단일 진실 원천 / DRY**: document·civil·NSA는 같은 "HTML 컬렉션" 동작 → 백엔드 1개 공유 서비스 + 프론트 1개 공유 컴포넌트로 수렴 (AGENTS/CLAUDE.md의 진실원천 색인 철학).
- **불변성·작은 파일**: 기존 코드 스타일(immutable state, 200~400줄) 준수.
- **폐쇄망 안전 우선**: 외부 접속 fetch는 same-origin 프록시로 해결(브라우저가 `localhost` 직접 호출 금지). NSA 게이트는 "보안"이 아니라 "가벼운 가림막"임을 명시.
- **변경 트라이앵글**(CLAUDE.md §2.3): 코드+테스트+문서(+docstring)를 같은 작업에 포함. 병합 전 backend pytest + frontend vitest **둘 다** green.

### 의사결정 동인 (Top 3 Drivers)
1. **외부접속 정확성** — 방문자가 페이지를 열 수 있으면 본문도 무조건 떠야 함(환경변수·CORS·LAN 모드에 의존하지 않는 해법 선호).
2. **확장성/중복 제거** — civil·NSA·향후 컬렉션이 document UI를 그대로 재사용.
3. **요청 7의 제약** — 상단 네비는 3개 고정. 신규(civil/NSA/ladder)는 **대시보드 카드 + 개별 페이지**로 노출(현재 civil-aircraft가 이미 그 패턴: `active="none"`).

### 핵심 근본원인 (#2)
- `fetchDocumentContent()`는 **클라이언트(useEffect)** 에서 `getBrowserApiBase()=NEXT_PUBLIC_API_BASE_URL=http://localhost:18437` 로 직접 호출.
- 방문자 브라우저에서 `localhost`=방문자 자기 PC → 백엔드 없음 → **Failed to fetch**.
- 목록은 **SSR**(`getServerApiBase()`=loopback, 호스트 자신) → 정상. → "목록은 보이는데 본문만 실패" 증상과 정확히 일치.
- 뉴스레터 본문은 same-origin 프록시 `/api/frontend/newsletters/[...segments]` 경유라 외부에서도 정상. **document는 이 프록시를 안 거치는 게 유일한 차이.**

### 검토한 대안 (Viable Options ≥2)
**옵션 A — same-origin BFF 프록시 (채택)**
뉴스레터와 동일하게 컬렉션 본문(+NSA 목록)을 Next 라우트로 프록시. 브라우저는 same-origin(`/api/frontend/collections/...`) 호출, Next 서버가 `SERVER_API_BASE_URL`(loopback)로 업스트림.
- 장점: 페이지가 열리는 모든 방문자에게 **무조건** 동작. CORS·NEXT_PUBLIC·LAN모드 무관. 기존 검증된 패턴 재사용.
- 단점: 라우트 파일 1개 + api.ts 호출경로 변경. 본문 트래픽이 Next 1홉 경유(폐쇄망 LAN이라 무시 가능).

**옵션 B — LAN 모드 안내(운영)만**
`setup_offline.bat --allow-host=<IP>` 로 `NEXT_PUBLIC_API_BASE_URL=http://<host>:18437` 재설정 후 frontend rebuild.
- 장점: 코드 변경 0.
- 단점: `NEXT_PUBLIC_*`는 **빌드타임 인라인** → 재빌드 필요, IP 바뀌면 또 깨짐. 운영자가 5자리 정합을 매번 맞춰야 함(이미 실패한 경로). **거부**(근본 해결 아님).

**옵션 C — read-beacon처럼 직접호출 유지 + CORS 확장**
- 단점: 여전히 NEXT_PUBLIC가 LAN IP여야 하고 와일드카드 CORS는 폐쇄망 정책 위반. **거부**.

→ **A 채택**. (B는 보조 문서 안내로만 병기, read-beacon은 의도상 직접호출 유지.)

### 사전부검 (Pre-mortem, deliberate) — 4 시나리오
0. **#2가 "초록 CI"인데 실제로는 여전히 깨진 채 출시**(이 버그 클래스의 전례 = option B 식 잘못된 자리 수정). 단위테스트는 fetch를 mock 하므로 localhost↔상대경로 회귀를 못 잡고, 수동 확인이 선택사항이면 그대로 통과. *완화*: (a) `api.test.ts`에 same-origin 경로 + localhost 베이스 미부착 단언(원버그 캐처), (b) 외부호스트 본문로드를 **필수 기록 게이트**로 승격(§4 게이트), (c) 프록시 액세스 로그를 `Tested:` 에 박음.
1. **NSA 게이트가 "보안"으로 오인** → 비번이 클라이언트 코드/번들에 노출, 백엔드 엔드포인트는 폐쇄망 내 무인증. *완화*: UI·문서·docstring에 "casual gate, not auth" 명시. 향후 실인증은 후속 과제로 분리. 민감자료는 NSA에 넣지 말 것 안내.
2. **컬렉션 프록시가 경로탈출(`../`) 허용** → 임의 파일 노출. *완화*: 백엔드 `StorageService.ensure_within_root` 재사용(기존 document와 동일 path-guard) + 컬렉션 화이트리스트(`document|civil|nsa`만, 그 외 404) + 프록시 라우트도 첫 세그먼트 화이트리스트 검증.
3. **기본 접힘 전환이 기존 테스트/UX 깨뜨림** → `documents-workspace.test.tsx` 등 빨강, 첫 문서 자동선택 안 되면 빈 화면. *완화*: 접힘이어도 `selected=documents[0]` 자동 로드(전체폭 뷰어에 바로 표시). 영향 테스트 동반 수정.

---

## 1.5 Architect 반영 (accepted deltas)
- **CSP 헤더 포워딩 불필요(정정)**: 본문은 백엔드가 **JSON** `{content_html}`로 주고 프론트는 `html-viewer.tsx`의 **`srcDoc`** 로 주입(=`src` 아님). 따라서 프록시는 `content-type`만 전달하면 됨(뉴스레터 allowlist에 CSP 없음에도 정상). 프록시가 CSP를 포워드할 필요 없음 — 사전부검/요구에서 CSP 항목 삭제.
- **쿼리스트링 verbatim 포워딩(필수) + 세그먼트 인코딩 유지(B2, 최고위험)**: content 본문 경로는 `?path=항공/상용기.html` **쿼리**. 프록시는 `request.nextUrl.search`를 **그대로** 전달(쿼리 `path` **재인코딩 금지** → 이중 인코딩 시 한글/폴더 문서 404). **단 "재인코딩 금지"는 쿼리스트링에만 적용**된다 — `[...segments]` **경로 세그먼트는 반드시 `encodeURIComponent`(per-segment) 유지**(`buildNewsletterUpstreamPath` 그대로)해 `../` 등 업스트림 경로 주입/SSRF를 차단. 즉 `buildCollectionUpstreamPath`는 세그먼트는 per-segment 인코딩, 쿼리는 verbatim. 비ASCII+슬래시 쿼리 + traversal 세그먼트 양쪽 테스트.
- **read-beacon 직접호출 유지(확인)**: `recordNewsletterRead`는 reader LAN IP 위해 직접호출 유지(프록시 금지). 인증/쿠키 필요한 admin 경로도 프록시 대상 아님.
- **NSA 워크스페이스 플래그 경량화**: `DocumentsWorkspace`에 `fetchListClientSide` 플래그 **추가 안 함**. NSA는 **게이트 래퍼**가 언락 후 `fetchCollectionList('nsa')`(same-origin 프록시, 클라이언트)로 목록을 받아 `documents` prop으로 워크스페이스에 주입. 워크스페이스는 항상 데이터 주도(비동기 모드 모름). 본문 select 시에는 `fetchCollectionContent('nsa', path)` 프록시 사용.
- **기본 접힘 default 확정**: `DocumentsWorkspace`의 `defaultSidebarOpen` **기본값 false**, `defaultFoldersOpen` **기본값 false**(접힘). document/civil/nsa 모두 동일. → 기존 `documents-workspace.test.tsx`의 **펼침 전제 단언(`doc-folder-항공` 노출/트리 기본표시)을 반드시 재작성**.
- **목록 mock 재배선**: 워크스페이스가 `fetchCollectionContent(collection, path)`를 직접 호출하도록 변경 → `documents-workspace.test.tsx`의 mock을 `fetchDocumentContent`→`fetchCollectionContent`로 교체하고 호출 단언 갱신.
- **백엔드 DRY는 렌더/path-guard에만**: 공유 `HtmlCollectionService.render_one`(sanitize+`ensure_within_root`+`.html`/`_debug` 가드)로 단일화. 기존 `documents`/`reports` 라우터는 **공유 서비스에 위임**(병렬 복제 금지)해 진짜 단일 구현. `reports`는 `_latest_report` 선택정책만 보존.
- **whitelist는 config 해석 루트로**: `{document→document_root_path, civil→civil_aircraft_root_path, nsa→nsa_root_path}`. 미등록 collection은 **파일시스템 접근 전에 404**. 컬렉션별 `StorageService(root, managed_storage_root)`로 올바른 루트 기준 가드.
- **civil-as-list는 사용자 명시 요구(#3)** → Architect의 "civil 단일보고서 contract 보존" 권고와 충돌하나, 요청이 명시적이므로 **list로 전환을 채택**(accepted tradeoff). 단, (a) civil도 이제 **클라이언트 본문 fetch가 생기므로 프록시 대상(#2 동일 버그가 생기기 전에 예방)**, (b) `civil-aircraft-report-page.test.tsx`의 "단일 렌더/`civil-aircraft-report` testid" 단언을 **list UI로 재작성**, (c) **(B1 정정)** civil 페이지는 list UI(`DocumentsWorkspace collection="civil"`)로 **전환**되므로, 전환 후 `CivilAircraftReport` 컴포넌트/`fetchCivilAircraftReport`/`reports/civil-aircraft` 엔드포인트는 **어떤 화면도 렌더하지 않는 "removal-deferred(1릴리즈)" 상태**다. 이는 두 UI가 동시에 라이브가 아님을 의미 — 단일보고서로 돌아가려면 `page.tsx` revert가 필요(엔드포인트만 살아있는 "롤백 극장" 표현 금지). 백엔드 엔드포인트/테스트는 회귀 안전망으로 1릴리즈 남기되, 차기 release에서 제거.
- **대시보드 카운트 확정**: 현재 active 3(newsletter/civil/document)+coming 2(announcement/schedule). NSA·Ladder(active) 추가 → **active 5 / coming 2**. `home-page.test.tsx` 기대치 이 숫자로 갱신.
- **NSA env override 표기**: `NEXT_PUBLIC_NSA_GATE_CODE`도 **빌드타임 인라인=번들 노출**(option B와 같은 한계). "구성가능"이라는 오해 방지 위해 cosmetic only로 문서화하거나 생략. 비번 `0000` 하드코딩으로 충분.

---

## 2. 아키텍처 변경 (백엔드)

### 2.1 공유 서비스 추출 + 컬렉션 라우터
- **신규** `backend/app/modules/collections/` (또는 documents 모듈을 일반화):
  - `service.py` — `HtmlCollectionService`: `discover_list(root) -> [{path,name,folder}]`, `render_one(root, path) -> html` (현 `documents/api/public.py::_discover_documents` + `get_document_html` 로직을 path-guard 포함해 이관/공유).
  - `api/public.py` — 라우터 mount `/api/v1/collections`:
    - `GET /api/v1/collections/{collection}/list`
    - `GET /api/v1/collections/{collection}/content/html?path=`
    - **화이트리스트** `{document: document_root_path, civil: civil_aircraft_root_path, nsa: nsa_root_path}`; 미등록 collection → 404; path는 `.html`만, `_debug.html` 제외, `ensure_within_root`로 루트 밖 차단.
- **config 추가** (`backend/app/core/config.py`): `nsa_root: str = './_database/nsa'` + `nsa_root_path` property. property는 기존 패턴대로 **`self._resolve_path(self.nsa_root)`** 사용(상대/절대 동등 처리, 폐쇄망 경로 패리티). (`document_root`, `civil_aircraft_root` 는 이미 존재.)
- **main.py**: `collections` 라우터 include(`prefix='/api/v1/collections'`).
- **호환성(저위험)**: 기존 `/api/v1/documents/*`, `/api/v1/reports/civil-aircraft/content/html` 라우터는 이번 릴리즈에서 **유지**(내부적으로 공유 서비스에 위임하도록 리팩터만; 엔드포인트 제거 X). civil 프론트는 신규 list로 전환하지만 단일-report 엔드포인트는 1릴리즈 deprecated로 남겨 롤백 여지 확보.

### 2.2 폐쇄망 디렉토리
- `_database/nsa/` 생성 안내(런북). civil은 기존 `_database/civil_aircraft/`에 **여러 .html**을 넣으면 목록화됨(현재 단일 → 다중으로 사용법 확장).

---

## 3. 프론트엔드 변경

### 3.1 same-origin 컬렉션 프록시 (#2 해결)
- **신규** `frontend/app/api/frontend/collections/[...segments]/route.ts` — 뉴스레터 프록시(`[...segments]/route.ts`) 그대로 복제:
  - `GET` → `${getServerApiBase()}/api/v1/collections/<segments>?<search>` 포워드, 응답 헤더 화이트리스트 전달, 실패 502.
  - 첫 세그먼트 화이트리스트(`document|civil|nsa`) 검증(미일치 404).
- `frontend/lib/newsletter-observability.ts` 와 같은 자리에 `buildCollectionProxyPath`/`buildCollectionUpstreamPath` 헬퍼 추가(또는 별도 `collection-proxy.ts`).
- **api.ts**:
  - `fetchCollectionContent(collection, path)` → same-origin `'/api/frontend/collections/'+collection+'/content/html?path='+encodeURIComponent(path)` (`cache:'no-store'`). **base URL 안 붙임**(상대경로=same-origin).
  - `fetchCollectionList(collection)`(클라이언트용, NSA 언락 후) → same-origin proxy.
  - 기존 `fetchDocumentContent` 는 `fetchCollectionContent('document', path)`로 위임(시그니처 유지) → **#2 즉시 해결**.
  - SSR 목록(document/civil)은 서버컴포넌트에서 `getServerApiBase()` 직접 호출 유지(서버사이드, 정상).

### 3.2 DocumentsWorkspace 일반화 + 기본 접힘 (#1, #3)
- `documents-workspace.tsx` props 확장:
  - `collection: 'document'|'civil'|'nsa'`(기본 `'document'`) → 본문 fetch에 사용.
  - `defaultSidebarOpen?: boolean`(기본 **false** = 목록 접힘) → `useState(defaultSidebarOpen)`.
  - `defaultFoldersOpen?: boolean`(기본 **false**) → `openFolders` 초기값을 빈 Set 으로(현재는 전체 펼침). 즉 "목록 기본 접혀있는" 두 의미(사이드바+폴더) 모두 충족.
  - `emptyHint?` 등 빈 상태 문구 파라미터화(civil/nsa 안내문 차등).
- 접힘 기본이어도 `selected=documents[0]` 자동선택 → 전체폭 뷰어에 즉시 표시 + 상단 셀렉트로 전환.
- 본문 fetch를 `fetchCollectionContent(collection, path)`로 교체.

### 3.3 Civil 카탈로그 목록화 (#3)
- `app/reports/civil-aircraft/page.tsx`:
  - SSR로 `fetchCollectionList('civil')` (서버 직접) → `DocumentsWorkspace collection="civil" defaultSidebarOpen={false}` 렌더.
  - 빈 목록 시 "_database/civil_aircraft 에 HTML을 넣으세요" 안내 유지.
- 단일-report 컴포넌트(`civil-aircraft-report.tsx`)는 목록 UI로 **대체**(렌더 안 됨 → removal-deferred, §1.5(c)/B1 참조). 대시보드 카드(이미 존재) 그대로.

### 3.4 NSA 탭 (#5)
- **신규** `app/nsa/page.tsx` — SSR은 목록을 **미리 안 받음**(게이트 전 노출 방지). `active="none"`.
- **신규** `components/collections/collection-password-gate.tsx`(client):
  - 비번 입력(기본 `0000`, 가능하면 `NEXT_PUBLIC_NSA_GATE_CODE` 로 오버라이드) 일치 전 입력폼만, 일치 시 자식 렌더.
  - **명시**: 클라이언트 가림막(보안 아님). 백엔드 무인증. 민감자료 금지 안내.
- 언락 시퀀스(M3 확정 — `fetchListClientSide` 플래그 **추가 안 함**): 게이트 래퍼가 정답 입력 후 `fetchCollectionList('nsa')`(same-origin 프록시, 클라이언트)로 목록을 받아, `<DocumentsWorkspace documents={list} collection="nsa" defaultSidebarOpen={false} />` 로 **prop 주입**. 워크스페이스는 항상 `documents`를 받는 데이터 주도 컴포넌트로 유지(비동기/게이트 모드 모름). 언락 전엔 목록/본문 요청이 **전혀 발생하지 않음**(테스트로 단언).
- 본문 select 시 `fetchCollectionContent('nsa', path)`(same-origin 프록시) 사용.
- 구성/스타일은 document와 동일(같은 `DocumentsWorkspace` 재사용).
- 게이트 컴포넌트 상단에 "casual gate, not auth / 백엔드 무인증 / 민감자료 금지" docstring 주석(변경 트라이앵글 4번째 자리).

### 3.5 사다리 게임 (#6)
- **신규** `app/games/ladder/page.tsx` + `components/games/ladder-game.tsx`(client, 순수 프론트, 백엔드 없음):
  - 참가자 N명 입력 + 상품 N개(예: "커피" 1, 나머지 "꽝") 입력.
  - 랜덤 사다리 생성 → 참가자→상품 매핑 계산/표시(결과 공개).
  - **테스트 가능성(M2 확정)**: 매핑 로직을 순수 함수 `computeLadderMapping(participants, prizes, rng = Math.random)`로 분리하고 `rng`를 **주입 가능**하게 한다. 런타임은 `Math.random`, 테스트는 시드/스텁 rng 주입. `ladder-game.test.tsx`는 (a) 고정 rng로 결정적 매핑 단언 + (b) 임의 rng에서도 성립하는 **불변식**(결과는 입력의 **전단사(bijection)**, 정확히 "커피" 1개/"꽝" N-1개, 모든 참가자가 정확히 1개 상품) 단언.
  - `active="none"`, AppShell 사용. 컴포넌트 상단 docstring: "순수 프론트, 백엔드 없음"(트라이앵글 4번째 자리).

### 3.6 대시보드 카드 (#7 충족)
- `app/page.tsx` MODULES 에 **NSA**(href `/nsa`), **Ladder**(href `/games/ladder`) 카드 추가. civil은 이미 있음.
- **상단 NAV_ITEMS 변경 없음**(dashboard/newsletter/document) → 요청 7 충족.

### 3.7 뉴스레터 달력 컴팩트 접힘 (#4)
- `components/newsletter/newsletter-date-calendar.tsx`: `open=false`일 때
  - **측정 가능한 compact(M1 확정)**: 접힘 시 컨테이너가 `p-2`(펼침 시 `p-4`)를 갖고, 설명 `<p>`(발행일 선택 안내)와 월 `<h2>`/요일 라벨이 **DOM에서 제거**(`hidden` 아닌 미렌더). 접힘 상태 = "달력 펼치기" 버튼만 있는 **슬림 바**.
  - **기존 테스트 충돌 명시(M1)**: `newsletter-date-calendar.test.tsx`의 접힘 상태 단언들(현재 `getByText('2026년 3월')` 및 요일 라벨이 접힘에서도 존재한다고 가정하는 라인 ≈26–29)을 **재작성**해야 한다 → 접힘 시 `queryByText('2026년 3월')`==null, 컨테이너에 `p-2` 클래스 존재, 펼침 토글 후 다시 표시.
  - 부모 그리드(reading 레이아웃)가 큰 min-height를 강제하지 않는지 확인(필요시 `h-full` 조정). → 검증단계에서 실측.

---

## 4. 테스트 (변경 트라이앵글)

### 4.0 요청별 수용기준 (각 요청 = 명명된 테스트/관측 가능 체크)
| # | 요청 | 수용기준(명명된 체크) |
|---|---|---|
| 1 | Document 목록 기본 접힘 | `documents-workspace.test.tsx`: 기본 렌더에 `documents-tree` 없음 + `documents-select` 존재, 첫 문서 자동선택·본문 표시 |
| 2 | 외부접속 본문 fetch | `api.test.ts`(same-origin `/api/frontend/collections/` + localhost 미부착) + `collections-proxy-route.test.ts`(포워드/화이트리스트/502/`?path=한글/…` verbatim) + **필수 외부호스트 수동 측정**(로그 줄을 `Tested:`에) |
| 3 | Civil 다중 카탈로그 목록 | 백엔드 `test_collections_api`(civil list 다항목) + `civil-aircraft-report-page.test.tsx` list UI·기본 접힘으로 재작성 |
| 4 | 달력 접으면 더 작게 | `newsletter-date-calendar.test.tsx`: 접힘 시 `p-2`·설명/`월 라벨` 미렌더, 펼치면 복귀(기존 라인 ≈26–29 재작성) |
| 5 | NSA(비번 0000) | `collection-password-gate.test.tsx`(오답 차단/정답 언락/**언락 전 요청 0건**) + `nsa-page.test.tsx` |
| 6 | 사다리 게임 | `ladder-game.test.tsx`: 고정 rng 결정적 매핑 + 임의 rng 불변식(전단사·"커피"1/"꽝"N-1) |
| 7 | 상단 탭 3개 유지 | `app-shell.test.tsx`: NAV_ITEMS 정확히 3개(회귀 가드) + `home-page.test.tsx` 카운트를 **MODULES에서 파생한 방식과 동일하게**(active 필터) 단언 — 리터럴 "5/2" 문자열 매칭 금지(B3). 현 구성 기준 결과는 active 5/coming 2. |


### 백엔드 (`backend/tests/unit|integration`)
- collections: `list`/`content/html` 정상, 미등록 collection→404, `../` 경로탈출→400, `.html` 외/`_debug.html`→404, 빈 루트→빈 목록.
- nsa_root config 기본값/override.
- 기존 documents/reports 테스트 green 유지(위임 리팩터 회귀).

### 프론트엔드 (`frontend/tests` Vitest)
- `documents-workspace.test.tsx`: **기본 접힘**(사이드바/폴더), 첫 문서 자동선택·로드. mock을 `fetchDocumentContent`→`fetchCollectionContent`로 교체하고 호출 단언 갱신.
- **(C1 회귀 가드 — 원버그를 잡는 단언)** `api.test.ts`: `fetchCollectionContent('document','x.html')`가 `fetch`를 **`/api/frontend/collections/` 로 시작하는 상대(same-origin) 경로**로 호출하고 **`http://localhost:18437` 베이스가 절대 안 붙음**을 단언. (이 단언 하나가 최초 버그를 잡았을 유일한 테스트.) `fetchCollectionList`도 동일.
- **(C2 인코딩 회귀)** `collections-proxy-route.test.ts`: 업스트림 포워드/첫세그먼트 화이트리스트/502 + **`?path=항공/상용기.html`(비ASCII+슬래시)가 업스트림 URL에 바이트 동일(단일 인코딩)로 도달**(이중 인코딩 금지). 템플릿은 `newsletters-route.test.ts`(쿼리 verbatim 통과 케이스).
- `civil-aircraft-report-page.test.tsx`: 목록 UI 렌더(다중 항목)·기본 접힘.
- 신규 `collection-password-gate.test.tsx`(오답 차단/정답 언락/언락 전 fetch 미발생).
- 신규 `nsa-page.test.tsx`.
- 신규 `ladder-game.test.tsx`(입력→결과 매핑, N=참가자/상품 일치).
- `home-page.test.tsx`: NSA·Ladder 카드 추가 반영(active/coming 카운트).
- `app-shell.test.tsx`: 상단 NAV 여전히 3개만(회귀 가드).
- `newsletter-date-calendar.test.tsx`: 접힘 시 설명/그리드 숨김·컴팩트.

### 게이트 (CLAUDE.md §2.6)
- 병합 전 `cd backend && pytest tests`(카운트 기록) **및** `cd frontend && npm run test`(카운트 기록) 둘 다 green.
- **(C1 — #2 의 필수 수용기준, "가능하면" 아님)** 외부 PC 또는 LAN IP로 `http://<host>:29501/documents` 접속 → **하위 폴더의 한글명 문서 선택 → 본문 렌더 확인**. 증거로 프록시 액세스 로그 `[FRONTEND][API ] 200 /api/v1/collections/document/content/html?path=...` 한 줄을 commit `Tested:` trailer 에 붙인다. 단위테스트(fetch mock)는 same-origin 경로만 보장하지 실제 외부호스트 동작을 증명하지 못하므로, 이 수동 측정값은 **릴리즈 게이트의 필수 항목**(§2.6 "명시적 측정값"). 이 기록 없이는 "#2 해결" 보고 금지.
- NSA: 언락 전 네트워크 요청 0건(테스트), 정답 입력 후에만 목록/본문 로드.

---

## 5. 문서/릴리즈 (실행 단계, 승인 후)
- `docs/INDEX.md`(wiki 입구), `docs/CLOSED_NETWORK_GUIDE.md`/`docs/runbook/windows-offline.md`에 (a) document 본문 same-origin 프록시로 외부접속 해결, (b) `_database/nsa` 추가, (c) civil 다중 카탈로그 사용법, (d) NSA 가림막 한계 명시.
- `frontend/lib/changelog.ts` + README 배지/검증 줄 = **버전 표기 단독 commit**(다른 변경과 분리, §2.6).
- 버전 1.4.0 제안. merge `--no-ff` 본문=release note 초안.
- ZIP asset upload(§2.7) 의무: `offline_package.bat` → `gh release upload` → `gh release view --json assets` 확인.

## 6. ADR
- **Decision**: same-origin BFF 프록시로 컬렉션 본문 제공 + document/civil/NSA를 1개 백엔드 공유서비스/화이트리스트 라우터 + 1개 프론트 컴포넌트로 일반화. 신규는 대시보드 카드로만 노출(상단 3탭 유지). NSA는 클라이언트 가림막.
- **Drivers**: 외부접속 무조건 동작, DRY/확장성, 요청 7 제약.
- **Alternatives**: LAN 모드 재설정(빌드타임 한계로 거부), CORS 와일드카드(정책 위반 거부), 컬렉션별 라우터 복제(중복으로 거부).
- **Consequences**: 본문 1홉 프록시 경유(LAN 무시 가능). NSA는 실보안 아님(명시). civil 단일-report 엔드포인트 1릴리즈 deprecated.
- **Follow-ups**: NSA 실인증(필요 시), 컬렉션 메타(설명/정렬) 확장, civil 단일-report 엔드포인트 제거(차기).

## 7. 미해결 가정 (승인 시 확정)
- **#1/#3 "접힘"** = 사이드바+폴더 모두 기본 접힘으로 해석(둘 다 적용). 만약 "폴더만/사이드바만"을 의도했다면 알려주세요.
- **#7** 신규 항목은 **대시보드 카드+페이지**로 노출(상단 3탭 불변)로 해석.
- NSA 비번 `0000` 하드코딩(또는 env override). 실인증 불요로 가정.
