# Task 2 — 원격 동기화와 historical ZIP 중앙-directory-only 재감사 증적

- 시작: `2026-07-10T18:18:54+09:00`
- 감사 완료: `2026-07-10T18:50:27+09:00`
- 브랜치/HEAD: `1.13.0-dev@034bd0324af9f69268d25ae605d9be0fd5c632fb`
- upstream divergence: `0 0`
- `origin/main...HEAD`: main 쪽 `0`, dev 쪽 `2`
- `git pull --ff-only`: `Already up to date.`
- unexpected product dirty: `0` (기존 OMO 계획·증적 상태만 변경)

## 감사 방식

- `gh api --paginate 'repos/Py-CI-Park/AeroOne/releases?per_page=100'`로 release 46개를 열거했다.
- 원격 ZIP은 HTTP `206 Partial Content`만 허용해 128 KiB tail, ZIP64 EOCD가 필요한 2건의 56-byte record, 중앙 디렉터리 범위만 메모리에 읽었다. HTTP 200은 본문을 읽기 전에 실패하도록 구현했다.
- Task 1에서 삭제된 1.12.2는 당시 remote digest·size와 일치한 pre-existing local archive에서 tail과 중앙 디렉터리만 sparse read했다.
- filename은 메모리에서 category count로만 집계하고 즉시 버렸다. raw entry name, entry stream/content, secret value는 출력·기록하지 않았다.
- policy: exact `.env.example`만 env에서 제외; `_database`, `backend/data`와 DB 확장자, `storage`, `backup/backups` state path, `.git/.omc/.omo/.worktrees/.codex/.claude/.agents`, venv/node_modules/Python·Next cache와 dev artifact를 unsafe로 분류했다.
- 일반 dependency 파일명에 포함된 `backup`은 state가 아니므로 제외하고, backup은 path segment 또는 `backend/data` 문맥으로 제한했다.

## 최종 실행 결과

- release count: `46`
- remote ZIP asset: `14`
- remote audited / unsafe / safe: `14 / 14 / 0`
- Task 1 contained pair absent: `true`
- planning table total explained: `15`
- audit error / contract mismatch: `0 / 0`
- remote range requests / bytes: `30 / 49,161,286`
- local range requests / bytes: `2 / 1,935,997`
- full archive download: `0`
- entry stream read: `0`
- raw entry-name output: `0`

카테고리 count 순서는 `env/database/storage/backup/agent-state/dev-artifact`이며 한 entry가 여러 카테고리에 포함될 수 있다.

| Tag | ZIP / SHA asset ID | ZIP digest / SHA digest | Verdict | Counts | CD entries / bytes | ZIP64 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.12.2 | 469662394 / 469662393 | `b67f595f0b33896015dfe1651f74d1f883de157094bf347bdf81f1d7d0c2e4cd` / `0b308b6174cd4086eb082b28338ff670fa1b27fb72e9e277dd3e81980490ea9e` | env/database/storage/agent-state/dev-artifact | 5/92/8/0/1/15350 | 16141 / 1804925 | false |
| 1.12.1 | 468959744 / 468959745 | `9b42988bed4344b83f8691b0e297f9489d0a861e6ac35fb8b6c92be2d26648f2` / `89821736f134c9b432b8d98af324b14430f5f8c54d3d5b3da329413ffab557a1` | env/database/storage/agent-state/dev-artifact | 5/92/8/0/1/15350 | 16139 / 1804743 | false |
| 1.12.0 | 467598771 / 467598772 | `01608c2f4fa039e8cf1cbdcd82f9995dbb1173e52f2898248d02ae64b8f4cb52` / `91f08a868288456b87f7c44d497de6691873fa9883788453e4af7090c8cc00b1` | env/database/storage/agent-state/dev-artifact | 5/92/8/0/1/15342 | 16130 / 1803808 | false |
| 1.11.0 | 467141283 / 467141282 | `c8435df405b1a84158874965e7e36525a3dfc31a9c0b0cf7cf37bd453c0db942` / `be43aaafa0c19c7c60ab4fc7c2d5c26d8bdb09c64fa731059855f0ab72437879` | env/database/storage/agent-state/dev-artifact | 5/92/8/0/1/15342 | 16119 / 1802754 | false |
| 1.10.0 | 466204038 / 466204039 | `5bfd1e8dd141f505b169afbb4f6e7114f337248e48ab80c3b8c91684b3916ad3` / `02fb5bba263f66cf95abdae76ef6dc0d4f79f1dc7777c9c31d42814f40cdeea4` | env/database/storage/agent-state/dev-artifact | 5/92/8/0/1/15336 | 16069 / 1797385 | false |
| 1.8.0 | 465087963 / 465087964 | `8abea7926e0c5b8836868ec9a2ecf774a610ed5c87d96e2efa4187aa08b10ceb` / `e6897ded0a0f5dc8892c6fd30b81f89610d00bd3e7a1ce18f0b02c123f186e7c` | env/database/storage/agent-state/dev-artifact | 5/91/8/0/1/15315 | 16022 / 1792191 | false |
| 1.7.1 | 463971385 / 463971384 | `492d99335b5b4a939a86d07e89757e5840ce2f52ba7cddcbb44ede506ea033ca` / `006064483b713cd12125ab8afdaf3d76db582dd992c1dde5c3b9ece9221a6531` | env/database/storage/agent-state/dev-artifact | 5/91/7/0/1/15307 | 15995 / 1789583 | false |
| 1.7.0 bundle | 460314227 / 460314229 | `df9d9d7bc3ed9b98561e3cd6a898b9cbcd29a5e28c50934c6ad8ff8b8e11189d` / `044f7bfe7efda686934ee0f5e2d132f51d9ede7be442252e037197339ccdd15b` | storage/agent-state/dev-artifact | 0/0/24/0/9/51788 | 82526 / 12944031 | true |
| 1.7.0 offline | 460314230 / 460314228 | `028f0d2f9a9f0563df36dbe121a57581057dd63966c97808e6c97dbf5b22ae07` / `d97e365eddb4a8c0fcc82e905194453f1065f92052375ed582e037a2927f7d70` | storage/dev-artifact | 0/0/3/0/0/15094 | 15677 / 1755909 | false |
| 1.6.2 | 451005119 / 451005118 | `246fad2df15770f3a36dfa3866f0866bc48e60b18253a1da9ff809f4c588cbe9` / `5493c7d2f4bd23724904527f5c6f7c699db8e60289c0df5c5d943b6f71685335` | storage/dev-artifact | 0/0/3/0/0/15104 | 15688 / 1756977 | false |
| 1.6.1 | 449183210 / 449183209 | `c28c4d431e587d3df252984a1a4c8012f5301aee08a4ef230e049fca8f225f9f` / `97e9e60f8242772bf06ba6b87b47b628ca98309b4619fbd19a5035f0047d50ea` | env/database/storage/agent-state/dev-artifact | 5/94/7/0/1/15301 | 16088 / 1798179 | false |
| 1.6.0 | 448898337 / 448898338 | `60b162581e53dbba5c155c1e5ea7b794741d7efe65e2999dafa1a5cbf038fc00` / `49650d0182affe374b5d53b8e031581b39de238fbc3e20cbd72bdf2b64c67144` | env/database/storage/agent-state/dev-artifact | 5/94/7/0/1/15301 | 16087 / 1798081 | false |
| 1.5.0 bundle | 448050524 / 448050525 | `9a057cf34de86ab220202b3b215baff32c5f5a1617ea55e33bcc8d575d55c6ec` / `7f92655d8afa9f1d6f9faf7e9d85e5dcc09800dfd5d0bd04fbd656e60e33e114` | storage/agent-state/dev-artifact | 0/0/24/0/9/51788 | 82526 / 12944031 | true |
| 1.5.0 offline | 448050213 / 448050212 | `faa0887c710a76af3df579ba41e35bcf7c9f23d57fd117177af280126ea8eebe` / `66ac8dc080f6a18562a291c01c843b9d4c1dcdc219127b0c444a12905e0671a9` | env/database/storage/agent-state/dev-artifact | 5/94/7/0/1/15286 | 16029 / 1791840 | false |
| 1.4.4 | 445483030 / 445483029 | `2d9da5e8188ec1d93736e1a2c5c4e977b5fef86a32cb8da728f59fb9c387bfd2` / `baf72bbefacda00e147199e7935ef2001f0942ae2a32c53311cc7e9d449142d1` | storage/dev-artifact | 0/0/3/0/0/15094 | 15581 / 1746654 | false |

## 현재 게이트

`2026-07-10` 사용자의 명시적 "삭제 승인" 뒤 exact ZIP/SHA 14쌍(28개 자산)을 삭제하고 12개 릴리스에 보존 경고를 추가했다. 실행기는 `releases=12 pairs=14 assets=28 mutated_releases=12 validated=true`로 종료했으며, 독립 판정은 `AdversarialVerify: confirmed`이다. Task 3과 1.12.3 릴리스의 승인 차단은 해제되었다.

- 실행 증적: `.omo/evidence/v1-13-0/task-2-execution.md`
- 독립 검증: `.omo/evidence/v1-13-0/task-2-verification.md`
- 비차단 증적 개선: 삭제 전 exact browser URL 원문 또는 비밀이 아닌 URL 해시 목록을 별도 보존해 제3자 재실행성을 높인다.

## Exact containment dry-run checkpoint — 2026-07-10T19:01:25+09:00

- 실행기: `.omo/evidence/v1-13-0/task-2-contain-historical-assets.sh`
- shell syntax: exit `0`
- `--help`: exit `0`
- `--execute` without exact approval token: exit `64`, `error=explicit_owner_approval_required`
- default dry-run: exit `0`
- dry-run summary: releases `12`, ZIP/SHA pairs `14`, assets `28`, mutated releases `0`, validated `true`
- 모든 release의 warning prefix는 아직 `false`이며, target 외 asset 집합 SHA-256은 빈 집합의 canonical hash `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`로 일치했다.
- dry-run 뒤 원격 ZIP/SHA exact ID 집합은 감사 전과 동일하다.

| Tag | Release ID | Raw body SHA-256 | LF-normalized body SHA-256 |
| --- | --- | --- | --- |
| 1.12.1 | 350098299 | `b0cdbe528598a9f0356afe4316326a36499e06ed91761cdf1c42c255da425ffd` | `8dfb1a7465259238afbd4f5a799dd51354ad2493ee5abb47a73aa525c009224c` |
| 1.12.0 | 349288922 | `627b3ff827d8c6d8890affc3c83724ba2965854cde7ef50e993345f970be491e` | `565530511ac0084898c5f8e15cce29784539a5d4cb488dbd2ac3691f87e28f97` |
| 1.11.0 | 349160310 | `6d60ad51e9d33d316374c27b8b2d58a86e51b3893b2a954f6f9cd46e90fbb3cb` | `d51b1f98b8a5bf333e3c482dec54d49e25f042686c45c83753482646649a15eb` |
| 1.10.0 | 348901285 | `bad8b3e9261f7d22b6dea9727661938c464ea56747203703d891077fbe227d83` | `9f98341265cb23c8140ac13255f9c38e6e6ebeec866e6838780f2fd817a5ed9b` |
| 1.8.0 | 348433168 | `56901fe2433df10215bd67c6539a7d463a4b8a60e8f761d7823a99da94767037` | `f109747927646d9a19f2b5010508a312e2ca66f0bedcce36aaa485deace3cfc2` |
| 1.7.1 | 347840668 | `b581d8dcbb9cdc29d098807afacede7f289be15ff91e15696ff7e5d847fd85a4` | `cab73b589bdc925c9f8041d620b3e80395e49be3b272fd2595302040ccc7d0dc` |
| 1.7.0 | 345933452 | `95ca34ff503fa22a0f11c174c86013f157334ad788810b653f577540fec04afe` | `72ae231bc26b50b3bc003bb64491c66abbb0a0510e0244322e056760d6e7b842` |
| 1.6.2 | 341233206 | `6684ecf89d1cb1bb8d612733a54df986354353cb9573bdf54ed8b714697f5043` | `58881f31f07f1c8768d2c4e56ee39dde1329ba190467932118d6ac5f78a36c9d` |
| 1.6.1 | 340129636 | `9f3e4be2e2bf3f1cd8e77a9d14d7704a418540a8872c76155d251a3e75496338` | `cb79b56a1ec1d4085ee268c0650b25a910b8f7eaf91883dc968d3b7ef928a55e` |
| 1.6.0 | 339928210 | `b3d4f11346fe03d6d9f97e23b9853f659453e19878520cae855cc8babec7b190` | `be54aa3f660508a0727e0f28ac1a908cc1f66c4ab8ee4dc1ce3d14a2dbe771ba` |
| 1.5.0 | 339458033 | `1d529c3a986ecee80ccac47cf27e51cdcc3f2b79f9ae76ad05cd1aedd2456e3e` | `8854166a8e45d3f0fc34e441f69ce158348c18e2b96905baa470b43d3289923e` |
| 1.4.4 | 338446523 | `291c9ce7882521de55910f64d1d032259dde14fed1859d087c7091b6633c5a35` | `f434a3107ca68b77e940f62dfb4b9dfaee19ec56e33281e79e3f52a8ea004897` |

실행 모드는 release/tag/draft/prerelease/tag commit과 warning 아래 원문 body dual hash, target 외 asset 집합을 보존하며 exact 28 asset ID만 삭제하고 old URL 404를 확인하도록 구성했다. 승인 토큰은 인증 비밀이 아니라 오조작 방지 장치이며, owner의 명시 승인 자체를 대체하지 않는다.
