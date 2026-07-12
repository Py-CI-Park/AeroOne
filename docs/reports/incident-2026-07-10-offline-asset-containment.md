# 사고 대응 보고서 — 폐쇄망 배포 자산 노출과 봉쇄 (2026-07-10)

> 본 문서는 공개 배포용으로 **redacted** 되었다. exact release/asset 식별자, digest, URL, 커밋 해시, 비밀값은 포함하지 않는다. 원본 감사·실행·검증 증적은 접근 통제된 내부 저장소(`.omo/evidence/v1-13-0/`)에 보존된다.

## 1. 요약

공개 GitHub Release로 배포되던 AeroOne offline package ZIP들이 코드·런타임 외에 운영 비밀과 데이터를 포함하고 있었다. 확인된 unsafe 자산을 운영자 승인 하에 봉쇄하고, 재발을 구조적으로 막는 도구를 구축했다. 이 문서는 그 사고 대응 기록이다.

## 2. 영향 자산 유형

공개 ZIP에서 다음 유형이 확인됐다(카테고리 단위, 원문 미개봉 감사 기준):

- 환경 파일(`.env` 계열)
- canonical 애플리케이션 DB와 backend data
- storage 트리
- agent/VCS 작업 상태와 dev artifact(캐시·빌드 산출물)

## 3. 원인

- 기존 `offline_package.bat`의 robocopy **deny-list** 방식은 저장소에 새로 생긴 로컬 상태를 자동으로 포함할 수 있었다.
- 최종 ZIP에 대한 정책 verifier가 없어, 산출물이 정책을 위반해도 걸러지지 않았다.

## 4. 탐지와 봉쇄

- 전체 공개 release를 **중앙-directory-only sparse 감사**로 점검했다. entry stream/content와 비밀값은 열지 않고, filename을 메모리에서 카테고리 count로만 집계했다.
- 확인된 unsafe ZIP과 짝 SHA 자산을 **운영자의 명시적 삭제 승인** 하에 exact ID 단위로만 제거했다. release·tag·release 본문·대상 외 자산은 보존했다.
- 보존이 필요한 release 본문 최상단에 **사용·재배포 금지와 정식 버전 교체 경고**를 추가했다.
- 삭제 후 이전 다운로드 URL이 미인증 상태에서 **404** 임을 확인했다.
- 감사·삭제·검증의 exact 식별자와 digest는 본 공개 문서에서 redact 했다(재캐시 탐색에 악용될 수 있으므로).

## 5. 재발 방지 (구축한 도구)

- **자격증명 회전 도구**: 전 계정 비밀번호·JWT·세션을 단일 `BEGIN IMMEDIATE` 트랜잭션으로 회전하고, DPAPI 기반 recovery/journal/quarantine로 중단에도 안전하게 재개한다.
- **공개 패키지 fail-closed allow-list + pre/post ZIP verifier**: 명시 허용 경로만 담고, 운영 비밀·데이터·dev artifact를 발견하면 산출물을 거부한다.
- **내부 데이터 bundle 승인·서명·암호 경계**: 실제 데이터는 공개 경로와 분리해, 역할별 이중 서명·조직 trust 검증·recipient 암호화를 통과한 내부 번들로만 전달한다.
- **git-archive allow-list 공개 package builder 인프라**: 추적 소스의 명시 정책 경로만 산출하고 verifier 통과 후에만 ZIP을 만든다(운영자 배포 경로 전환은 실 build + Sandbox smoke 검증 후 적용).

## 6. 운영자 후속 조치

1. **자격 증명 회전(권장, 운영자 실행)**: 노출 의심 시 서비스를 중지하고 [`../runbook/credential-rotation.md`](../runbook/credential-rotation.md) 절차로 `scripts\rotate_aeroone_credentials.ps1`을 실행한다. 이는 되돌릴 수 없는 production 변경이므로 운영자 승인·실행이 필요하다.
2. **정식 버전 교체**: 철회된 공개 ZIP은 신규 설치·재배포에 사용하지 않고 정식 버전으로 교체한다.
3. **향후 배포**: 검증된 allow-list builder와 verifier를 통과한 산출물만 배포한다.

## 7. 증적 보존

감사·실행·독립 검증 원문(exact 식별자·digest 포함)은 접근 통제된 내부 `.omo/evidence/v1-13-0/`에 보존한다. 본 공개 문서는 정책 수준 기록으로, exact 식별자와 비밀값을 담지 않는다.
