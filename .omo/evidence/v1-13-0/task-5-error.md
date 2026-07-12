# Task 5 — 실패 경로 증적

## 기대 실패 검증 (parameterized, synthetic fixture, 실제 파일명/경로 미기재)

`test_verify_pre_stage_is_fail_closed` / `test_validate_raw_entries_rejects_unsafe_paths` /
`test_verify_post_zip_rejects_*` 각 케이스는 synthetic `tmp_path` fixture 위에서
단 하나의 위반만 주입한 뒤 `PackagePolicyError`가 발생하고 코드가 정확히
일치함을 확인한다. 각 케이스는 non-zero(예외 raise)로 종료하며 evidence에는
카테고리 코드만 남긴다.

| 위반 유형 | redacted 코드 | 검증 위치 |
| --- | --- | --- |
| root 밖으로 resolve되는 path traversal | `path-traversal` | raw-entry 검증 |
| 리터럴 `..` 세그먼트 | `path-traversal` | raw-entry 검증 |
| symlink entry | `symlink-entry` | raw-entry 검증 |
| 대소문자만 다른 중복 경로 | `duplicate-entry` | raw-entry 검증 |
| 실제 `.env` 파일(허용 목록의 `.env.example` 패턴은 매치 안 됨을 별도 확인) | `forbidden-env-secret` | pre-stage 정책 |
| DB 파일(`backend/data/**`, `*.db`) | `forbidden-database` | pre-stage 정책 |
| storage 런타임 파일(`storage/**`) | `forbidden-storage-runtime` | pre-stage 정책 |
| manifest 항목 삭제(실제 파일은 남아 있음, extra) | `manifest-extra-entry` | manifest 1:1 |
| manifest 중복 항목(동일 path 2회) | `duplicate-entry` | manifest 1:1 |
| installer 파일을 교체하고 manifest hash도 함께 위조(정책 hash와만 불일치) | `installer-hash-mismatch` | installer trust |
| installer Authenticode thumbprint 불일치 | `installer-thumbprint-mismatch` | installer trust |
| installer Authenticode subject 불일치 | `installer-subject-mismatch` | installer trust |
| installer 서명 상태가 `Valid`가 아님(`NotSigned`) | `installer-signature-invalid` | installer trust |
| allow-list 밖 신규 top-level 디렉터리 | `toplevel-not-allowed` | pre-stage 정책 |
| post-ZIP entry 이름의 path traversal(`../`) | `path-traversal` | post-ZIP (extract 없음) |
| post-ZIP에서 pre-stage 서명 검증 시점과 entry 바이트가 달라짐(digest drift) | `post-zip-digest-mismatch` | post-ZIP (extract 없음) |
| post-ZIP이 manifest 대비 entry 누락 | `manifest-missing-entry` | post-ZIP (extract 없음) |

모든 케이스는 `pytest.raises(PackagePolicyError)`로 예외를 강제하며,
`excinfo.value.code`가 표에 명시한 코드와 정확히 일치할 때만 GREEN으로 판정한다.
deny-list 단독 매칭만으로 PASS하는 경로는 없다 — 각 fail-closed 케이스는
allow-list 판정, manifest 1:1, installer 서명 cross-check 중 정확히 해당하는
계층에서 걸러진다.

## 구현 중 발견하고 해결한 실패 (RED → GREEN)

- 최초 fixture 작성 직후 `PolicyDocument`/`ForbiddenCategory`/`PackageManifest`에
  남겨둔 `strict=True`가 JSON에서 읽은 `list`를 `tuple` 필드로 코어션하는 것을
  거부해 21개 중 18개가 `ValidationError`로 실패했다. 컨테이너 보유 모델의
  `strict=True`를 제거해(필드 단위 `sha256`/`thumbprint` 패턴 검증은 유지) 해결했다.
- 최초 fixture의 thumbprint 리터럴이 38자였고(40자 hex 요구) `RequiredInstaller`
  검증에서 즉시 실패했다. 40자 hex fixture 값으로 교정했다.
- 대소문자 중복 raw-entry 케이스의 `resolved` 필드가 실제 `root_resolved`
  기준으로 정규화되지 않아 traversal 체크가 duplicate 체크보다 먼저 걸려
  의도한 코드(`duplicate-entry`)가 아닌 `path-traversal`로 실패했다.
  fixture 빌더를 `root_resolved` 상대 경로로 재구성해 해결했다.

## 미해결 오류

- 없음 (focused 테스트: 21 passed)

## 민감정보 원칙

- 본 증적에는 암호, JWT 비밀, DB 원문, 실제 `.env` 파일명/경로, DPAPI payload,
  실제 installer 바이너리 또는 실제 운영 데이터가 포함되지 않는다. 모든
  실패 케이스는 synthetic `tmp_path` fixture 위에서 재현했다.
