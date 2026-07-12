# Task 3 독립 review-work — Round 2

- 대상: `2259fdc35dc1c9e9a125500b90c951285af312d5`
- 기준: `2f592c46aacab83c3cfa12610a87651082deba5e`
- 판정: `REVIEW FAILED`
- Task 4: 계속 실행 금지

| Lane | Verdict | Confidence / severity |
| --- | --- | --- |
| Goal & constraints | FAIL | HIGH |
| Hands-on QA | PASS | HIGH |
| Code quality | INCONCLUSIVE | reviewer model capacity |
| Security | FAIL | HIGH (5 release blockers) |
| Context mining | FAIL | HIGH |

## Round 2에서 확인된 개선

- QA actual-process 56건과 corrupt-pending 독립 2차 실행은 PASS했다.
- current-user DPAPI purpose binding, unique rotation ledger, `BEGIN IMMEDIATE`, WAL-aware recovery, active admin, strict command models, path/provenance, secure temp, atomic current/previous journal, initial/env-move/credential/cross-volume crash, restore archive/new rotation, exact ACL 테스트가 구현됐다.
- backend 324, frontend 313/66, typecheck/build, Ruff/basedpyright/PowerShell AST, 링크·literal 검사가 구현자 revision에서 통과했다.

## 남은 차단 수정 범위

1. active root/backend env를 읽기·ACL·DB commit 전에 handle-based containment/reparse/single-link로 검증한다.
2. root/backend env publish 직후 journal 전 실제 crash를 추가하고, active env digest가 NEW이면 quarantine을 반복하지 않고 journal을 전진시킨다.
3. workspace의 `.aeroone-rotation-*.tmp` plaintext orphan을 exact path/link/ACL/ownership 검증 후 resume에서 안전 정리한다.
4. `Local\` mutex를 machine-global namespace와 exact ACL로 바꾸고 cross-session contention을 테스트 가능한 경계로 검증한다.
5. recovery backup과 credential DB commit을 하나의 Python process/연속 `BEGIN IMMEDIATE` writer-lock window로 결합해 중간 application writer를 차단한다. 실행기는 known AeroOne service/listener 중지 상태도 fail closed로 확인한다.
6. root와 backend env를 서로 다른 exact profile로 검증하고 공식 `.env.example` key를 모두 포함하며 필수 security-mode key 누락을 차단한다.
7. production `-DryRun`은 secure parent/root를 포함해 어떤 파일도 만들지 않게 validation-only 경로로 앞당긴다.
8. public `-Failpoint` accepted values는 원래 4개만 유지하고 internal crash hooks는 nonce TestMode 전용 비공개 env/seam으로 이동한다.
9. 일반 일일/admin backup restore에도 service stopped → 명시 new rotation archive → 새 admin login까지 강제하는 실행 가능한 절차와 테스트를 추가한다.
10. 사용자별 새 credential을 stdout/transcript 없이 current-SID GUI로 조회·복사·자동 clipboard clear할 수 있는 운영 지원 도구와 runbook을 제공한다.
11. README/CLOSED_NETWORK_GUIDE의 철회된 1.12.2 asset 반입 안내와 setup "매번 생성" 문구를 현재 GitHub 상태/seed 계약으로 교정한다.
12. strict env allow-list에 공식 import-host keys를 반영하고 실제 root/backend fixture를 사용한다.
13. DPAPI plaintext buffer zeroization, quarantine manifest strict binding, bootstrap file exact ACL 검증의 MEDIUM 항목도 가능한 범위에서 닫는다.

Round 2는 승인 증거가 아니다. 새 commit에서 5개 lane을 다시 실행하며 code-quality lane은 새 reviewer로 교체한다.
