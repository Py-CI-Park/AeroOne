# CHANGELOG v1.7

Release date: 2026-07-14

## Changed

- Source Archive의 검증등급 규정을 페이지 상단으로 이동
- 색상 규정을 제조사·비교 선택·출처등급·상태/접근성의 4개 범례로 재구성
- 로컬 PDF 25건을 55개 출처 카드 내부 첨부파일로 통합
- Source 검색에 PDF 파일명·첨부 문서 제목을 포함
- Portal 및 Source 분포 차트를 카드 헤더 제목 + 제목 없는 반응형 SVG로 변경
- Source tier 라벨을 `등급 코드 + 짧은 정의`의 2줄 표시로 변경

## Removed

- Source Archive의 별도 `로컬 공식 PDF 아카이브` 카드 섹션
- 중복 `Local PDF Registry` JSON
- 중복 `PDF Archive Index` HTML
- 별도 PDF 전용 v1.7 ZIP 배포
- 분포 SVG 내부의 중복 차트 제목·부제

## Added

- `Civil_Aircraft_Source_Registry_v1.7.json`: 통합 출처 레코드와 `localAttachments`
- `Civil_Aircraft_PDF_Integrity_v1.7.csv`: PDF별 SHA-256·크기·페이지 수 검사표
- 제조사 7색·비교 슬롯 6색/마커·출처등급·상태 범례
- 차트 text bounding-box와 horizontal-overflow Runtime QA

## Unchanged

- 항공기 65건 수치·파생지표·형상 파라미터
- 출처 ID 55건과 필드별 근거
- 로컬 PDF 바이너리 25건과 SHA-256
- v1.6 Wide Catalog·Radar
- v1.5 실척 외형·포지션 맵
- 미공개값 비추정 정책

## QA

- Static QA: 64/64 PASS
- Runtime QA: 41/41 PASS
- Visual QA: 12/12 PASS
- PDF SHA-256·크기·헤더: 25/25 PASS
