# Task 5 — 공개 오프라인 패키지 fail-closed allow-list 정책 + pre/post ZIP verifier

## 결과

- 상태: 완료
- 실제 운영 환경 파일, DB, `%USERPROFILE%\AeroOne-secure`: 변경하지 않음
- 검증 대상: pytest `tmp_path` 임시 작업공간에 생성한 synthetic 스테이징 트리·manifest·ZIP
- 비밀값, 실제 파일명, 실제 경로 원문 출력: 0건 (evidence에는 카테고리/코드만 기록)

## 구현 계약

- `packaging/installer-policy.json`: release/QA profile, 필수 installer 정확히 2개(Python 3.12.7 amd64, Node 20.18.0 x64)의 filename/SHA-256/Authenticode thumbprint/subject를 정확한 값으로 고정. 공개 ZIP top-level allow-list(코드/런타임 디렉터리만)와 5개 forbidden 카테고리(env-secret, database, storage-runtime, agent-state, dev-artifact)를 패턴/예외로 명시.
- `backend/app/operations/package_policy_contracts.py`: `PackagePolicyErrorCode` StrEnum(20개 세분화된 코드), `PackagePolicyError`, `PolicyDocument`/`ForbiddenCategory`/`RequiredInstaller`/`PackageManifest`/`ManifestEntry` pydantic 모델, `AuthenticodeSignatureInfo`/`ManifestProvenance`/`PreStageResult`/`PostZipResult` 데이터클래스.
- `backend/app/operations/package_policy_verifier.py`: 정책/manifest/entry 검증 로직(글롭 매처, path 안전성, allow-list, manifest 1:1, hash, provenance, installer trust)과 `verify_pre_stage()`/`verify_post_zip()` 오케스트레이터.
- `packaging/verify_offline_package.py`: Python CLI. 정책 위반 시 stdout에 `{"ok": false, "code": "<redacted-category-code>"}`만 출력하고 non-zero exit — 파일명/경로 미노출.
- `scripts/packaging/Verify-OfflinePackage.psm1`: OS 계층(Authenticode `Get-AuthenticodeSignature`, 파일 존재)만 담당하고 정책 판정은 Python CLI에 위임하는 `Invoke-OfflinePackagePreStageVerification`/`Invoke-OfflinePackagePostZipVerification`.

## 검증 항목 (pre-stage / post-ZIP 공통, path 기반)

- path traversal(실제 root 밖으로 resolve, 리터럴 `..` 세그먼트), symlink, 대소문자 무시 중복 entry 거부
- manifest ↔ 실제 entry 정확히 1:1 (누락 0, 추가 0)
- 각 manifest entry의 hash와 origin/tag/commit/policy(provenance) 일치
- 필수 installer 2종의 정확한 filename/SHA-256/Authenticode Valid 서명/thumbprint/subject
- allow-list 밖 top-level 자동 거부(신규 top-level 자동 허용 없음), 실제 `.env*`(`.env.example` 예외 패턴은 실제 `.env`에 매치되지 않음을 별도 검증) 및 DB/storage/agent-state/dev-artifact 카테고리 거부
- post-ZIP: archive를 extract하지 않음. entry는 `zipfile.ZipFile.open()` 스트림으로만 SHA-256을 계산해 pre-stage에서 Valid 서명으로 검증된 digest와 path 기준으로 비교(디스크에 산출물 미기록)

## TDD 및 자동 검증

- RED: 최초 fixture 작성 직후 pydantic strict 컨테이너 타입 불일치(list→tuple strict 코어션 거부)와 fixture thumbprint 길이 오류(38자)로 21개 중 18개 실패 확인 → contracts의 컨테이너 필드 strict 제거, fixture thumbprint를 40자 hex로 교정, 대소문자 중복 raw-entry 테스트의 `resolved` 경로를 실제 `root_resolved` 하위로 재구성하여 GREEN 전환.
- GREEN: `PYTHONPATH=. python -m pytest tests/unit/test_package_policy_verifier.py tests/unit/test_installer_policy_json.py -q -p no:cacheprovider` → **21 passed**, 실패 0.
- CLI 계약 스모크: `packaging/verify_offline_package.py pre-stage`/`post-zip`을 synthetic tmp fixture(별도 임시 policy/manifest/installer, 실제 저장소 자산과 무관)로 subprocess 호출해 `{"ok": true, ...}` 및 exit code 0 확인.
- PowerShell AST 파서로 `scripts/packaging/Verify-OfflinePackage.psm1` 구문 오류 0건 확인(`[System.Management.Automation.Language.Parser]::ParseFile`).

## 의도적으로 수행하지 않은 항목

- 실제 Python/Node 설치 파일에 대한 실제 Authenticode 서명 검증은 수행하지 않음(오프라인 환경에 실제 installer 바이너리가 없음). `Get-AuthenticodeSignatureInfo`는 실제 파일에 대해서만 호출되는 얇은 OS-계층 래퍼로 구현했고, pytest에서는 이 래퍼가 반환할 형태를 시뮬레이션하는 `AuthenticodeSignatureInfo`를 주입해 Python 쪽 cross-check 로직(Valid 여부/thumbprint/subject 일치)을 검증했다. 실제 installer 바이너리로의 end-to-end Authenticode 검증은 리더의 실제 배포 파이프라인에서 별도로 수행되어야 한다.
- 프로젝트 전역 pytest/ruff/basedpyright/포매터 실행은 하지 않음(과제 지시에 따라 focused 테스트만 실행; 전체 검증은 리더 담당).
- 커밋/push는 하지 않음.
