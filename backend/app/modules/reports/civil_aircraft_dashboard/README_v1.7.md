# Civil Aircraft Encyclopedia & Comparison Dashboard v1.7

## 실행

압축 해제 후 루트의 `index.html`을 엽니다.

```text
Civil_Aircraft_Encyclopedia_Dashboard_v1.7/index.html
```

로컬 PDF는 패키지의 `sources/pdfs/` 폴더를 사용하므로 전체 폴더 구조를 유지해야 합니다.

## 릴리스 목적

v1.7은 v1.6의 항공기 데이터와 비교 기능을 변경하지 않고 **Sources 정보구조와 Portal/Sources 분포 차트의 가독성만 정리한 유지보수 릴리스**입니다.

- 항공기: 65건
- 출처 레코드: 55건
- 로컬 공식·감항당국 PDF: 25건
- Source/Portal 분포 차트: 반응형, 가로 스크롤 없음
- 검증등급: A+ / A / B+ / B / C
- 출처등급: A1 / A2 / B1 / B2

## v1.7 변경사항

### 1. 출처 화면 통합

기존의 `로컬 공식 PDF 아카이브` 카드 25개와 `출처 레지스트리` 카드 55개를 별도 표시하지 않습니다. 55개 출처 레코드 안에 관련 로컬 PDF를 첨부하는 단일 구조로 변경했습니다.

각 통합 출처 카드에서 다음을 함께 확인합니다.

- 출처 ID·기관·발행연도·자료유형·출처등급
- 검증 필드와 적용 기체
- 공식 페이지 또는 발행기관 PDF
- 로컬 PDF 파일명·페이지 수·크기·페이지 근거
- SHA-256

### 2. 검증·색상 규정 상단 배치

- 항공기 검증등급 규정을 검색과 차트보다 위에 배치
- 제조사 색상 7종
- 비교 선택 1–6의 색상·마커
- 출처등급 배지
- 현행·레거시·목표/개발 상태 배지
- 색상 외 직접 레이블·마커 병행 원칙

### 3. 분포 차트 가독성

- Portal의 `세그먼트 구성`, `검증등급 분포` 차트에서 SVG 내부 중복 제목 제거
- Sources의 `출처 등급 분포` 긴 라벨 잘림 제거
- 차트 SVG를 카드 폭에 맞게 반응형으로 축소
- 데스크톱·모바일 가로 스크롤 제거

## 출처 파일 구조

```text
sources/
├─ Civil_Aircraft_Source_Registry_v1.7.json   # 55개 통합 레코드 + PDF 첨부정보
├─ Civil_Aircraft_Source_Manifest_v1.7.csv    # 출처별 통합 매니페스트
├─ Civil_Aircraft_PDF_Integrity_v1.7.csv      # PDF 25건 무결성 검사표
├─ Civil_Aircraft_External_Source_Links_v1.7.csv
├─ README_SOURCES_v1.7.md
└─ pdfs/                                      # 로컬 PDF 25건
```

별도 PDF 전용 ZIP은 만들지 않았습니다. 같은 25개 파일을 다시 압축해 중복 보관하는 것을 피하고 Full Package를 정본으로 사용합니다.

## 유지된 기능

- v1.6 13열 Wide Catalog와 접이식 상세 패널
- 선 중심 6축 Radar 및 표시 모드
- v1.5 Top / Side / Front / Overlay / 확대 / SVG 저장
- 포지션 맵 레이블 모드·툴팁·집중 보기
- v1.3 필드별 `fieldEvidence`, 미공개값 비추정, 출처등급
- 65개 기체 수치·형상·검증등급

## 사용 제한

- 항속거리 조건은 제조사와 형상별로 동일하지 않습니다.
- SVG는 공개 치수 기반 파라메트릭 비교 도식이며 제조사 CAD 또는 인증도면이 아닙니다.
- 구매, 운항, 공항 적합성, 인증, 구조·공력 해석, 정비 의사결정에 사용하지 마십시오.
- C929의 미공개 MTOW·항속·치수는 추정하지 않습니다.

## 검증

- Static QA: `qa/Civil_Aircraft_QA_Report_v1.7.json`
- Runtime QA: `qa/Civil_Aircraft_QA_Runtime_v1.7.json`
- Visual QA: `qa/Civil_Aircraft_Visual_QA_v1.7.json`
- 배포 파일 해시: `SHA256SUMS_v1.7.txt`
