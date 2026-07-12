# Task 6 — 공개 오프라인 패키지 builder(git archive allow-list) + wrapper + Sandbox smoke harness

## 결과

- 상태: 자율 가능 부분 완료(GREEN). 실제 npm ci/build/wheelhouse full run, 실제 installer 바이너리, Windows Sandbox 실행은 범위 밖(하단 gap).
- 작업 위치: `.worktrees/1.12.3-hotfix` (로컬 main, HEAD `e1ddf3b`). root worktree·기존 커밋 파일 무수정.
- 실제 운영 환경 파일, DB, `%USERPROFILE%\AeroOne-secure`: 변경하지 않음
- 검증 대상: pytest `tmp_path` 임시 작업공간에 생성한 synthetic 소스 트리/git 상태/tracked-path 목록
- 비밀값, 실제 파일명 원문 출력: 0건 (evidence에는 카테고리/코드만 기록)

## 구현 계약

- `backend/app/operations/offline_package_build_contracts.py`: `OfflinePackageBuildErrorCode`(12개 코드), `OfflinePackageBuildError`, `BuildOptions`/`GitState`/`SandboxLaunchOptions`(pydantic, `frozen=True, extra="forbid"`), `ReleaseContext`/`BuildPlan`(dataclass).
- `backend/app/operations/offline_package_policy.py`: I/O 없는 순수 경계 로직.
  - `validate_build_options()`: reuse-node-modules/reuse-next-build/reuse-wheelhouse/include-dev-dependencies/allow-public-data/allow-timestamp-fallback **6개 토글 전부** 예외 없는 fail-closed 거부(override 경로 없음).
  - `validate_requirements_source()`: wheelhouse가 `backend/requirements.txt`가 아니면 즉시 거부(dev 파일명 거부).
  - `determine_release_context()`: dirty worktree는 태그 상태와 무관하게 즉시 거부. HEAD의 exact annotated tag가 `version`과 정확히 일치할 때만 release 모드(publishable=True, `dist/AeroOne-offline-<version>.zip`). 태그 없음/불일치는 자동으로 QA 모드(publishable=False, `artifacts/qa/<version>/<version>-pr-<commit8>`, wall-clock timestamp 미사용 — deterministic commit-based 이름만 사용).
  - `select_allowlisted_paths()`: Task 5 `check_top_level_allowed`/`classify_forbidden`를 재사용해 tracked-path 목록에서 allow-list 밖/forbidden-category 경로를 **제외**(`git archive <pathspec>`가 목록에 없는 경로를 자동 제외하는 것과 동일한 의미론). 추가로 builder 전용 denylist(`backend/requirements-dev.txt`, `frontend/node_modules/**`, `frontend/.next/**`, `offline_assets/python-wheels/**`)를 겹쳐 적용 — 실제 `packaging/installer-policy.json`은 node_modules를 카테고리 금지하지 않으므로(정식 패키지에 필요한 런타임 자산이라) 이 builder 전용 필터가 없으면 `backend/requirements-dev.txt`가 선택에 새는 실측 버그를 CLI 스모크로 발견해 수정함(하단 TDD 참고).
  - `plan_build()`: 위 3단계(옵션 검증 → release/QA 컨텍스트 → allow-list 선택)를 순서대로 오케스트레이션. 첫 위반에서 즉시 예외(부분 plan 미생성).
  - `validate_sandbox_launch_options()`: networking-enabled/interactive-pause 스위치 전부 거부, timeout은 `0 < n ≤ 20`분만 허용.
  - `build_manifest_entries()`: Task 5 `compute_sha256` 재사용해 manifest entry 생성(hash 계산 로직 중복 구현 없음).
- `packaging/build_offline_package_plan.py`: Task 5 `verify_offline_package.py`와 동일한 CLI 계약 패턴. `plan` 서브커맨드(정책 위반 시 `{"ok": false, "code": "<redacted>"}` + exit 1, 성공 시 mode/publishable/output_dir/zip_name/selected_count), `manifest` 서브커맨드(스테이지 루트 + 선택 경로 목록 → manifest.json 생성).
- `scripts/build_offline_package.ps1`: 신규 builder 본체. git plumbing(`git status --porcelain`, `git rev-parse HEAD`, `git describe --tags --exact-match HEAD`, `git ls-files`)만 담당하고 정책 판정은 전부 Python plan CLI에 위임. real-run 경로: `git archive --format=zip -- <selected-paths>`로 allow-list 스테이지 생성 → `npm ci`(재사용 없음) → `npm run build` → `npm prune --omit=dev`(production prune) → `pip download -r backend/requirements.txt -d offline_assets/python-wheels`(파일명 fail-closed 재확인) → `offline_installers/` → `offline_assets/installers/` 복사(Task 5 필수 installer 2종 자리) → manifest 생성(Python CLI) → `Verify-OfflinePackage.psm1`의 pre-stage/post-zip 함수로 Task 5 검증 통과 후에만 ZIP 생성 → SHA-256 `.sha256` 파일. `-DryRun`은 plan만 출력하고 종료.
- `offline_package.bat`: 기존 robocopy deny-list 본체를 제거하고 `scripts\build_offline_package.ps1` 호출로 축소. `--dry-run`/`--help` 호출 계약(인자 없음/두 옵션)을 그대로 보존.
- `scripts/sandbox/AeroOnePackageSmoke.wsb.template`: `Networking=Disable`(고정, 파라미터화하지 않음), package 매핑은 `ReadOnly=true`, receipt 매핑은 `ReadOnly=false`, `LogonCommand`가 guest bootstrap을 무인 실행.
- `scripts/sandbox/run_offline_package_smoke.ps1`: 호스트 측 launcher. timeout ≤20분 재검증(정책과 이중 방어), WSB 렌더링, `WindowsSandbox.exe` 실행, receipt 폴링, `ok=false` 또는 timeout이면 실패로 판정(exit 1).
- `scripts/sandbox/guest_bootstrap.ps1`: guest 측. Python이 아직 설치되지 않은 시점이므로 "verifier"는 순수 PowerShell `Get-FileHash`로 manifest.json 대비 재해시(Task 5 verifier와 동일한 hash-compare 원칙, Python 의존성 없이 재구현) → Python silent installer(exit 0 필수, 3010=재부팅 필요=FAIL) → Node MSI silent installer(동일 계약) → 레지스트리에서 PATH 재조회 → python/node/npm 정확한 버전 assert → `setup_offline.bat --no-pause --local`/`start_offline.bat --no-pause --local`(무인, pause 없음) → health check → frontend 접근성 → login flow → `_database\nsa` 기본 empty 확인 → `stop_all.bat`. 각 단계는 `$CurrentStep` 추적 후 단일 `catch`에서 실패 단계를 기록하고, 임시 파일에 쓴 뒤 `Move-Item`으로 최종 `receipt.json`에 원자적 rename(부분 기록 노출 없음).

## TDD 및 자동 검증

- RED: 최초 CLI 스모크에서 실제 `packaging/installer-policy.json`(node_modules/requirements-dev.txt를 카테고리 금지하지 않음)을 대상으로 `select_allowlisted_paths`를 호출했더니 `backend/requirements-dev.txt`와 `frontend/node_modules/pkg/index.js`가 selected_count=8에 포함되는 실측 버그 발견 → `_is_builder_denied_path()` 추가(builder 전용 denylist)로 재현·수정, CLI 재실행으로 `selected_count=6`(dev-only 항목 완전 제외) 확인.
- RED: basedpyright에서 파라미터화 테스트의 `dict[str, bool | int]` 언패킹(`SandboxLaunchOptions(**kwargs)`)이 pydantic strict 필드 타입과 불일치(`error: Argument of type "bool | int" ...`) → Task 5 `test_package_policy_verifier.py`의 `Callable` 팩토리 패턴을 그대로 채용해 `make_options: Callable[[], BuildOptions|SandboxLaunchOptions]` 람다 파라미터로 재작성, 0 errors로 전환.
- GREEN: `cd backend && PYTHONPATH=. "D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe" -m pytest tests/unit/test_offline_package_builder.py tests/unit/test_package_policy_verifier.py tests/unit/test_installer_policy_json.py -q -p no:cacheprovider` → **44 passed**(신규 23 + 기존 Task 5 21), 실패 0.
- Builder→Task5-verifier 체인: `test_builder_to_verifier_chain_passes_for_a_compliant_synthetic_repo`(synthetic tracked-path 목록에 allow-list 경로 + forbidden 경로 혼재 → `plan_build()`로 release 모드/selected_paths 산출 → 선택된 경로만 materialize + 2개 Task 5 installer 자리 → manifest 생성 → `verify_pre_stage`/`verify_post_zip` **PASS**) 및 `test_builder_to_verifier_chain_fails_closed_when_forbidden_path_smuggled_into_stage`(스테이지에 `.env`가 우회 반입돼도 Task 5 verifier가 `FORBIDDEN_ENV_SECRET`로 **fail-closed** 거부 — defense in depth) 로 체인 확인.
- 경계 값 테스트: release 모드는 exact tag=HEAD=version에서만 진입(태그 없음/`v1.12.2`/`v1.13.0-dev` 3가지 mismatch 케이스 모두 QA 모드로 자동 전환, 출력 경로에 `T`(ISO timestamp 마커) 미포함 확인), dirty worktree는 태그 상태 무관 즉시 거부, 6개 옵션 토글 전부 override 없이 거부, sandbox launch 4개 fail-closed 케이스(networking/interactive-pause/timeout=0/timeout=21) 확인.
- CLI 스모크: `packaging/build_offline_package_plan.py plan`(release/QA 양쪽 모드, `--include-dev-dependencies` 거부 확인, dirty 거부 확인)과 `manifest` 서브커맨드(synthetic 2-파일 스테이지 → manifest.json 정상 생성) subprocess 실행으로 exit code/JSON 계약 확인.
- ruff: `ruff check backend/app/operations/offline_package_build_contracts.py backend/app/operations/offline_package_policy.py packaging/build_offline_package_plan.py backend/tests/unit/test_offline_package_builder.py` → **All checks passed**.
- basedpyright: `cd backend && basedpyright app/operations/offline_package_build_contracts.py app/operations/offline_package_policy.py ../packaging/build_offline_package_plan.py tests/unit/test_offline_package_builder.py` → **0 errors**, 74 warnings(0 errors 요건 충족; warning은 Task 5 `verify_offline_package.py` 기준선과 동일한 `reportAny`/`reportUnusedCallResult` 계열).
- PowerShell AST: `[System.Management.Automation.Language.Parser]::ParseFile()`로 신규 3개 `.ps1`(`scripts/build_offline_package.ps1`, `scripts/sandbox/run_offline_package_smoke.ps1`, `scripts/sandbox/guest_bootstrap.ps1`) 전부 **0 parse errors** 확인. 이 과정에서 PowerShell 7 전용 `??` null-coalescing 연산자가 두 곳(`build_offline_package.ps1`의 `--tag` 인자, `guest_bootstrap.ps1`의 catch 블록)에 실수로 들어간 것을 발견해 PS 5.1 호환 조건문(`if ($x) { $x } else { '' }`, `$CurrentStep` 추적 변수)으로 교체 — 환경이 PowerShell 5.1이라는 CONTEXT 제약을 실제로 검증한 사례.
- WSB 템플릿: `[xml](Get-Content -Raw ...)`로 `AeroOnePackageSmoke.wsb.template` XML 파싱 확인(정상).

## 의도적으로 수행하지 않은 항목 (gap)

- **실제 `npm ci`/`npm run build`/`npm prune`, 실제 `pip download` wheelhouse full run은 이 sandbox에서 수행하지 않음.** 이유: 이 환경에 실제 frontend 의존성 트리를 온라인으로 새로 받는 것은 시간/네트워크 상 이번 자율 범위 밖이며(다른 Task들과 동일 패턴), `scripts/build_offline_package.ps1`의 `Invoke-FrontendBuild`/`Invoke-BackendWheelhouse` 함수는 완전히 구현되어 있으나 실행 증적은 없다. 경계 로직(allow-list 선택, release/QA 판정, 옵션 fail-closed 거부)은 synthetic 입력으로 100% pytest 검증됨.
- **실제 Python 3.12.7 / Node 20.18.0 installer 바이너리는 이 저장소에 추가하지 않음** (`offline_installers/`가 비어 있는 상태 그대로 유지). Task 5 required-installer 정책(정확한 SHA-256/Authenticode thumbprint/subject)은 이미 `packaging/installer-policy.json`에 고정되어 있으므로, 실제 바이너리를 배치하면 `scripts/build_offline_package.ps1`이 그대로 동작해야 하지만 이번 범위에서는 바이너리 미반입으로 실행하지 않았다.
- **Windows Sandbox 실행(`WindowsSandbox.exe`)은 전혀 수행하지 않음.** 이유: Windows Sandbox 최적 기능 활성화와 관리자 elevation이 필요하고, 실제 offline package ZIP(위 두 gap 때문에 아직 존재하지 않음)이 선행 조건이다. `scripts/sandbox/run_offline_package_smoke.ps1`/`guest_bootstrap.ps1`/`AeroOnePackageSmoke.wsb.template`은 전부 작성 완료했고 PowerShell AST 파서 + XML 파서로 구문 오류 0건만 확인했다. `validate_sandbox_launch_options()`(networking/interactive-pause/timeout 경계)는 pytest로 별도 검증했으므로, 실행 시 사용될 정책 판정 로직 자체는 synthetic 입력 기준으로 GREEN이다.
- 이에 따라 "guest가 verifier 통과 후 Python/Node silent installer exit 0, PATH refresh, exact versions, 무인 setup/start/health/frontend/login/empty-NSA/stop을 atomic receipt로 남긴다"는 시나리오는 **로직 상으로 구현되어 있으나 이 sandbox에서 실행 증적은 없다.** 실 installer 바이너리 반입과 Windows Sandbox 기능이 가능한 환경(리더의 워크스테이션)에서 `scripts/build_offline_package.ps1` → `scripts/sandbox/run_offline_package_smoke.ps1` 순서로 실행해 `receipt.json`을 확인하는 것을 후속 검증으로 남긴다.
- 프로젝트 전역 pytest/ruff/basedpyright/포매터 실행은 하지 않음(과제 지시에 따라 focused 테스트만 실행; 전체 검증은 리더 담당). basedpyright는 신규 Python 파일에 한해 0 errors를 확인했다.
- 커밋/push는 하지 않음.
