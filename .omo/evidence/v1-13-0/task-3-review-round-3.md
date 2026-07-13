# Task 3 독립 review-work — Round 3

- 검토 commit: `d6628dd4679fe004ad68a62bf07789365d51a2dc`
- 기준 commit: `2f592c4`
- 검토 시간: `2026-07-11T08:50:15+09:00` ~ `2026-07-11T09:35:10+09:00`
- 판정: `REVIEW FAILED`
- Task 4 실제 운영 회전: 계속 금지

| Lane | 판정 | 핵심 근거 |
|---|---|---|
| Goal & constraints | FAIL | production viewer provenance가 canonical rotate script와 viewer를 동일 파일로 비교해 항상 실패 |
| Hands-on QA | FAIL | 23 scenario 중 13 PASS/10 FAIL; 일반 사용자 execute가 `SeSecurityPrivilege` 요구로 `stage_recovery` 중단 |
| Code quality | FAIL | immutable recovery overwrite, recovery/journal publication crash window, production root hard-code |
| Security | FAIL | service restart TOCTOU, recovery overwrite, restore/archive freshness race, clipboard history/clear failure |
| Context mining | FAIL | 공식 설치 경로·env topology와 production tool 계약 불일치, setup 문서 drift |

## 차단점

1. recovery/final ACL 적용이 ordinary current-SID 프로세스에서 `PrivilegeNotHeldException`을 발생시킨다. owner+DACL만 설정하고 SACL privilege를 요구하지 않아야 한다.
2. viewer production provenance가 viewer 자신을 canonical rotate script와 비교해 항상 `provenance-script-mismatch`다.
3. production root가 개발 PC 절대 경로에 고정되어 `D:\AeroOne` / `C:\Programs\AeroOne` 설치와 맞지 않는다.
4. 정상 installer topology는 `backend/.env`만 생성하지만 회전기는 root/backend 두 env를 모두 필수로 요구한다.
5. DB commit 후 journal advance 전 crash/torn fallback에서 prepared resume가 원래 pre-rotation recovery를 post-state로 교체할 수 있다.
6. recovery 교체와 journal reseal 사이에 recovery digest가 어느 journal에도 결합되지 않는 전원 장애 창이 있다.
7. service/listener preflight는 check-then-act라 회전 중 앱 재시작을 막지 못한다. 앱 시작과 회전기가 공유하는 maintenance lock이 필요하다.
8. restore 비교와 archive 사이 writer lock이 풀려 freshness race가 있다.
9. clipboard history/cloud 제외가 없고 clear 재시도 소진/창 종료 실패 시 plaintext를 잔존시킬 수 있다.
10. no-backup `[IO.File]::Replace(..., $null)` 경로가 PowerShell/.NET에서 legal-form 오류를 내는 실제 경로가 있다.
11. setup 재실행이 기존 DB 암호를 바꾼다고 오해시키는 README/phase-8/phase-22 문서가 남아 있다.

## 3가설 runtime audit

- H1 crash/retry consistency: `INCONCLUSIVE`. 실제 self-kill은 도달했으나 resume가 ACL privilege 문제로 `stage_credentials_promote` nonzero 종료했다. silent-success는 관찰되지 않았다.
- H2 writer/listener race: `INCONCLUSIVE`. direct production transaction은 외부 writer를 `database is locked`로 거부했고 Global mutex/listener는 PASS했으나 full orchestration은 `stage_recovery` 이전 종료했다.
- H3 DPAPI/viewer leakage: `INCONCLUSIVE`. isolated ValidateOnly/DPAPI/error boundary는 REFUTED(누출·zero-exit 없음)됐지만 actual WPF clipboard는 미조작이며 static blocker가 남았다.

## 양호한 항목

- public failpoint exact 4, TestMode nonce confinement, dry-run no-write, DPAPI native zero-before-free, listener pre-mutation block, Global mutex DACL은 실제/집중 검증에서 통과했다.
- 검토·QA worktree는 source diff 없이 clean 상태였고 운영 `.env`, DB, secure root는 접근하지 않았다.

Round 3은 승인 증거가 아니다. 위 blocker를 RED→GREEN으로 수정한 새 commit에서 review-work 5개 lane과 debugging runtime audit을 모두 다시 실행해야 한다.
