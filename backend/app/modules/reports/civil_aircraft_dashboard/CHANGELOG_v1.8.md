# CHANGELOG v1.8

Release date: 2026-07-17

## Added

- 실척 실루엣 상호작용: 실루엣에 hover 시 치수(Length/Span/Height) 툴팁 + 대상 강조(나머지 흐림), 클릭 시 백과 상세 딥링크. 오버레이(ON)와 개별 패널(OFF) 모두 적용.
- 비교 실척 시트/오버레이의 PNG·SVG 내보내기 버튼(캔버스 직렬화 기반 PNG). 기존 SVG 저장에 PNG 저장을 추가.
- 제조사·세대별 실루엣 프리셋 11종(A320neo, A220, A330neo, A350, A380, 787, 737 MAX, 777X, 747-8, ATR 72, E-Jet E2). 파라메트릭 위 패밀리 파라미터 오버라이드로 후퇴각·윙렛·더블데크·험프 형상 충실도를 높임.
- 측면도 날개 후퇴각(wingSweepDeg) 반영 — 후퇴각이 클수록 익단 시위가 뒤로 밀리는 프로파일.
- `assets/js/civil-aircraft-meta.v1.8.js`: 포털 첫 화면용 경량 메타(KPI·분포·검색 인덱스, 13KB). 전체 데이터의 순수 파생물.

## Changed

- 데이터 지연 로딩(lazy split): 포털(index.html)이 전체 데이터(civil-aircraft-data.v1.8.js, 338KB) 대신 경량 메타만 로드해 첫 화면을 그린다. 백과·비교·출처 페이지 진입 시 전체 데이터를 로드한다.
- 빌드 산출물 파일명·버전 표기를 v1.7 → v1.8 로 갱신(자바스크립트·CSS·데이터·출처 레지스트리·매니페스트·문서 세트).
- 포털 스크립트를 CA 코어 비의존 자립형(portal.v1.8.js)으로 재작성.

## Unchanged (비추정 원칙 유지)

- 항공기 65건의 사양 수치·파생지표·fieldEvidence·comparisonBasis.
- 출처 ID 55건과 로컬 PDF 25건·SHA-256(저장소는 v1.7과 동일하게 대용량 PDF/standalone/qa 스냅샷을 제외한 실행 번들 subset).
- 미공개값 비추정 정책, "not a controlled drawing" 면책. 실루엣 프리셋은 공개 형상 분류의 시각 근사이며 통제도면이 아니다.
- v1.7 Wide Catalog·line-first Radar·position-map 레이블 모드·출처 통합 구조.

## Integrity

- `SHA256SUMS_v1.8.txt`: 저장소 실재 번들 파일 37건의 SHA-256 매니페스트. 회귀 테스트가 실제 파일 해시와 정합을 강제.
- `BUILD_INTEGRITY_v1.8.json`: v1.8 변경 요약·출처 아키텍처·repo subset 정책.
