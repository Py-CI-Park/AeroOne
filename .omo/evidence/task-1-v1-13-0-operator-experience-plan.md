# Task 1 QA Evidence - v1.13.0 Operator Experience Plan

Verdict: PASS

Task: Create the v1.13.0 development branch and protect unrelated dirty work.

Surface and invocation: Git CLI from `C:/Users/KAI/Chanil_Park/Project/AeroOne/.worktrees/1.13.0-dev` and `C:/Users/KAI/Chanil_Park/Project/AeroOne`.

## Command Outputs Summarized

| Ref | Surface | Exact invocation | Exit | Observed output |
|---|---|---:|---:|---|
| CMD-1 | worktree Git CLI | `git branch --show-current` | 0 | `1.13.0-dev` |
| CMD-2 | worktree Git CLI via `cmd.exe` | `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` | 0 | `origin/main` |
| CMD-2a | worktree Git CLI via PowerShell | `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` | 1 | PowerShell parsed `@{upstream}` as a hash literal; rerun through `cmd.exe` recorded in CMD-2. |
| CMD-3 | worktree Git CLI | `git rev-list --left-right --count 1.13.0-dev...origin/main` | 0 | `0 0` |
| CMD-4 | worktree Git CLI | `git status --short --branch` | 0 | `## 1.13.0-dev...origin/main`; `?? .omo/` |
| CMD-5 | main worktree Git CLI | `git status --short --branch` | 0 | `## main...origin/main`; `?? .omo/`; `?? _codex_exports/`; `?? pkg264_082120.zip`; `?? pkg264_082120/`; `?? pkg264_082225.zip`; `?? pkg264_082225/` |
| CMD-6 | main worktree Git CLI | `git worktree list --porcelain` | 0 | Main worktree at `C:/Users/KAI/Chanil_Park/Project/AeroOne` on `refs/heads/main`; dev worktree at `.worktrees/1.13.0-dev` on `refs/heads/1.13.0-dev`; both at `2f592c46aacab83c3cfa12610a87651082deba5e`. |

Main worktree untracked paths observed as out of scope:

- `.omo/`
- `_codex_exports/`
- `pkg264_082120.zip`
- `pkg264_082120/`
- `pkg264_082225.zip`
- `pkg264_082225/`

## Pass Criteria

| Criterion | Evidence | Verdict |
|---|---|---|
| Branch command returns exactly `1.13.0-dev`. | CMD-1 output was `1.13.0-dev`. | PASS |
| Upstream command returns exactly `origin/main`. | CMD-2 output was `origin/main`. | PASS |
| Rev-list command returns exactly `0 0`. | CMD-3 output was `0 0`. | PASS |
| Evidence lists main worktree untracked paths as out of scope. | CMD-5 captured `.omo/`, `_codex_exports/`, `pkg264_082120.zip`, `pkg264_082120/`, `pkg264_082225.zip`, `pkg264_082225/`. | PASS |

## Manual QA Matrix

### surfaceEvidence

| Scenario id | Criterion reference | Surface | Exact invocation | Verdict | artifactRefs |
|---|---|---|---|---|---|
| S1 | branch-current | Git CLI, dev worktree | `git branch --show-current` | PASS | A1 |
| S2 | upstream-origin-main | Git CLI, dev worktree via `cmd.exe` | `git rev-parse --abbrev-ref --symbolic-full-name @{upstream}` | PASS | A1 |
| S3 | branch-not-diverged | Git CLI, dev worktree | `git rev-list --left-right --count 1.13.0-dev...origin/main` | PASS | A1 |
| S4 | dev-worktree-status | Git CLI, dev worktree | `git status --short --branch` | PASS | A1 |
| S5 | main-dirty-scope | Git CLI, main worktree | `git status --short --branch` | PASS | A1 |
| S6 | worktree-registration | Git CLI, main worktree | `git worktree list --porcelain` | PASS | A1 |

### adversarialCases

| Scenario id | Criterion reference | Adversarial class | Expected behavior | Verdict | artifactRefs |
|---|---|---|---|---|---|
| A-1 | dirty-worktree | dirty_worktree | Main repo dirty paths are observed and classified out of scope; no product files are modified. | PASS | A1 |
| A-2 | branch-not-diverged | stale_state | `git rev-list --left-right --count 1.13.0-dev...origin/main` returns `0 0`. | PASS | A1 |
| A-3 | branch/upstream/worktree-registration | misleading_success_output | Branch, upstream, status, and worktree list are all recorded instead of trusting prior worker claims. | PASS | A1 |
| A-4 | command-completion | hung_or_long_commands | Commands complete quickly without hanging. | PASS | A1 |
| A-5 | input-shape | malformed input | Not applicable: fixed Git commands and paths were supplied by the task. | PASS | A1 |
| A-6 | instruction-integrity | prompt injection | Not applicable: no untrusted file content was executed or treated as instructions. | PASS | A1 |
| A-7 | control-flow | cancel/resume | Not applicable: this run completed in one uninterrupted executor pass. | PASS | A1 |
| A-8 | test-stability | flaky tests | Not applicable: no tests were requested or needed for branch/worktree verification. | PASS | A1 |
| A-9 | interruption-history | repeated interruptions | Not applicable to this run: earlier worker attempts were not trusted; commands were reproduced here. | PASS | A1 |

### artifactRefs

| id | kind | Description | Path |
|---|---|---|---|
| A1 | markdown evidence | Task 1 Git command transcript summary, pass criteria, adversarial QA, and cleanup receipt. | `C:/Users/KAI/Chanil_Park/Project/AeroOne/.worktrees/1.13.0-dev/.omo/evidence/task-1-v1-13-0-operator-experience-plan.md` |

## Cleanup Receipt

No cleanup was required or performed. Writes were limited to this evidence file and the required ledger append. Product files, commits, branch changes, `_codex_exports/`, `pkg264_082120*`, and `pkg264_082225*` were not modified.
