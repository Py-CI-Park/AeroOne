# Civil Aircraft v1.7 Revision Record

## 1. 릴리스 식별

- Version: **1.7**
- Release date: **2026-07-14**
- Base: **v1.6 Full Archive & Comparison Workspace**
- Release type: **Source Information Architecture & Chart Readability Maintenance**
- 데이터 기준일: **2026-07-13**

## 2. 사용자 요구사항 추적

| ID | 사용자 요구 | v1.7 구현 | 검증 |
|---|---|---|---|
| V17-01 | Sources 출처등급 차트 글자와 박스 겹침 제거 | 긴 단일 라벨을 등급 코드와 짧은 설명의 2줄 라벨로 분리 | SVG text bounding-box 0건 이탈 |
| V17-02 | Sources 차트 가로 스크롤 제거 | 820-unit 반응형 SVG, `min-width:0`, host overflow hidden | 1600/1366/390px scrollWidth=clientWidth |
| V17-03 | 로컬 PDF 아카이브와 출처 레지스트리 하나로 정리 | 55개 출처 카드에 25개 PDF를 `localAttachments`로 연결; 별도 PDF 카드 0개 | Source cards 55, attachment rows 25 |
| V17-04 | 항공기 검증등급 규정을 상단 배치 | Hero/KPI 다음 첫 governance 섹션으로 이동 | DOM 위치 grade < color < search < chart |
| V17-05 | 색상 규정을 체계적 범례로 표시 | 제조사 7색, 비교 6색+마커, 출처등급, 상태/접근성 4개 카드 | policy cards 4 |
| V17-06 | Portal 두 그래프 제목과 박스 겹침 해결 | 카드 헤더만 제목으로 사용하고 SVG 내부 중복 제목 제거 | SVG 텍스트에 차트 제목 0건 |
| V17-07 | 이전 배포파일 삭제 허용 | v1.7 Full Package 검증 후 `/mnt/data`의 v1.4~v1.6 사용자 배포 ZIP/Standalone/개별 QA를 정리 | 최종 배포 단계 수행 |

## 3. 소스 통합 모델

### 3.1 정본

`Civil_Aircraft_Source_Registry_v1.7.json`이 출처 화면과 배포용 출처 메타데이터의 정본입니다.

```text
source record (55)
├─ 출처 ID / 기관 / 등급 / 공식 URL
├─ 검증 필드 / 적용 기체 / 페이지 근거
└─ localAttachments[] (전체 합계 25)
   ├─ 파일명 / 로컬 경로
   ├─ 페이지 수 / 파일 크기
   ├─ SHA-256 / 검증일
   └─ 발행기관 PDF URL
```

### 3.2 ID가 다른 관련 로컬 파일 5건

현행 출처 레코드와 로컬 보관 PDF의 ID가 다른 5건은 별도 카드로 중복 표시하지 않고 관련 레코드에 연결했습니다.

| 로컬 PDF ID | 연결 출처 ID |
|---|---|
| `AIRBUS_A350F_FF_2026` | `AIRBUS_FREIGHTERS` |
| `COMAC_C909_ACAP` | `COMAC_C909_PAGE` |
| `EASA_B767_ARCHIVE` | `EASA_B767_CURRENT` |
| `EASA_B777_ARCHIVE` | `EASA_B777_CURRENT` |
| `EASA_ERJ190_ARCHIVE` | `EASA_ERJ190_CURRENT_PDF` |

### 3.3 유지한 기계검증 파일

`Civil_Aircraft_PDF_Integrity_v1.7.csv`는 출처 레지스트리가 아니라 PDF 25건의 파일 단위 해시·페이지 검증표입니다.

## 4. 변경 파일

### 화면

- `index.html`
- `apps/source_archive.html`
- `assets/js/charts.v1.7.js`
- `assets/js/core.v1.7.js`
- `assets/js/source-archive.v1.7.js`
- `assets/css/civil-aircraft-v1.7.css`

### 데이터·출처

- `data/Civil_Aircraft_Data_v1.7.json` — 메타데이터/릴리스 설명만 변경
- `assets/js/civil-aircraft-data.v1.7.js` — 동일 데이터 번들
- `sources/Civil_Aircraft_Source_Registry_v1.7.json`
- `sources/Civil_Aircraft_Source_Manifest_v1.7.csv`
- `sources/Civil_Aircraft_PDF_Integrity_v1.7.csv`

### 배포·검증

- `README_v1.7.md`
- `CHANGELOG_v1.7.md`
- `REVISION_v1.7.md`
- `qa/*v1.7*`
- `BUILD_INTEGRITY_v1.7.json`
- `SHA256SUMS_v1.7.txt`

## 5. 데이터 변경 여부

다음은 **변경하지 않았습니다.**

- 항공기 65건의 사양값
- 파생 비교지표
- `fieldEvidence`
- `comparisonBasis`
- 검증등급 배정
- SVG 형상 파라미터
- 출처 ID 55건
- PDF 25건의 바이너리

변경된 것은 Source UI의 표시 구조와 배포용 통합 레지스트리 구조입니다.

## 6. QA 결과

| 검증 | 결과 |
|---|---:|
| Static QA | 64/64 PASS |
| Chromium Runtime QA | 41/41 PASS |
| Visual QA | 12/12 PASS |
| Source cards | 55 |
| Local PDF attachment rows | 25 |
| Separate PDF cards | 0 |
| Portal/Source chart horizontal overflow | 0 |
| Revised SVG clipped text | 0 |
| PDF SHA-256/size/header | 25/25 PASS |
| Mobile document overflow | 0 |

## 7. 버전 계보

- v1.2: 비교 UX, 카드, 실척 외형, 직접 레이블
- v1.3: 단일 데이터 원본, 필드 근거, 미공개값 비추정, 공식 PDF 아카이브
- v1.4: Portal 통합, Alias 검색, 검증등급 정의
- v1.5: 카드·실척·포지션 맵·Radar 시각 개선
- v1.6: PDF 25건 복원, Wide Catalog, line-first Radar
- **v1.7: 통합 Source Registry, 상단 거버넌스 범례, 반응형 분포 차트**
