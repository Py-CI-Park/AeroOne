# Aero Work 울트라골 G001~G007 — 2.0.0 후보 정리 보고서

- 작성일: 2026-07-20
- 브랜치: `aero-work-dev` (HEAD `7d94464`; 이번 리뷰 해소 커밋은 리더가 추후 기입)
- 관계: [`../dev_plan/aero-work-full-parity-plan.md`](../dev_plan/aero-work-full-parity-plan.md)의 F8 "남은 후속"([`aero-work-phase-f1-f8.md`](aero-work-phase-f1-f8.md) §3)을 채운 후속 사이클. F1~F8(기본 구현)이 세운 골격 위에 G001~G007이 릴리스 후보 수준 깊이를 더한다.
- 한 줄: SSE 스트리밍·분류체계 마법사+업무 허브·FTS5 키워드 검색(백그라운드 재색인)·종이 미리보기+수정 지시 재생성·업무대화 첨부+LLM 보조 라우팅 5개 기능 스토리(G001~G006)를 각각 기능 구현 → 아키텍트 재리뷰 → 레드팀 스위트 게이트로 마감했고, G007 Playwright E2E·ZIP QA·2.0.0-dev 버전 정합까지 완료했다. 리뷰 지적(P1 1·P2 4·P3 1)은 본 워킹트리에서 해소하며 커밋 해시는 리더 커밋 후 채운다.

---

## 1. 스토리별 요약

각 스토리는 "기능 브랜치 병합 → 아키텍트 재리뷰(BLOCK/지적 해소) → 레드팀 스위트 → 체크포인트" 순서로 게이트를 거쳤다. collect-only 수치를 통과 수치처럼 쓰던 표현은 제거한다. 현재 보고서의 전량 실측은 Playwright E2E **1 passed(8.8s)**, 프런트 vitest **652/652 passed**, 백엔드 전량 **1 failed 후 격리 결함을 `7d94464`로 봉합·해당 파일 50 passed 재실행, 최종 1568 passed/3315s**, ZIP QA 빌드 Task 5 pre/post **ok(entry 21442·installer 2, 신규 wheel 포함)** 이다.

### G001 — 업무대화·문서작성 AI 응답 SSE 스트리밍
- 범위: 업무대화 지식 답변·문서작성 AI 내용 생성을 SSE(delta→done) 스트리밍으로 전환. 중단 시 `error` 프레임, 프롬프트 인젝션 방어, 스트림 실패 시 안전 문구 폴백.
- 게이트: 기능 브랜치 병합(`dcfa19e`, 111 passed) → 리뷰 블로커(MEDIUM 2·LOW 4·QA finding) 해소(`f0793ee`, **122 passed**, 적대(redteam) 스위트 10건 포함) → G001 체크포인트.
- 커밋(최종): `f0793ee`
- 테스트: 병합 시점 `pytest aero_work 122 passed`(적대 10 + 글루 1 포함) · `tsc --noEmit 0`.
- 후속 미검증: 실 LLM/실 OpenAI 호환 스트리밍 체감(라이브 실사는 G002에서 확인).

### G002 — 지식 검색·위키 실사 결함 수정
- 범위: G001 라이브 실사에서 발견한 표기 결함 2건 — 키워드 검색 결과 "일치 N회" 라벨 누락, 위키 문서 카드 `<mark>` 즉시 강조 미동작.
- 게이트: 결함 수정(`81047a7`, tsc 0 + 라이브 브라우저 3회 재검증) → 리뷰 LOW 지적(캡션 분기·`searchModel` 초기화·vitest 회귀 4건) 해소(`0073772`, **vitest 4 passed**) → G002 체크포인트.
- 커밋(최종): `0073772`
- 테스트: `npx vitest run tests/components/aero-work-knowledge.test.tsx` 4 passed · `tsc --noEmit 0` · 라이브 브라우저 실측("일치 1회" 라벨·마크 강조 확인).

### G003 — 분류체계 마법사 + 지식위키 업무 허브
- 범위: LLM 업무 분류 3단계 마법사(니즈 입력 → 분류 검토 → 적용) → 지식위키 업무 허브(대표 공식본 + 카테고리) 반영. 마이그레이션 `20260719_0029`.
- 게이트: 기능 브랜치 병합(`bc8a33d`, 신규 서비스 단위 9·통합 6 포함 100 passed·vitest 8) → 리뷰 지적(MEDIUM 2·LOW 5, 실패 사유 노출·수동 후보·위키 기능 보존) 해소(`5bf4637`, taxonomy 33 passed·vitest 11, `20260719_0030` 마이그레이션 2건 포함) → 재리뷰 P3(마법사 실패 사유·수동 후보 UI 경로 vitest 고정, `1c997b2`, vitest 9 passed) → G003 체크포인트.
- 커밋(최종): `1c997b2`
- 테스트: `pytest taxonomy 33 passed`(마이그레이션 0030 2건 포함) · `npx vitest run tests/components/aero-work-taxonomy.test.tsx` 9 passed · `tsc --noEmit 0`.
- 후속 미검증: 실 LLM 분류 품질 재실사(1차 라이브 실사에서 정상 확인됨).

### G004 — FTS5 키워드 검색 + 백그라운드 재색인
- 범위: 키워드 검색을 SQLite `LIKE` → **FTS5**로 승격(한국어 부분일치), 재색인을 동기 → **백그라운드**로 전환(202 Accepted + 진행률 폴링 + 409 충돌 응답). 마이그레이션 `20260719_0031`(기존 데이터 백필 포함).
- 게이트: 기능 브랜치 병합(`256c041`, FTS 단위 7·비동기 통합 9 포함 166 passed·vitest 15) → 리뷰 블로커(HIGH 2·MEDIUM 3·LOW 6, 기존 DB 백필·색인 고착 방지·가드 정합) 해소(`ff68803`, 176 passed·vitest 6, 백필·409·스윕 포함) → 재리뷰 후속(폴백 경고 로그·기동 스윕 테스트, `555ea35`, 21 passed) → G004 체크포인트.
- 커밋(최종): `555ea35`
- 테스트: `pytest aero_work 176 passed`(백필 3·409 충돌 1·기동 스윕 1 포함) + 후속 21 passed · `npx vitest` 6 passed · `tsc --noEmit 0` · `20260719_0031` up/down 왕복 검증.
- 후속 미검증: 대용량(수천 파일) 재색인 실측 성능, 멀티워커 배포(현재 단일 uvicorn 전제 명시).

### G005 — 양식 종이 미리보기 + 수정 지시 재생성
- 범위: 5개 문서 양식(시행문/1페이지/풀버전/이메일/임의형식)의 **서버 HTML 근사 렌더**("종이" 미리보기) + 이전 초안을 반영한 **수정 지시 재생성** 루프(스트리밍 경로 포함).
- 게이트: 기능 브랜치 병합(`9c72220`, 미리보기 단위 8·통합 6·재생성 4 포함 194 passed·vitest 18) → 리뷰 지적(MEDIUM 3·LOW 4, 경합 가드·위계 일치·절단 정합) 해소(`0e0aac4`, 230 passed·vitest 7) → 재리뷰 잔여(스트림 경로 절단 신호·단언 보강, `21ae8a0`, stream+preview_redteam 43 passed·vitest 7) → G005 체크포인트.
- 커밋(최종): `21ae8a0`
- 테스트: `pytest stream+preview_redteam 43 passed`(XSS 벡터 다중 케이스·경계값·프롬프트 인젝션 무해화 포함) · `npx vitest` 7 passed · `tsc --noEmit 0`.
- 후속 미검증: 실 LLM 재생성 품질 라이브 실사(별도 확인 완료 상태로 넘어감), **한컴 실기 HWPX 서식 호환**(운영자 게이트, §3).

### G006 — 업무대화 첨부 + LLM 보조 인텐트 분류
- 범위: 업무대화에 파일 첨부(AeroAI 첨부 계약 재사용, PDF/DOCX/HWPX 텍스트 추출)와 규칙 미매칭 시 **LLM 보조 2차 분류**(지식 폴백 한정) 추가.
- 게이트: 기능 브랜치 병합(`0e4aae4`, LLM 폴백 단위 18·첨부 통합 14 포함 262 passed·vitest 14, 발화표 무수정 확인) → BLOCK 해소(CRITICAL 1·HIGH 5·MEDIUM 3·LOW 2, 실배선 정합·안전 강등·Windows 추출, `114bd6c`, 285 passed·vitest 5, 실 Windows B6 케이스 포함) → 재리뷰 후속(M1 가드 회귀 테스트·데드 브랜치 정리, `f085ac0`, 20 passed·vitest 5) → G006 체크포인트 → G007 진행 지시.
- 커밋(최종): `f085ac0`
- 테스트: `pytest aero_work 285 passed`(G006 시점) · `npx vitest` 첨부 컴포넌트 5 passed · `tsc --noEmit 0`.
- 후속 미검증: 실 LLM 보조 분류 품질(라이브 확인 예정).

### G007 — Playwright E2E + 릴리스 후보 게이트
- 범위: `/aero-work` 7탭, 업무대화 멀티인텐트(schedule.create+document), 일정 등록 확인, 문서 HWPX 다운로드, 지식폴더 키워드 검색, 최종 저장 요청 → 승인 → HWPX 다운로드를 실제 브라우저로 검증했다. 오프라인 ZIP QA 빌드와 2.0.0-dev 버전 후보 정합도 같은 G007 마감 범위에 포함한다.
- 상태: **완료**. 커밋: `960465d`(C 게이트 산출물 병합) · `c4111c5`(패키징 명령 길이 수정 병합) · `5fe395a`(버전 고정 테스트 정합 병합) · `7d94464`(Leantime 격리 테스트 봉합 병합) · 이번 리뷰 해소 커밋:
- 테스트: Playwright E2E **1 passed(8.8s)** · frontend vitest **652/652 passed** · backend 전량 **1568 passed/3315s**(선행 1 failed 격리 결함은 `7d94464`로 봉합하고 해당 파일 50 passed 재실행) · ZIP QA 빌드 Task 5 pre/post **ok(entry 21442·installer 2, 신규 wheel 포함)**.

---

## 2. 릴리스 선결 게이트 체크리스트

`aero-work-phase-f1-f8.md` §4의 릴리스 선결 게이트를 G001~G007 진행 결과로 갱신한다.

| # | 게이트 | 상태 | 비고 |
|---|---|---|---|
| 1 | 전체 백엔드 `pytest tests`(회귀 포함) + 프런트 `vitest` 전량 green | 완료 — backend 전량 1 failed(격리 결함) 후 `7d94464`로 봉합, 해당 파일 50 passed 재실행, 최종 **1568 passed/3315s**. frontend vitest **652/652 passed** | 리더 검증 완료 |
| 2 | 오프라인 ZIP 재빌드(신규 wheel 반입 후 Task 5 검증) | 완료 — QA 빌드 Task 5 pre/post **ok(entry 21442·installer 2, 신규 wheel 포함)** | 릴리스 asset 게시 전 최종 release mode 재빌드는 `main` 태그 단계에서 수행 |
| 3 | **한컴(HWPX) 실기 검증** | 대기 — **유일한 외부 의존**. 본 개발 환경엔 한컴이 없어 서식 확정 전 필수. G005 종이 미리보기는 서버 HTML 근사이며 한컴 실물 렌더와 별개 | **운영자 한컴 설치 PC 필요** |
| 4 | 브라우저 E2E(`/aero-work` 7탭 + 오케스트레이션 실채팅) | 완료 — Playwright E2E **1 passed(8.8s)** | G007 |
| 5 | `main` 병합·태그·Release(ZIP 동시 첨부) | 대기 | **운영자 승인 후**(본 워크트리는 `aero-work-dev`이며 커밋 권한이 리더로 한정됨) |

---

## 3. 2.0.0 major 근거

`aero-work-phase-f1-f8.md` §4 "릴리스 권고"의 major 판정(신모듈 다수 + 신규 마이그레이션 + 신규 의존)에 더해, G001~G007이 다음을 추가한다.

- **신규 마이그레이션 3건**: `20260719_0029`(분류체계), `20260719_0030`(카테고리-파일 색인), `20260719_0031`(지식 FTS5 + 기존 데이터 백필) — F1~F8의 `20260719_0020~0023`에 이어 스키마가 계속 확장됨.
- **API 계약 확장**: SSE 스트리밍 엔드포인트(G001), 키워드 검색 FTS5 전환 + 비동기 재색인 202/409 계약(G004), 미리보기/재생성 스트림 엔드포인트(G005), 첨부 필드가 추가된 오케스트레이션 요청 스키마(G006) — 기존 클라이언트가 알지 못하는 새 응답 형태(SSE 프레임, 202 폴링)가 도입되어 부가기능이 아닌 **인터페이스 확장**이다.
- **사용자 관점 신기능 5종**(SSE 스트리밍·분류체계 마법사·FTS5 키워드 검색·종이 미리보기+수정 재생성·첨부+LLM 라우팅)이 모두 gongmuwon 파리티 체크리스트(`aero-work-full-parity-plan.md` §2)의 항목을 채우며, 각각 독립 리뷰·레드팀 게이트를 통과한 규모 있는 변경이다.
- AGENTS.md §9 기준: minor/major는 phase 보고서 필수 — 본 문서가 G001~G007의 phase 보고서 역할을 하며, `2.0.0` 트랙 결론을 유지한다(F1~F8 보고서의 권고를 재확인, 상향 조정 없음).
- 버전 후보 표기는 프런트 `APP_VERSION`과 백엔드 `settings.app_version`을 `2.0.0-dev`로 맞춘다. README 배지와 "릴리스 X.Y.Z 기준" 문구는 AGENTS.md §9.1에 따라 정식 릴리즈 직전 마지막 커밋에서만 `2.0.0`으로 바꾼다.

---

## 4. 결론

G001~G007은 F1~F8이 남긴 "후속" 목록(LLM 보조 라우팅·FTS5·종이 미리보기·분류체계 마법사·첨부)을 기능 구현·아키텍트 재리뷰·레드팀 스위트 3단 게이트와 Playwright E2E로 마감했다. 전량 실측은 Playwright E2E 1 passed(8.8s), frontend vitest 652/652 passed, backend 최종 1568 passed/3315s(선행 격리 결함은 `7d94464`로 봉합·해당 파일 50 passed 재실행), ZIP QA Task 5 pre/post ok(entry 21442·installer 2, 신규 wheel 포함)이다. 남은 pending은 운영자 전용 게이트인 **한컴 실기 HWPX 검증**과 **`main` 병합·태그·Release(ZIP 동시 첨부)**뿐이다. 버전 스코프는 F1~F8 권고를 유지해 **major `2.0.0`**이다.
