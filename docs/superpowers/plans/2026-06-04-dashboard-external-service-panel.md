# 대시보드 외부 서비스 / 포트 연결 패널 (구현 계획)

- 작성일: 2026-06-04
- 상태: **계획만 (미구현)** — 운영자 요청으로 문서만 선반영. 실제 구현은 별도 사이클에서 진행한다.
- 관련 버그 수정: 1.1.1 `/theme` 리다이렉트 0.0.0.0 회피 (이 문서의 핵심 제약이 같은 원인에서 나온다)

---

## 1. 배경 / 동기

현재 대시보드(`frontend/app/page.tsx`)는 모듈 카드 4개를 보여준다 — Newsletter(active) + Announcement / Schedule / Document(coming soon, 비활성 `div`). 운영자는 이 대시보드를 폐쇄망 LAN 안의 **다른 사내 서비스로 가는 허브**로 쓰고 싶어 한다. 구체적으로:

1. 비활성 "coming soon" 카드 외에 **운영자가 정의한 카드를 더 추가**할 수 있어야 한다.
2. 각 카드가 **같은 서버(같은 IP)의 다른 포트**(예: `:8080` 모니터링 대시보드)나 **외부 고정 URL**로 연결될 수 있어야 한다.

즉 "모듈 카드 = 내부 라우트(`/newsletters`)" 라는 현재 가정을, "카드 = 내부 라우트 또는 외부/포트 링크" 로 확장한다.

---

## 2. 핵심 제약 — 호스트를 고정하지 말 것 (1.1.1 버그의 교훈)

이 기능의 가장 중요한 함정은 1.1.1 에서 고친 다크모드 0.0.0.0 버그와 **같은 뿌리**다.

- 기본 LAN(1.0.22+)에서 서비스는 `0.0.0.0` 으로 바인딩되고, 사용자는 `http://<LAN-IP>:29501/` 또는 `http://localhost:29501/` 등 **제각각의 호스트**로 접속한다.
- 포트 링크를 `http://localhost:8080/` 처럼 **서버 기준으로 고정**하면, LAN 의 다른 PC 사용자는 `localhost` = 자기 PC 로 해석해 엉뚱한 곳으로 가거나 연결이 끊긴다.
- 서버 사이드에서 `request.url` 의 origin 으로 절대 URL 을 만들면 `0.0.0.0` 으로 오염된다(1.1.1 의 원인 그대로).

**결론:** 같은 IP 다른 포트로 가는 링크는 반드시 **브라우저가 현재 접속한 호스트**를 기준으로 만들어야 한다. 즉 클라이언트에서 `window.location.protocol` + `window.location.hostname` 을 읽고 포트만 교체한다. 서버에서 호스트를 추측하지 않는다.

---

## 3. 제안 설계

### 3.1 데이터 모델 확장

`MODULES` 배열 항목에 링크 종류를 구분하는 필드를 추가한다(불변 객체, 기존 항목과 호환).

```ts
type ModuleLink =
  | { kind: 'internal'; href: string }                 // 기존 Next 라우트 (예: '/newsletters')
  | { kind: 'port'; port: number; path?: string }      // 같은 호스트의 다른 포트
  | { kind: 'external'; url: string };                  // 외부 고정 URL
```

- `internal` — 지금처럼 `<Link href>`.
- `port` — 클라이언트에서 `${location.protocol}//${location.hostname}:${port}${path ?? '/'}` 로 계산해 일반 `<a>` (새 탭 권장).
- `external` — 고정 절대 URL 을 일반 `<a>` (새 탭 + `rel="noopener noreferrer"`).

### 3.2 컴포넌트

- `ServiceCard` 는 현재 `active` 면 `<Link>`, 아니면 `div`. 여기에 외부/포트 분기를 더한다.
- `port` 종류는 호스트를 런타임에 읽어야 하므로 작은 **클라이언트 컴포넌트**(`'use client'`)로 분리한다. 예: `PortLinkCard` 또는 카드 내부의 `PortAnchor`.
  - SSR 시점에는 `window` 가 없으므로 hydration 전에는 `href="#"` 또는 비활성으로 두고, 마운트 후 실제 href 를 채운다(또는 `suppressHydrationWarning`).
- `internal`/`external` 은 서버 컴포넌트로 충분(호스트 계산 불필요).

### 3.3 카운트 문구 단일화

대시보드 상단 `titleMeta="1 active · 3 coming soon"` 가 **하드코딩**돼 있다(`page.tsx`). 카드가 늘면 어긋난다. `MODULES` 에서 active/coming-soon 개수를 계산해 문구를 파생하도록 바꾼다.

---

## 4. 구현 단계 (TDD)

1. `ModuleLink` 타입과 `MODULES` 데이터 확장 + `titleMeta` 파생 계산. (단위 테스트: 개수 파생)
2. `ServiceCard` 에 `external` 분기 추가(일반 `<a target="_blank" rel>`). (컴포넌트 테스트)
3. `port` 링크용 클라이언트 컴포넌트 추가 — `window.location.hostname` 기준 href 계산, SSR 가드. (컴포넌트 테스트: hostname mock 으로 포트만 교체 검증)
4. 문서 동기화 — `docs/INDEX.md` §6 대시보드 행, 본 plan 의 spec 짝(`docs/superpowers/specs/2026-06-04-...-design.md`) 추가.

---

## 5. 수용 기준

- [ ] 운영자가 `MODULES` 에 한 줄로 내부/포트/외부 카드를 추가할 수 있다.
- [ ] 포트 카드는 LAN 의 다른 PC 에서 눌러도 **그 PC 가 접속한 호스트의** 해당 포트로 연결된다(localhost 고정 금지).
- [ ] 외부 카드는 새 탭 + `rel="noopener noreferrer"` 로 열린다.
- [ ] 상단 active/coming-soon 카운트가 `MODULES` 에서 자동 파생된다.
- [ ] 비활성 카드의 기존 동작(비링크 `div`)은 회귀 없이 유지된다.

---

## 6. 리스크 / 미해결 질문

- **대상 서비스 가용성** — 포트 링크가 가리키는 서비스가 `0.0.0.0`(또는 LAN IP)로 떠 있고 방화벽이 열려 있어야(`scripts/allow_lan_firewall.cmd` 와 동일 고려) LAN 의 다른 PC 에서 닿는다. 이는 AeroOne 외부 조건이라 본 기능이 보장하지 못한다 — 카드 클릭 실패 시 안내가 필요할 수 있다.
- **혼합 콘텐츠(mixed content)** — 대시보드가 향후 HTTPS 로 가고 대상이 HTTP 면 브라우저가 차단한다. 현재는 전부 HTTP 라 무관.
- **카드 정의 위치** — 코드 상수(`MODULES`)로 둘지, `.env`/설정 파일로 빼서 운영자가 코드 수정 없이 바꾸게 할지는 별도 결정 필요.
- **권한/노출** — 외부 URL 카드는 폐쇄망 정책상 어디까지 허용할지 운영자 합의 필요.

---

## 7. 범위 밖 (이번 문서에서 다루지 않음)

- 실제 코드 구현(별도 사이클).
- 카드 정의를 런타임 설정으로 외부화하는 작업.
- 대상 서비스의 헬스체크/가용성 표시.
