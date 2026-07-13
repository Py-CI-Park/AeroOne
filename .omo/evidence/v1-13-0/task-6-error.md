# Task 6 — 실패 케이스 / fail-closed 경계 증적

모든 케이스는 synthetic 입력(임시 git 상태 dataclass, synthetic tracked-path 목록, `tmp_path` 스테이징 트리)만 사용했고 실제 저장소 파일/경로/비밀값은 출력하지 않았다. 아래는 `backend/tests/unit/test_offline_package_builder.py`의 실패-경로 테스트가 실제로 확인한 코드/동작이다.

## 1. Build-option fail-closed (override 경로 없음, 6종 전부)

| 요청 옵션 | 결과 코드 | 검증 |
|---|---|---|
| `reuse_node_modules=True` | `reuse-node-modules-forbidden` | `test_validate_build_options_is_fail_closed` |
| `reuse_next_build=True` | `reuse-next-build-forbidden` | 〃 |
| `reuse_wheelhouse=True` | `reuse-wheelhouse-forbidden` | 〃 |
| `include_dev_dependencies=True` | `dev-dependencies-forbidden` | 〃 |
| `allow_public_data=True` | `public-data-forbidden` | 〃 |
| `allow_timestamp_fallback=True` | `tag-required` | 〃 |

CLI 스모크(synthetic tracked-paths, 실제 `packaging/installer-policy.json` 사용):
```
python packaging/build_offline_package_plan.py plan --version 1.13.0 --commit <sha> --tag v1.13.0 --clean \
  --policy packaging/installer-policy.json --tracked-paths <tmp> --include-dev-dependencies
```
출력: `{"ok": false, "code": "dev-dependencies-forbidden"}`, exit=1.

## 2. Dirty worktree — 태그 상태 무관 즉시 거부

`test_dirty_worktree_is_rejected_regardless_of_tag_state`: `GitState(is_clean=False, head_tag="v1.13.0")`(release 조건을 모두 만족하는 태그를 갖고 있어도)로 `determine_release_context()` 호출 시 `dirty-worktree` 즉시 raise, release/QA 판정 로직에 도달하지 않음.

CLI 스모크(clean 플래그 생략): `{"ok": false, "code": "dirty-worktree"}`, exit=1.

## 3. 태그 없는 timestamp fallback — QA 모드로 자동 흡수(에러가 아니라 안전한 대체)

`test_mismatched_or_missing_tag_falls_back_to_qa_mode_not_release`: `head_tag=None` / `"v1.12.2"`(과거 버전) / `"v1.13.0-dev"`(pre-release suffix) 3가지 모두 `mode="qa"`, `publishable=False`로 낙착하고 `output_dir`에 wall-clock 타임스탬프 컴포넌트(`T` 포함 ISO 문자열)가 **전혀 없음**을 어서션(`assert "T" not in context.output_dir`). `allow_timestamp_fallback=True`로 명시적 타임스탬프 대체를 **요청**하면 위 표의 `tag-required`로 거부됨 — "요청 시 거부, 미요청 시 안전한 QA 대체"라는 두 경로를 모두 확인.

## 4. Forbidden top-level / dev-only 경로 — 선택에서 제외(git archive pathspec 미포함과 동일 의미론)

`test_select_allowlisted_paths_excludes_forbidden_and_out_of_allowlist_entries`: `.env`, `backend/data/*.db`, `storage/**`, `.omo/**`, `.gjc/**`, `backend/requirements-dev.txt`, `frontend/node_modules/**`, `frontend/.next/**`, `vendor/**`(allow-list 밖 top-level), `dist/**`, `.worktrees/**` — 11개 forbidden/out-of-scope 경로가 selected 목록에 **0건** 포함됨을 개별 assert로 확인.

`test_select_allowlisted_paths_rejects_empty_selection`: allow-list에 하나도 걸리지 않는 tracked-path 목록(`vendor/only.txt`만)을 넣으면 `empty-selection`으로 거부(공허한 ZIP을 만들지 않음).

## 5. Task 5 verifier가 최종 방어선 — smuggled forbidden path

`test_builder_to_verifier_chain_fails_closed_when_forbidden_path_smuggled_into_stage`: builder의 `select_allowlisted_paths()`를 완전히 우회해 스테이지에 직접 `backend/.env`를 넣고 manifest에도 포함시킨 뒤 `verify_pre_stage()`를 호출 — `PackagePolicyErrorCode.FORBIDDEN_ENV_SECRET`로 거부됨을 확인. builder 단계 실수/우회가 있어도 Task 5 verifier가 ZIP 신뢰 이전에 두 번째로 차단한다는 defense-in-depth를 실증.

## 6. Sandbox launch options fail-closed

`test_validate_sandbox_launch_options_is_fail_closed`:

| 요청 | 결과 코드 |
|---|---|
| `networking_enabled=True` | `network-sandbox-forbidden` |
| `interactive_pause=True` | `interactive-pause-forbidden` |
| `timeout_minutes=0` | `sandbox-timeout-invalid` |
| `timeout_minutes=21`(20분 상한 초과) | `sandbox-timeout-invalid` |

`scripts/sandbox/AeroOnePackageSmoke.wsb.template`은 `<Networking>Disable</Networking>`을 파라미터화하지 않고 고정해 위 첫 번째 케이스를 구조적으로 원천 차단하며, `LogonCommand`는 무인 실행만 지원(interactive pause 스위치 자체가 노출되지 않음).

## 7. Requirements 소스 fail-closed

`test_validate_requirements_source_rejects_dev_requirements_file`: `"backend/requirements-dev.txt"` 파일명이 wheelhouse 소스로 요청되면 `dev-dependencies-forbidden`로 거부(생산 요구사항 파일 `requirements.txt`만 허용).

## 8. offline_package.bat 계약 보존

`--help`/`--dry-run`/인자 없음(기본 real-run) 3가지 호출 형태를 그대로 유지한 채 내부를 `scripts\build_offline_package.ps1` 위임으로 축소했다(코드 리뷰로 확인; wrapper 자체는 실행 스모크를 하지 않음 — PowerShell 본체 실행이 이번 범위 밖 gap이기 때문. `--help` 분기는 스크립트 로직상 PowerShell을 호출하지 않고 즉시 `exit /b 0`).

## 종합

- pytest: `cd backend && PYTHONPATH=. <venv-python> -m pytest tests/unit/test_offline_package_builder.py -q -p no:cacheprovider` → **23 passed**(그중 실패/거부 경로를 어서션하는 테스트가 14개: 6개 build-option 토글 + 4개 sandbox 옵션 + empty-selection 1개 + dirty-worktree 1개 + dev-requirements 1개 + smuggled-forbidden-path 1개), 실패 0.
- 모든 실패 케이스는 redacted 코드(`OfflinePackageBuildErrorCode`/`PackagePolicyErrorCode`)만 노출하고 실제 경로/파일명/비밀값을 로그에 남기지 않는다.
