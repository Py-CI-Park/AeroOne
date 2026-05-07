# 단계 9 보고서 — L5 `ensure_db_state.py` docstring

- 작성일: 2026-05-07
- 형식: 단일 파일 docstring 보강 + 회귀 방지용 단위 테스트
- 결과: **모듈 / 함수 docstring 으로 종료 코드 0/1/2/3 의미를 코드 안에 남기고, 4분기를 지키는 단위 테스트 7건 추가**

---

## 1. 문제 정의 (L5)

폐쇄망 운영 흐름에서 가장 미묘한 분기는 `setup_offline.bat` 가 `python scripts\ensure_db_state.py` 의 `%ERRORLEVEL%` 을 보고 `alembic upgrade head` 또는 `alembic stamp head` 로 갈라지는 지점이다. 단계 8 의 runbook §6.1 에서 종료 코드 0/2/3 의 의미를 표로 적었지만, 코드 자체에는 어떤 docstring 도 없어 다음 두 위험이 남아 있었다.

- 다음에 본 모듈을 손대는 개발자가 의미를 추적하려면 runbook 을 거꾸로 찾아 읽어야 한다.
- 새 종료 코드가 추가되거나 분기 의미가 미세하게 바뀌면 runbook 만 갱신되고 코드 본문에 흔적이 남지 않을 수 있다.

본 단계는 코드와 문서의 진실 원천을 일치시키는 작은 마무리 작업이다.

---

## 2. 변경 내용

### 2.1 모듈 docstring (신규)

`backend/scripts/ensure_db_state.py` 파일 상단에 모듈 docstring 을 추가했다. 본 모듈의 존재 이유, 종료 코드 0/1/2/3 각각의 정확한 의미와 setup 배치 흐름에서의 다음 단계, 사용 예 (CMD 의 `%ERRORLEVEL%` 분기 패턴), 그리고 sqlite3 표준 라이브러리만 쓰는 이유 (pip install 단계 이전에도 호출 가능) 까지 한 묶음으로 적었다.

### 2.2 `main()` 함수 docstring (신규)

함수 단위 docstring 도 같은 파일 안에 추가했다. 인자 시그니처, 반환 코드별 의미, 부수 효과 (DB 부모 디렉토리 생성 한 번), "잘못된 메타데이터를 자동으로 고치지 않는 이유" (데이터 손상 가능성 있는 결정을 setup 배치 = 운영자 동의 흐름으로 끌어올리기 위함) 를 한 단락으로 명시했다.

### 2.3 `CORE_TABLES` 상수 추출

기존에는 `if {'users', 'newsletters', 'categories'} & tables:` 처럼 하드코딩되어 있던 핵심 테이블 집합을 모듈 상수 `CORE_TABLES` 로 끌어 올렸다. docstring 이 가리키는 "핵심 테이블" 의 실체가 코드 한 군데에서 명확히 보이고, 나중에 도메인 테이블이 늘어나도 한 줄만 고치면 된다.

### 2.4 회귀 방지 테스트 (신규)

`backend/tests/unit/test_ensure_db_state.py` 에 7건의 단위 테스트를 추가했다.

| 테스트 | 시나리오 | 기대 종료 코드 |
|---|---|---|
| `test_missing_arg_returns_1` | 인자 없이 호출 | 1 |
| `test_missing_file_returns_2` | DB 파일이 존재하지 않음 | 2 |
| `test_empty_db_returns_2` | 빈 sqlite 파일 (테이블 없음) | 2 |
| `test_tables_without_alembic_metadata_returns_3` | users / newsletters 테이블만 있고 alembic_version 없음 | 3 |
| `test_alembic_version_filled_returns_0` | alembic_version 행이 채워진 정상 DB | 0 |
| `test_alembic_version_empty_row_returns_3` | alembic_version 테이블은 있으나 행 없음 (손상 케이스) | 3 |
| `test_parent_directory_is_created` | 부모 디렉토리 부재 시 자동 생성 + 종료 코드 2 | 2 + dir 생성 |

각 테스트는 `tmp_path` 픽스처로 격리된 sqlite 파일을 만들어 subprocess 로 실 모듈을 호출하므로, docstring 에 적은 분기 의미와 실제 동작이 정확히 일치하는지를 매 회귀에서 검증한다.

---

## 3. 검증 결과

| 검증 | 결과 |
|---|---|
| 신규 단위 테스트 7건 | 7 passed |
| 직전 phase 7 까지의 회귀 (`pytest tests`) | 66 passed (직전 59 + 신규 7) |
| `python scripts\ensure_db_state.py` 인자 누락 | exit 1 (docstring 명세 일치) |
| 기존 분기 0/2/3 모두 | docstring 표 + runbook §6.1 + 신규 테스트 모두 동일 동작 확인 |

---

## 4. 의도적으로 손대지 않은 것

- **알고리즘 자체** : 테이블 검사 / alembic_version 행 점검 / 종료 코드 매핑 로직은 그대로 유지. 단계 9 의 목적은 "문서를 코드 안에 새기는 것" 이며, 분기 동작 자체는 단계 8 의 시뮬레이션에서 이미 검증된 상태.
- **`SystemExit` 호출 위치** : `main()` 의 반환을 `raise SystemExit(main())` 로 위임하는 기존 패턴을 그대로 유지해 단위 테스트가 함수 반환값을 직접 호출 가능한 상태도 보존.
- **인자 파서** : 단일 위치 인자(파일 경로)로 충분해 argparse 도입은 과한 비용. 인자 누락 시 종료 코드 1 도 기존과 동일.

---

## 5. 결론

코드와 docstring 과 runbook 이 **세 자리에서 동일한 종료 코드 표를 공유**하게 됐다. 추후 분기를 손댈 사람은 docstring 한 군데만 읽어도 의미를 파악할 수 있고, 단위 테스트가 회귀를 자동 차단한다. 단계 9 가 단계 6 / 7 / 8 의 운영 신뢰성을 코드 안에서 한 번 더 매듭짓는다.
