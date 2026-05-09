# CLAUDE.md (Claude Code 전용 안내)

본 저장소의 모든 일반 규칙 (한국어 커밋, Lore trailer, PR 형식, 위험 신호, 코드 진실 원천 색인) 은 [`AGENTS.md`](AGENTS.md) 에 정리되어 있습니다. 본 문서는 Claude Code 가 본 저장소에서 작업할 때 **추가로 적용되는 Claude 전용 규칙** 만 다룹니다.

- 기준 commit: `bb94269`
- 진입점 색인: [`docs/INDEX.md`](docs/INDEX.md)

---

## 1. AGENTS.md 규칙 우선

Claude Code 도 [`AGENTS.md`](AGENTS.md) 의 §3 커밋 규칙, §4 PR 규칙, §5 변경 시 따라야 할 순서, §6 위험 신호를 그대로 따릅니다. 본 문서는 그 위에 더해지는 얇은 추가 규칙입니다.

---

## 2. Claude Code 전용 추가 규칙

### 2.1 한국어 커밋의 강제 본문 분량

`AGENTS.md` §3 의 한국어 본문 1~3 문단 요구를 Claude Code 는 항상 **3 문단 이상** 으로 적습니다. Claude Code 가 한 commit 에 묶는 변경의 폭이 사람 작업자보다 넓은 경우가 많아, 짧은 본문은 의도와 영향 범위를 다음 독자가 따라잡지 못하게 만듭니다.

본문 3 문단의 권장 구성:

1. **배경** — 무엇을 해결하려고 했는가, 왜 지금 이 변경이 필요했는가.
2. **선택한 접근** — 무엇을 어떻게 바꿨는가, 왜 그 방식인가.
3. **검토하고 제외한 대안** — 다른 길 (a)(b)(c) 를 짧게 적고 거부 사유.

### 2.2 Lore trailer 의 분량

Claude Code 는 trailer 값 한 줄 만으로 끝내지 않습니다. 특히 `Tested:` 와 `Not-tested:` 는 실제 실행한 명령과 그 출력 요지를 한 묶음으로 적어, 다음 독자가 "이 commit 의 검증 범위가 어디까지인가" 를 한 자리에서 확인할 수 있게 합니다.

### 2.3 변경의 트라이앵글

코드 / 배치 / 테스트 / 문서 네 자리 중 한 자리만 손대고 끝내지 않습니다. 보안 정책, DB 분기, 운영 모드, 폐쇄망 옵션의 변경은 다음 4자리를 동시에 commit 에 포함합니다.

- 코드 본문 (`backend/`, `setup_offline.bat`, `start_offline.bat` 등)
- 회귀 테스트 (`backend/tests/unit/`)
- 문서 (해당 `docs/runbook/*.md`, `docs/CLOSED_NETWORK_GUIDE.md`, `docs/INDEX.md`)
- 코드 안 docstring 또는 batch `:help` 라벨

이 4자리 중 한 자리라도 빠지면 다음 독자가 어떤 자리에서 진실 원천이 흐려졌는지 추적이 어려워집니다.

### 2.4 ralph / autopilot 모드 종료 절차

Claude Code 가 ralph 또는 autopilot 모드로 작업할 때는 작업 완료 후 반드시 `/oh-my-claudecode:cancel` 을 호출해 mode state 를 정리합니다. 정리 없이 세션을 종료하면 다음 세션의 stop hook 이 잘못된 mode 를 감지해 의도치 않은 재진입을 일으킵니다.

### 2.5 wiki 입구 갱신 의무

Claude Code 가 새 문서를 추가하거나 기존 문서의 본문 섹션을 크게 바꿀 때, [`docs/INDEX.md`](docs/INDEX.md) 의 해당 섹션도 같은 commit 에서 갱신합니다. wiki 의 입구가 코드 변경과 어긋나면 다음 독자가 잘못된 자리에 도착합니다.

### 2.6 릴리즈 사이클의 강화 규칙

[`AGENTS.md`](AGENTS.md) §9 의 5 단계 릴리즈 사이클을 Claude Code 는 다음 강화 규칙과 함께 따릅니다.

- **dev 브랜치 보존 절대** — 운영자가 명시적으로 "정리해" 라고 말하지 않는 한 `<버전>-dev` 브랜치를 `git branch -d` 또는 `git push --delete` 로 삭제하지 않습니다. 1.0.2-dev / 1.0.3-dev 가 origin 에 남아있는 것이 의도된 상태입니다.
- **버전 표기 commit 단독화** — README 의 배지 / "검증" 섹션 한 줄 두 자리는 release 직전 마지막 commit 한 개로만 묶고, 다른 코드 / 문서 변경과 섞지 않습니다. 다음 release 직전에 같은 한 줄 갱신만 반복하면 되도록 표면을 최소화합니다.
- **merge commit 의 본문은 release note 의 초안** — `git merge --no-ff` 의 commit 메시지 본문이 GitHub release 의 notes 와 거의 같은 구조 (변경 분류 + commit 목록 + 호환성 + 검증) 가 되도록 작성합니다. 같은 정보를 두 자리에 다시 적지 않아도 됩니다.
- **검증 게이트는 명시적 측정값으로** — pytest 카운트 (66 passed 등), Playwright 측정값 (iframe.height, body.scrollHeight 등), broken-link grep 결과 (0 건) 같은 숫자를 commit 본문의 `Tested:` 에 포함합니다. "통과 확인함" 같은 추상 표현은 거부.
- **긴급 hotfix 도 한국어 + Lore trailer** — AGENTS.md §9.4 의 hotfix 예외도 §3 commit 규칙과 §2.1 본문 분량은 그대로 적용합니다. 긴급하다고 영문 한 줄 commit 으로 우회하지 않습니다.

---

## 3. 진입점 색인

| 독자 / 상황 | 입구 |
|---|---|
| 일반 규칙 전체 | [`AGENTS.md`](AGENTS.md) |
| 처음 보는 사람 | [`README.md`](README.md) |
| 폐쇄망 운영자 | [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) |
| 개발자 | [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) |
| 기여자 | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| 전체 문서 색인 | [`docs/INDEX.md`](docs/INDEX.md) |
| 단계별 변경 의도 | [`docs/reports/INDEX.md`](docs/reports/INDEX.md) |
| 설계 산출물 (plan/spec) | [`docs/superpowers/INDEX.md`](docs/superpowers/INDEX.md) |
