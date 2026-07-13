# Task 2 — historical release asset containment 실행 증적

- 상태: `SUCCESS`
- 저장소: `Py-CI-Park/AeroOne`
- 승인 receipt: 2026-07-10 사용자 입력 `삭제 승인`
- 실행기: `.omo/evidence/v1-13-0/task-2-contain-historical-assets.sh`
- 실행기 SHA-256: `e5df09b26be329ad13b3b34560cda990130e19c410df580d42378980bf2d3221`
- 기록 시각: `2026-07-10T19:28:09+09:00`

## 실행 계약

Git Bash에서 실행기 전체를 검토한 뒤 다음 구문 검사를 수행했고 exit code `0`을 확인했다.

```bash
"$BASH" -n .omo/evidence/v1-13-0/task-2-contain-historical-assets.sh
```

승인된 실행 명령은 아래와 같다. 승인 guard 문자열 원문은 이 증적에 중복 저장하지 않았으며, 실제 입력값이 실행기에 고정된 exact approval token과 일치했음을 `approval_token_match=true`로 기록한다.

```bash
"$BASH" .omo/evidence/v1-13-0/task-2-contain-historical-assets.sh --execute --approval-token <REDACTED_APPROVAL_GUARD>
```

- execute invocation 수: `1`
- approval_token_match: `true`
- exit code: `0`
- 최종 summary: `mode=execute releases=12 pairs=14 assets=28 mutated_releases=12 validated=true`

## release별 보존·삭제 검증

아래 body 값은 원문이 아니라 warning 아래 기존 suffix의 SHA-256이다. `raw before=after`와 `LF-normalized before=after` 비교를 모두 실행기가 통과했다. 모든 행에서 release ID, tag, tag commit, draft/prerelease가 변경 전후 동일했고 warning prefix가 추가되었다. `other assets` 해시는 target ID를 제외한 정렬 JSON 집합의 변경 전후 SHA-256이다.

| tag | release ID | pairs/assets | suffix raw SHA-256 (before=after) | suffix LF-normalized SHA-256 (before=after) | other assets SHA-256 (before=after) | old URLs |
|---|---:|---:|---|---|---|---:|
| 1.12.1 | 350098299 | 1 / 2 | `b0cdbe528598a9f0356afe4316326a36499e06ed91761cdf1c42c255da425ffd` | `8dfb1a7465259238afbd4f5a799dd51354ad2493ee5abb47a73aa525c009224c` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.12.0 | 349288922 | 1 / 2 | `627b3ff827d8c6d8890affc3c83724ba2965854cde7ef50e993345f970be491e` | `565530511ac0084898c5f8e15cce29784539a5d4cb488dbd2ac3691f87e28f97` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.11.0 | 349160310 | 1 / 2 | `6d60ad51e9d33d316374c27b8b2d58a86e51b3893b2a954f6f9cd46e90fbb3cb` | `d51b1f98b8a5bf333e3c482dec54d49e25f042686c45c83753482646649a15eb` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.10.0 | 348901285 | 1 / 2 | `bad8b3e9261f7d22b6dea9727661938c464ea56747203703d891077fbe227d83` | `9f98341265cb23c8140ac13255f9c38e6eebeec866e6838780f2fd817a5ed9b` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.8.0 | 348433168 | 1 / 2 | `56901fe2433df10215bd67c6539a7d463a4b8a60e8f761d7823a99da94767037` | `f109747927646d9a19f2b5010508a312e2ca66f0bedcce36aaa485deace3cfc2` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.7.1 | 347840668 | 1 / 2 | `b581d8dcbb9cdc29d098807afacede7f289be15ff91e15696ff7e5d847fd85a4` | `cab73b589bdc925c9f8041d620b3e80395e49be3b272fd2595302040ccc7d0dc` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.7.0 | 345933452 | 2 / 4 | `95ca34ff503fa22a0f11c174c86013f157334ad788810b653f577540fec04afe` | `72ae231bc26b50b3bc003bb64491c66abbb0a0510e0244322e056760d6e7b842` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 4/4 = 404 |
| 1.6.2 | 341233206 | 1 / 2 | `6684ecf89d1cb1bb8d612733a54df986354353cb9573bdf54ed8b714697f5043` | `58881f31f07f1c8768d2c4e56ee39dde1329ba190467932118d6ac5f78a36c9d` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.6.1 | 340129636 | 1 / 2 | `9f3e4be2e2bf3f1cd8e77a9d14d7704a418540a8872c76155d251a3e75496338` | `cb79b56a1ec1d4085ee268c0650b25a910b8f7eaf91883dc968d3b7ef928a55e` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.6.0 | 339928210 | 1 / 2 | `b3d4f11346fe03d6d9f97e23b9853f659453e19878520cae855cc8babec7b190` | `be54aa3f660508a0727e0f28ac1a908cc1f66c4ab8ee4dc1ce3d14a2dbe771ba` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |
| 1.5.0 | 339458033 | 2 / 4 | `1d529c3a986ecee80ccac47cf27e51cdcc3f2b79f9ae76ad05cd1aedd2456e3e` | `8854166a8e45d3f0fc34e441f69ce158348c18e2b96905baa470b43d3289923e` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 4/4 = 404 |
| 1.4.4 | 338446523 | 1 / 2 | `291c9ce7882521de55910f64d1d032259dde14fed1859d087c7091b6633c5a35` | `f434a3107ca68b77e940f62dfb4b9dfaee19ec56e33281e79e3f52a8ea004897` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | 2/2 = 404 |

합계:

- exact target assets 삭제: `28/28`
- old browser download URLs: `28/28 = HTTP 404`
- warning prepend 및 suffix dual-hash 보존: `12/12 releases`
- release/tag/tag commit 및 draft/prerelease 보존: `12/12 releases`
- target 외 asset 집합 보존: `12/12 releases`
- 변경된 release body: `12`
- 1.12.2 및 계약 표 밖 asset 변경: `0`

## 종료 상태

- 부분 실패: 없음
- mismatch: 없음
- 추가 삭제 또는 재실행: 없음
- cleanup: 실행 Git Bash process는 exit code `0`으로 종료했고, 실행기는 임시 파일을 생성하지 않는다.
- ZIP/SHA asset 다운로드 또는 내용 열람: 하지 않음
- release/tag 삭제, commit/push/PR, product file/plan/ledger/boulder 변경: 하지 않음
