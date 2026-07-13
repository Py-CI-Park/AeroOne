# Task 3 독립 review-work — Round 1 차단점 교정 증적

## 판정 범위

- 기준 실패: `task-3-review-round-1.md`의 P0와 차단 수정 범위 15개
- 대상: 최초 구현 `ca9ce3e` 이후 후속 교정 변경분
- 실제 운영 자격 증명 회전: 수행하지 않음
- 비밀값·암호 해시·환경 원문·DPAPI payload 출력: 0건

## blocker별 RED→GREEN

| # | Round 1 blocker | RED / 구분 근거 | GREEN 구현·검증 |
|---:|---|---|---|
| 1 | production에서 TestMode/test Python/failpoint 차단 | marker만 둔 root가 TestMode를 열고 undocumented option이 surface에 남는 경계를 재현 | OS temp 아래 nonce+marker를 함께 요구하고 production에서 failpoint를 거부. `test_marker_alone_does_not_authorize_test_mode`, `test_unknown_failpoint_provider_and_root_options_are_rejected` 통과 |
| 2 | ProductRoot와 WorkspaceRoot physical provenance 결합 | 복사된 스크립트가 production workspace를 대상으로 삼는 경로를 분리 재현 | script file identity와 production physical root를 handle 기준으로 결합. `test_copied_script_cannot_target_the_production_workspace` 통과 |
| 3 | reparse/junction/hardlink/physical escape 차단 | canonical DB hardlink, marker hardlink, DB parent junction을 각각 허용하는 RED 확인 | component reparse, final path, volume/file ID, link count, containment을 mutation 전에 검증. path-security 4건 통과 |
| 4 | env exact allow-list | 예상 밖 credential/provider key와 일반 undocumented key가 준비 단계를 통과하는 RED 확인 | 두 env profile을 exact key set으로 고정하고 추가/누락/불일치를 fail closed. unknown credential·undocumented env 테스트 통과 |
| 5 | WAL-safe recovery, 전체 lock, `BEGIN IMMEDIATE` | raw file recovery가 live WAL frame을 보존하지 못하고 동시 runner가 겹칠 수 있는 경계 재현 | SQLite online backup, DB identity, `BEGIN IMMEDIATE`, physical workspace mutex 적용. WAL writer recovery와 external concurrent process 테스트 통과 |
| 6 | secure temp 생성·flush·원자 승격 | 예측 가능한 temp hardlink가 victim을 덮을 수 있는 RED 확인 | random temp, `CreateNew`, no-share, ACL-at-creation, WriteThrough, `Flush(true)`, readback 후 atomic publish. `test_precreated_plaintext_temp_hardlink_is_never_opened_or_modified` 통과 |
| 7 | atomic strict journal과 artifact binding | extra field/checksum 변조, phase jump, torn current가 구분되지 않는 RED 확인 | frozen/extra-forbid schema, sequence, checksum, rotation/DB/env/bundle binding, current/previous 세대 적용. journal unit 2건과 torn-current recovery 통과 |
| 8 | resume 전 전체 artifact 검증·reconciliation | corrupt pending resume가 active `.env`를 먼저 quarantine으로 이동하는 P0를 2회 재현 | live env 접근 전에 pending/final/quarantine/recovery/journal ACL·single-link·digest·복호화·schema를 검증하고 실제 상태를 reconcile. corrupt pending, missing live root, credential move crash 통과 |
| 9 | cross-volume quarantine copy/verify/finalize | partial copy와 finalize 직후 process death에서 source 제거 순서가 깨지는 seam 재현 | `CreateNew` temp→flush/readback→atomic final→size/SHA-256 verify→source delete 순서 적용. quarantine partial/final crash 테스트 통과 |
| 10 | final collision과 output/ACL preflight | 기존 final credential과 예상 밖 secure output이 DB mutation 뒤 발견될 수 있는 RED 확인 | output inventory, exact ACL, final collision을 DB commit 전에 검사. `test_existing_final_credential_blocks_before_database_or_environment_mutation`, unexpected output 테스트 통과 |
| 11 | DB/file exactly-once ledger+mutex | audit row만으로 rotation/material 재사용을 구분하지 못하는 RED 확인 | database identity singleton과 unique `(database_id, material_fingerprint)` ledger, rotation ID binding, workspace mutex 적용. ledger 2건·migration 3건·concurrency 1건 통과 |
| 12 | configured admin active/role 재검증 | inactive/non-admin/demoted configured admin이 prepare 또는 commit을 통과하는 RED 확인 | prepare와 commit 모두 exact configured active admin 및 최소 활성 admin을 검증. unit 2그룹 통과; inactive 로그인은 상태 비공개 정책대로 401 유지 |
| 13 | strict Pydantic와 command/ctypes typing | extra field와 문자열 failpoint coercion이 boundary를 통과하는 RED 확인 | strict/frozen/extra-forbid command·journal 모델과 작은 handler로 분리. command boundary 2건, Ruff PASS, basedpyright 0 errors/0 warnings |
| 14 | 실제 crash/corruption/concurrency process tests | in-process exception만으로 torn file과 process death seam이 미검증 | secure-root 초기화, quarantine copy/finalize, env/credential move, torn journal, corrupt pending, final collision, mutex를 실제 별도 process kill로 검증. focused 56건 통과 |
| 15 | setup-only 문서와 DB restore 재회전 계약 | README/운영 문서가 setup 재실행을 사고 대응 전체 회전으로 안내하고 completed bundle 재사용 위험을 남김 | setup과 incident rotation을 분리하고 exact confirmation `ARCHIVE_COMPLETED_ROTATION_AND_START_NEW` 후 old root archive→별도 신규 rotation 계약 구현. old login 401/new login 200; README·종합 가이드·Windows/install/admin runbook·INDEX·phase 26 동기화 |

## 최종 자동 검증

| Gate | 결과 |
|---|---|
| Task3 focused | 56 passed, 3 warnings, 21:01 |
| backend 전체 | 324 passed, 3 warnings, 20:21 |
| frontend 전체 | 313 passed / 66 files |
| frontend typecheck | exit 0 |
| frontend production build | PASS, static pages 7/7 |
| Ruff changed production+tests | PASS |
| basedpyright production+0009 migration test | 0 errors, 0 warnings, 0 notes |
| Python compileall | PASS |
| PowerShell | ps1/psm1 13개 AST PASS, 최대 함수 43줄, main 432줄, handler 233줄 |
| 문서 | 상대 링크 11개 PASS, trailing whitespace 0 |
| credential literal | 공개 고정값 exact count 0, JWT-like literal count 0 |

backend 첫 전체 실행은 worktree가 계산한 `.worktrees\AeroOne-bundle` 부재로 Open Notebook dry-run 테스트 2건이 standalone fallback을 확인하며 실패했습니다. 실제 sibling bundle을 가리키는 임시 junction에서 두 테스트가 2 passed로 바뀌었고, 같은 환경의 전체 재실행이 324 passed였습니다. junction은 제거했고 실제 bundle target은 보존했습니다.

## 실제 운영 비접촉 증적

- hotfix worktree에는 `.env`, `backend\.env`, `backend\data\aeroone.db`가 존재하지 않았습니다.
- 실제 저장소의 세 파일 수정시각은 모두 작업 시작 `2026-07-10T22:10:07+09:00` 이전이었습니다.
- 실제 저장소 `.env`: 2026-03-28, `backend\.env`: 2026-06-04, DB: 2026-07-08 수정 상태 유지.
- production 기본 명령은 실행하지 않았고 모든 회전 실행은 pytest synthetic OS temp workspace의 강한 TestMode nonce를 사용했습니다.
- frontend/bundle junction 제거 후 target 보존, hotfix 관련 Node process 0, QA port 29502 listener 0을 확인했습니다.

## 남은 visual gate

[`task-3-visual-qa/README.md`](task-3-visual-qa/README.md)에 375px 실제 렌더의 overflow/CJK 부분 증거를 남겼습니다. 1280px, 변경 행 가시 캡처, console 오류 0, fresh dual-oracle은 충족하지 못했으므로 visual QA를 PASS로 기록하지 않습니다. 기존 Next 15 sync-dynamic API와 backend 미기동 fetch fallback은 후속 UI/QA owner가 production build+backend 환경에서 재검증해야 합니다.
