# Task 3 도움말 credential redaction — Visual QA 증적

## 판정

- 상태: **미완료 / PASS 아님**
- 변경 범위: `frontend/components/layout/help-manual-button.tsx`의 도움말 문자열 1건
- 실제 렌더: Chrome extension, Next dev current source, `375x812`
- 캡처: [`help-admin-375.png`](help-admin-375.png)

## 확인된 사실

| 항목 | 측정값 | 판정 |
|---|---:|---|
| viewport | `375x812` | 실행됨 |
| document `clientWidth / scrollWidth` | `360 / 360` | 가로 overflow 없음 |
| dialog `clientWidth / scrollWidth` | `327 / 327` | 가로 overflow 없음 |
| 변경 대상 cell `clientWidth / scrollWidth` | `185 / 185` | cell 내부 overflow 없음 |
| 변경 문구 DOM | `docs/runbook/credential-rotation.md 자격 증명 사고 대응 런북` 포함 | 렌더됨 |
| 공개 고정 비밀번호 | repo-wide exact grep 0 | 제거됨 |

CJK 글리프 누락이나 tofu는 캡처와 DOM에서 관찰되지 않았습니다. 다만 변경 대상 행은 modal 내부 스크롤 아래에 있어 이 캡처의 가시 영역에는 포함되지 않습니다.

## 완료하지 못한 게이트

1. in-app Browser는 `iab` backend가 없었습니다.
2. agent-browser는 managed/system Chrome 모두 DevTools active port를 만들기 전에 종료됐습니다.
3. 연결된 Chrome extension은 페이지와 관리자 도움말 DOM을 열었지만 내부 스크롤 명령이 timeout되어 변경 행의 가시 캡처를 만들지 못했습니다.
4. 따라서 `1280px` 캡처와 fresh dual-oracle review를 수행하지 않았습니다.
5. dev server는 기존 Next 15 `cookies().getAll()` sync-dynamic-apis 오류 2건과 backend 미기동 fetch fallback을 기록했습니다. 이번 text-only 변경과 직접 관련은 없지만 console 오류 0 게이트는 충족하지 못했습니다.

## 정리 영수증

- Chrome viewport override reset 및 QA tab finalize
- agent-browser active session 0
- Next dev `29502` listener 0
- hotfix worktree의 임시 `frontend/node_modules` junction 제거
- 공유 저장소 `frontend/node_modules` 보존

Final QA owner는 backend가 준비된 production build에서 관리자 도움말을 `375px`과 `1280px`로 다시 열어 변경 행을 가시 영역에 둔 fresh capture와 dual review를 완료해야 합니다.
