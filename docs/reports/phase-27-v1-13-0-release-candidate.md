# 단계 27 — v1.13.0 릴리스 후보 통합

## 변경 배경

철회된 1.12.2 배포본을 대체하려면 자격 증명 사고 대응만 추가하는 것으로는 충분하지 않았다. 계정·권한·Activity·관리자 운영 화면을 실제 서버 계약에 연결하고, workspace 전체를 복사하던 공개 패키징 경계를 tracked source allow-list와 반복 가능한 브라우저 검증으로 교체해야 했다. 이 단계는 공개 1.12.3을 생략하고 검증된 hotfix 계보를 보존한 채 v1.13.0으로 직접 릴리스하는 합의안의 마지막 개발 단계다.

## 핵심 수정 사항

| 영역 | 결과 |
|---|---|
| 계보 | incident/hotfix 커밋을 no-ff 통합하고 개별 한국어 커밋과 Lore trailer를 보존했다. |
| 인증·권한 | credentials-only session BFF, 파생 visibility flag, 안전한 `next` 경로, 상태 보존 `ApiError`를 적용했다. Document는 공개를 유지하고 NSA·AeroAI는 서버 권한 실패 시 비노출한다. |
| 본인 Activity | 최근 세션·로그인·AeroAI 사용 기록을 고정 스키마와 최신 20건으로 제공한다. 토큰 hash는 단일 helper를 사용하고 IP·UA·prompt·본문·내부 식별자는 직렬화하지 않는다. |
| 관리자 Overview | 사용자·로그인·AI·세션·모듈의 실제 24시간 집계와 이전 기간 delta를 제공한다. DB URL과 민감 audit metadata는 제외한다. |
| Users·Sessions·Modules | 10건 페이지네이션, 검색·정렬 초기화, 15초 접속자 전용 갱신, purge 확인, 모듈 접근 tuple의 서버측 원자 검증과 preset/preview를 구현했다. |
| 접근성·브라우저 | 설치된 production Chrome으로 smoke, 375/768/1280과 200% zoom, Axe, Lighthouse 3회 중앙값, React 진단을 같은 SHA에서 실행하는 harness를 추가했다. |
| 공개 패키지 | `offline_package.bat`을 `scripts/build_offline_package.ps1` wrapper로 축소했다. builder는 `git archive` allow-list, clean `npm ci`/build/prune, production wheelhouse, 정확한 인스톨러, pre-stage/post-ZIP verifier를 강제한다. |
| 운영 안전 | QA runtime은 loopback·임시 DB/storage/import root와 소유 PID만 사용하고 운영 `.env`, canonical DB, secure root, 고정 production port를 변경하지 않는다. |

## 검증 결과

릴리스 후보 검증은 커밋별 `artifacts/qa/v1.13.0/<SHA>/` 아래에 redacted receipt와 로그를 남긴다.

| 게이트 | 명령 | 관측 결과 |
|---|---|---|
| Backend 전체 | `node scripts/qa/run_v113_backend_gates.mjs --sha <SHA> --suite all` | backend 567 passed, package·migration-heads·migration exit 0 |
| Frontend 전체 | `npm test && npm run typecheck && npm run build` | Vitest 397 passed / 73 files, TypeScript 0 error, Next 15.2.9 production build 성공 |
| Browser RC | `npm run qa:browser:all -- --sha <SHA>` | smoke 1, matrix 4, Axe 1 통과; Lighthouse·React 진단·teardown exit 0 |
| QA 오프라인 ZIP | `powershell -File scripts/build_offline_package.ps1 -Version 1.13.0` | `publishable=False`; clean build와 인스톨러 검증 후 pre-stage/post-ZIP 모두 `ok: true`, ZIP/SHA 생성 |
| Wrapper 계약 | focused pytest + `offline_package.bat --help` | 25 passed, builder 위임·production requirements·금지 재사용 계약 통과 |
| 노출 검사 | QA artifact pattern scan | 로컬 사용자 경로, 합성 비밀번호, 실제 secret assignment, U+FFFD 0 |

정식 배포 ZIP은 PR 병합 뒤 main의 exact annotated `1.13.0` tag에서만 `publishable=true`로 생성한다. 태그 전 QA ZIP은 운영 반입물이 아니다.

## 영향 범위와 제약

- `APP_ENV` 4개 값, `closed_network`/`production` secret 강도 검증, LAN 기본 바인딩, `--local` opt-out, `ensure_db_state.py` 종료 코드 0/1/2/3, 방화벽 `LocalSubnet` 범위는 유지한다.
- 공개 패키지는 `.gjc`, `.omo`, `.env`, DB/storage, vendor, artifacts, source `node_modules`/`.next`, `requirements-dev.txt`를 포함하지 않는다.
- 실제 운영 자격 증명 회전은 별도 사고 대응 작업이다. 노출 범위가 현재 live deployment와 겹친다는 판정이 나오면 별도 승인된 rotation receipt 전에는 릴리스를 차단한다.
- Windows Sandbox는 부가 검증이며, 필수 패키지 게이트는 빈 격리 폴더에서 네트워크 없이 setup/start/health/login/empty-NSA/cleanup을 확인하는 것이다.

## PR·릴리스 경계

1. 최종 dev SHA에서 backend/frontend/browser/package/격리 설치 증거를 다시 생성한다.
2. 한국어 PR에 변경 배경, 핵심 수정, 명령·출력, 영향 범위, 후속 작업을 기록한다.
3. PR 승인 전에는 main에 병합하지 않는다.
4. 승인 후 `--no-ff` 병합, annotated `1.13.0` tag, exact-tag ZIP/SHA 생성, push, GitHub Release asset 업로드와 재다운로드 digest 검증을 수행한다.
5. 태그는 이동하지 않으며 실패는 forward fix로 처리한다.
