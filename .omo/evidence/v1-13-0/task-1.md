# Task 1 — 1.12.2 proven-unsafe asset pair 봉쇄 증적

- 시작: `2026-07-10T18:05:33.1836532+09:00`
- 종료: `2026-07-10T18:15:55+09:00`
- 소요: `622초`
- 저장소: `Py-CI-Park/AeroOne`
- 릴리스/태그: release ID `350620445`, tag `1.12.2`
- 태그 커밋: `2f592c46aacab83c3cfa12610a87651082deba5e`

## 실행 범위

- 기존 릴리스와 태그를 유지했다.
- 기존 본문 맨 위에 사용·재배포 금지와 1.12.3 교체 예정 경고를 추가했다.
- ZIP asset ID `469662394`와 paired SHA asset ID `469662393`만 exact ID로 삭제했다.
- 다른 historical release/asset은 변경하지 않았다.
- ZIP을 다운로드·추출·열람하지 않았고 entry stream/content 또는 entry name을 기록하지 않았다.

## 보호 조건과 adversarial 결과

첫 실행은 계획에 기록된 본문 해시와 API raw 본문 해시를 직접 비교해 exit 1로 안전하게 중단됐다. 이 시점의 재조회는 warning 없음, 두 target asset 존재, 두 old URL 200으로 외부 부작용이 없음을 확인했다.

원인은 동시 외부 수정이 아니라 줄바꿈 표현이었다. GitHub API는 원문 CRLF 25개를 보존하고 `gh release view --template`은 LF로 정규화한다. 동일 본문을 다음 두 기준으로 교차 확인한 뒤 재실행했다.

- API raw CRLF body SHA-256: `81dda70a367b73445ee8f433e7312d5f6904288590dbecf32bbf6b5de0cbeabe`
- LF-normalized body SHA-256: `4f1cb3546799c29af7927f6055a5e40ad48dcadb8db5c431e080118784247aef`
- 기존 body `updated_at`: `2026-07-07T23:21:26Z`

## 삭제 전 일치 검증

- ZIP digest: `sha256:b67f595f0b33896015dfe1651f74d1f883de157094bf347bdf81f1d7d0c2e4cd`
- SHA asset digest: `sha256:0b308b6174cd4086eb082b28338ff670fa1b27fb72e9e277dd3e81980490ea9e`
- 다른 asset 수: `0`
- 다른 asset 집합 SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`

## 삭제 후 검증

- release 보존: `true`
- tag 보존: `true`
- latest release tag 유지: `1.12.2`
- warning prefix 확인: `true`
- warning 아래 raw CRLF suffix SHA-256: `81dda70a367b73445ee8f433e7312d5f6904288590dbecf32bbf6b5de0cbeabe`
- warning 아래 LF-normalized suffix SHA-256: `4f1cb3546799c29af7927f6055a5e40ad48dcadb8db5c431e080118784247aef`
- 독립 `gh release view` suffix SHA-256: `4f1cb3546799c29af7927f6055a5e40ad48dcadb8db5c431e080118784247aef`
- target asset count: `0`
- 다른 asset 수: `0`
- 다른 asset 집합 SHA-256: `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`
- ZIP old URL unauthenticated status: `404`
- SHA old URL unauthenticated status: `404`

## 판정

Task 1 acceptance criteria를 모두 충족했다. 비밀값, archive entry name, archive content는 증적에 포함하지 않았다.
