# Unified Source Registry v1.8

- `Civil_Aircraft_Source_Registry_v1.8.json`: 55개의 출처 레코드와 관련 로컬 PDF 첨부정보를 하나의 구조로 관리합니다.
- `Civil_Aircraft_Source_Manifest_v1.8.csv`: 출처별 공식 URL·검증필드·적용기체·로컬 PDF 첨부파일을 한 행에 기록합니다.
- `Civil_Aircraft_PDF_Integrity_v1.8.csv`: 25개 PDF의 SHA-256·크기·페이지 수 검증을 위한 기계검사용 파일입니다. 별도 출처 레지스트리가 아닙니다.
- `pdfs/`: 공식·감항당국 PDF 25건.

## 관련-ID PDF 연결

현행 웹/TCDS 레코드와 ID가 다른 레거시 PDF 5건은 중복 카드로 표시하지 않고 관련 현행 출처에 첨부합니다.

- EASA Boeing 767 archive → `EASA_B767_CURRENT`
- EASA Boeing 777 archive → `EASA_B777_CURRENT`
- EASA ERJ-190 archive → `EASA_ERJ190_CURRENT_PDF`
- COMAC C909 ACAP → `COMAC_C909_PAGE`
- Airbus A350F Facts & Figures → `AIRBUS_FREIGHTERS`
