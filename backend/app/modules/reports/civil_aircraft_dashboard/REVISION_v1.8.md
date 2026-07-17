# Civil Aircraft v1.8 Revision Record

## 1. 릴리스 식별

- Version: **1.8**
- Release date: **2026-07-17**
- Base: **v1.7 Source Information Architecture & Chart Readability**
- Release type: **Interactive Silhouette, Export & Lazy-Load Enhancement**
- 데이터 기준일: **2026-07-13** (사양·출처 값 불변)

## 2. 사용자 요구사항 추적

| ID | 사용자 요구 | v1.8 구현 | 검증 |
|---|---|---|---|
| V18-01 | 실척 실루엣 상호작용 | 실루엣 그룹에 `data-aircraft-id`·치수 tooltip 부여, hover 시 치수 툴팁 + 대상 강조(나머지 opacity 0.2), 클릭 시 백과 상세 딥링크(`ca:open-aircraft`) | 라이브 브라우저: hover 툴팁·강조·클릭 모달 확인 |
| V18-02 | 비교 시트/오버레이 내보내기 | Overlay/Panel 공통축척 SVG에 `PNG 저장`·`SVG 저장` 버튼(캔버스 직렬화) | SVG 다운로드 파일명 `Civil_Aircraft_v1.8_Same_Scale_*` 확인 |
| V18-03 | 형상 충실도 향상 | 제조사·세대별 프리셋 11종을 파라메트릭 위 패밀리 오버라이드(`FAMILY_PRESETS`)로 병합; 데이터 미변경, "not a controlled drawing" 유지 | 65기 사양값·출처 diff 0 |
| V18-04 | 측면 날개 후퇴각 | `sideView`에서 `wingSweepDeg`로 익단 시위를 뒤로 밀어 프로파일에 반영 | Side view 렌더 확인 |
| V18-05 | 초기 로딩 경량화 | 포털이 경량 메타(`civil-aircraft-meta.v1.8.js`, 13KB)만 로드; 전체 데이터(338KB)는 백과/비교 진입 시 로드 | 포털 로드 스크립트 2종·`CIVIL_AIRCRAFT_DATA` 미정의 확인 |

## 3. 변경 파일

### 스크립트·스타일

- `assets/js/aircraft-svg.v1.8.js` — 패밀리 프리셋(`FAMILY_PRESETS`/`resolveParams`), 측면 후퇴각, 실루엣 상호작용 훅(`data-aircraft-id`·tooltip).
- `assets/js/dashboard.v1.8.js` — `bindScale`(hover/강조/클릭), PNG 저장 핸들러, 내보내기 파일명 v1.8.
- `assets/js/portal.v1.8.js` — 신규 자립형 포털(메타 기반 KPI·분포·검색).
- `assets/js/civil-aircraft-meta.v1.8.js` — 신규 경량 메타(전체 데이터 파생).
- `index.html` / `apps/*.html` — 스크립트/스타일 참조·버전 표기 v1.8, 실척 섹션 설명에 상호작용 안내.
- `assets/css/civil-aircraft-v1.8.css` — 파일명 갱신(레이아웃 규칙 불변; 내부 역사 주석은 도입 시점 기록으로 보존).

### 데이터·출처

- `data/Civil_Aircraft_Data_v1.8.json` — metadata.version/title/releaseDate/buildNote만 갱신, 항공기 65건 값·파생지표·형상 파라미터 불변.
- `data/Civil_Aircraft_Data_Schema_v1.8.json`, `data/Civil_Aircraft_Data_Dictionary_v1.8.md` — 파일명/식별자 v1.8.
- `sources/Civil_Aircraft_Source_Registry_v1.8.json`, `..._Manifest_v1.8.csv`, `..._PDF_Integrity_v1.8.csv`, `..._External_Source_Links_v1.8.csv`, `README_SOURCES_v1.8.md` — 파일명 v1.8(레코드·해시 불변).

### 배포·검증

- `SHA256SUMS_v1.8.txt` — 저장소 실재 번들 파일 37건 매니페스트.
- `BUILD_INTEGRITY_v1.8.json`, `CHANGELOG_v1.8.md`, `README_v1.8.md`, 본 문서.
- 회귀: `backend/tests/integration/test_reports_api.py`(서빙·CSP·traversal), `backend/tests/unit/test_civil_dashboard_bundle.py`(신규: v1.8 무결성·메타 파생 정합·프리셋/상호작용 마커).

## 4. 불변 보증

- 사양·출처·fieldEvidence·comparisonBasis·미공개값 비추정 정책 그대로.
- 저장소 subset 정책(대용량 PDF/standalone/qa 스냅샷 제외) v1.7과 동일.
- 실루엣 프리셋은 공개 형상 분류의 시각 근사이며 제조사 CAD·인증도면이 아니다.
