# Task 3 독립 review-work — Round 1

- 대상: `ca9ce3e3adc0d39a43dc854e88eb0cd4629d293c`
- 기준: `2f592c46aacab83c3cfa12610a87651082deba5e`
- 판정: `REVIEW FAILED`
- Task 4: 실행 금지

| Lane | Verdict | Confidence / severity |
| --- | --- | --- |
| Goal & constraints | FAIL | HIGH |
| Hands-on QA | FAIL | HIGH |
| Code quality | FAIL | HIGH |
| Security | FAIL | HIGH (CRITICAL 0 / HIGH 9 / MEDIUM 5) |
| Context mining | FAIL | HIGH |

## 재현된 P0

`after_db_commit` 상태에서 ACL이 정상인 `pending/root-env.dpapi`를 1 byte 변조한 뒤 resume하면 exit 1로 실패하면서 active root `.env`를 먼저 quarantine으로 이동해 제거한다. intact control은 complete로 끝난다. 서로 다른 synthetic workspace에서 2회 재현했으며 secret/hash 출력은 0이었다.

## 차단 수정 범위

1. production root에서는 TestMode와 test Python/failpoint를 절대 허용하지 않고 test marker 하나만으로 우회되지 않게 한다.
2. 실행 스크립트의 physical ProductRoot와 대상 WorkspaceRoot를 production에서 동일 provenance로 결합한다.
3. workspace/env/DB/secure artifacts의 reparse/junction/symlink/hardlink와 physical path escape를 fail closed로 검증한다.
4. env key를 휴리스틱 deny가 아니라 exact allow-list로 검증하고 예상 밖 credential/provider key가 하나라도 있으면 차단한다.
5. SQLite recovery를 WAL/journal-safe backup과 전체 실행 lock/`BEGIN IMMEDIATE` 경계로 바꾸고 concurrent runner를 차단한다.
6. plaintext env temp를 제한 ACL·no-share·CreateNew·난수 경로로 먼저 생성하고 쓰기/flush 뒤 원자 승격한다.
7. journal은 atomic temp+flush+replace, sequence/checksum/rotation identity/bundle·DB·env binding을 사용한다.
8. resume은 journal을 읽기 전에 active env를 강제하지 않고 pending/final/quarantine/live artifact를 모두 사전 복호화·스키마·ACL·digest 검증한 뒤 실제 상태를 reconciliation한다.
9. live env 격리는 D:→C: 교차 볼륨 copy/verify/flush/atomic-finalize 뒤에만 원본을 제거하며 partial copy를 정상으로 수용하지 않는다.
10. final credential collision과 모든 output/ACL 조건을 DB commit 전에 preflight한다.
11. 전용 unique rotation ledger와 workspace-scoped mutex로 exactly-once를 DB/파일 양쪽에서 보장한다.
12. configured admin이 active admin인지 prepare/commit 양쪽에서 확인한다.
13. Pydantic boundary를 strict/frozen/extra-forbid로 만들고 ctypes/command typing 경고를 제거한다.
14. 실제 crash seam, torn journal, corrupt pending, final collision, cross-volume partial copy, concurrent execution을 별도 프로세스 테스트로 추가한다.
15. README, `docs/INDEX.md`, `docs/CLOSED_NETWORK_GUIDE.md`, Windows/admin runbook의 setup-only password rotation과 backup restore 계약을 실제 도구/재회전 절차에 맞게 갱신한다.

## 검토에서 확인된 양호 항목

- Python 사용자 변경은 한 SQLAlchemy transaction에서 수행되고 role/is_active/count를 보존한다.
- CSPRNG, current-user DPAPI, 비밀 없는 argv/stdout/status/count 계약은 정상 경로에서 확인됐다.
- focused 17 tests와 backend 285 tests는 구현자 환경에서 통과했다.
- 한국어 commit 제목/본문과 Lore trailer 7개, no push/tag/release/PR 제약을 충족했다.

Round 1은 승인 증거가 아니다. 위 차단점을 수정한 새 commit에서 review-work 5개 lane을 모두 새로 실행해야 한다.
