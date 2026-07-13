# Task 7 — 내부 데이터 bundle 시스템 (production 데이터 배포 경로와 구조적으로 분리)

## 결과

- 상태: Python 경계 검증 계층 완료(GREEN) / PowerShell CMS 계층 구현 완료(정적 검증만)
- 실제 운영 환경 파일, DB, `%USERPROFILE%\AeroOne-secure`, `C:\ProgramData\AeroOne`, 실 cert store(`Cert:\CurrentUser\My`, `Cert:\LocalMachine\My`), 실 레지스트리: 변경하지 않음
- 신규 crypto dependency: 0개. PowerShell 계층은 `System.Security.Cryptography.Pkcs`(SignedCms/EnvelopedCms, .NET in-box, `Add-Type -AssemblyName System.Security`로 로드 확인)만 사용
- 비밀값, 실제 파일명 원문 출력: 0건

## 구현 계약

- `packaging/internal-data-approval.schema.json`: 11개 필드 정확 매칭, `additionalProperties: false`, `allowed_roots` enum `{newsletter, civil_aircraft, document, nsa}`, TTL≤24h/mixed-roots 규칙은 설명(description)에 명시하고 실제 강제는 strict parser + pydantic + business rule에서 수행.
- `packaging/internal-data-trust.schema.json`: `signers[].eku_oid` const Document Signing OID, `recipients[].eku_oid` const Email Protection OID, `additionalProperties: false`.
- `packaging/internal-data-envelope.schema.json`: outer `content_encryption_oid` const AES-256-CBC OID, inner `entries`에 `approval.json`/`inventory.json` 포함 강제.
- `backend/app/operations/internal_data_bundle_contracts.py`: 경계/정책 결정을 전담하는 순수 Python 계층.
  - `InternalDataBundleErrorCode`(28개 세분화 코드), `InternalDataBundleError`.
  - `ApprovalRecord`/`TrustPolicy`/`TrustSigner`/`TrustRecipient` pydantic 모델(`frozen=True, extra="forbid"`).
  - `parse_strict_json_object()`: UTF-8 strict decode + `object_pairs_hook`으로 duplicate key 거부(`ConvertFrom-Json` 단독 금지 요구사항의 실체).
  - `parse_approval_strict()`: schema_version/TTL(≤24h)/expires>issued/발효창/mixed-roots/include_nsa 정합성/unknown-root를 모두 fail-closed로 검증.
  - `validate_signers()`: normal={data_owner,security_officer}, nsa={nsa_data_owner,security_officer} 정확한 role 집합 + **서로 다른 thumbprint 강제**(동일 signer dual-role 거부) + EKU/서명/체인/유효기간 검증.
  - `validate_recipient()`: thumbprint/environment/EKU/private-key 존재/유효기간 검증.
  - `validate_aes_oid()`: AES-256-CBC OID 정확 일치만 허용.
  - `parse_trust_policy()`: 레지스트리 pin(`pinned_sha256`) 부재/불일치 시 fail-closed, policy 자체 만료 검증.
  - `validate_approval_against_trust_policy()`: policy `max_approval_ttl_hours`/`allowed_roots` 상한 강제.
  - `validate_trust_policy_acl()`: SYSTEM+Administrators+authorized SID **정확히 3개**, 상속 비활성, 전부 Read-only만 허용(추가 ACE/쓰기 권한/상속 ACE/미승인 SID는 모두 거부).
  - `validate_target_root()`: `..`/`.`/절대경로/드라이브문자 포함 시 path-traversal 거부, top-level이 `allowed_roots` 밖이면 별도 코드로 거부.
  - `validate_inventory()`: SHA-256 재계산 후 approval의 `source_inventory_sha256`과 불일치 시 거부.
  - `validate_envelope_entries()`: 내부 ZIP entry가 정확히 `approval.json`+`inventory.json`+2개 `.p7s`+승인된 root 하위 content만 포함하는지 강제.
  - CLI: 기본 모드(stdin raw approval bytes → strict parse, exit 0/1)와 `--rpc` 모드(JSON 요청 dispatch로 위 모든 검증 함수를 노출) 제공. PowerShell 계층은 이 CLI를 통해서만 경계 판정을 내리며, 자체적으로 정책 로직을 재구현하지 않는다.
- PowerShell CMS 계층(5개 스크립트, 신규):
  - `scripts/New-AeroOneInternalApproval.ps1`: approval을 정확한 필드 순서의 raw UTF-8 bytes로 생성한 뒤, 파일로 쓰기 전에 Python strict parser로 **왕복 검증**(수용 게이트가 `ConvertFrom-Json` 단독이 아님을 실체화).
  - `scripts/Sign-AeroOneInternalApproval.ps1`: 단일 role/단일 signer가 raw approval bytes에 대해 detached `SignedCms`(SHA-256, `X509IncludeOption.EndCertOnly`)를 1개 생성. Document Signing EKU/유효기간/체인(`RevocationMode=NoCheck`, `NoFlag`) 검증 후에만 서명. private key는 이미 발급된 인증서의 것만 사용(신규 생성 없음).
  - `scripts/Install-AeroOneInternalTrust.ps1`: trust policy가 참조하는 모든 signer/recipient thumbprint가 **이미 설치된** 인증서인지만 검증(cert/key 생성 0). 정책 파일을 owner=Administrators, 상속 비활성, SYSTEM+Administrators+authorized SID 3-ACE만으로 배포하고 SHA-256을 레지스트리에 고정.
  - `scripts/build_internal_data_bundle.ps1`: 이미 생성된 2개 `.p7s`만 검증(private signing key 미사용, 0회 서명). approval 파싱/trust policy pin 검증/dual-role 검증/recipient 검증/inventory 검증/envelope entry 검증을 모두 Python `--rpc`에 위임. inner ZIP 조립 후 `EnvelopedCms`로 AES-256-CBC(OID `2.16.840.1.101.3.4.1.42`) 암호화. public-data flag 미설정, repo/dist/GitHub 출력 경로 미사용.
  - `scripts/Import-AeroOneInternalDataBundle.ps1`: decrypt → AES OID 확인 → approval 파싱 → trust policy pin → 서명 2건(dual-role) → recipient → inventory → envelope entry 순서로 **전부** 사전검증 완료 후에만 staging 시작. maintenance gate(`-MaintenanceGateActive`) 없이는 중단. same-volume staging 디렉터리(`TargetRoot` 부모 아래) 생성 → durable journal(`staged`→`swapped`→`committed`) 기록 → old-root backup rename → staged rename 원자적 교체 → 실패 시 journal 기반 rollback(백업 복원). 재시작 시 `swapped`에서 멈춘 journal을 감지해 gate 보유 시에만 복구.

## TDD 및 자동 검증

- RED: 최초 pydantic 모델에 남긴 `strict=True`가 JSON에서 읽은 ISO-8601 문자열→`datetime`, `list`→`tuple` 코어션을 거부해 68개 중 25개가 `ValidationError`(schema-violation)로 실패. 컨테이너/구조 필드의 `strict=True`를 제거(개별 필드 `pattern`/`min_length` 제약은 유지)하여 해결.
- RED: `validate_target_root`가 `PurePosixPath`의 자동 `.` 정규화로 `civil_aircraft/./file.json`을 traversal로 잡지 못함 → `PurePosixPath` 제거하고 raw 컴포넌트 분리 후 `.`/`..` 명시 거부로 재작성.
- RED: fixture thumbprint가 38자(40자 hex 요구)여서 owner/security/nsa_owner 서명 관련 5개 케이스가 schema-violation으로 실패 → 40자 hex로 교정.
- GREEN: `cd backend && PYTHONPATH=. "D:/Chanil_Park/Project/Programming/AeroOne/backend/.venv/Scripts/python.exe" -m pytest tests/unit/test_internal_data_bundle.py -q -p no:cacheprovider` → **68 passed**, 실패 0.
- RPC 계약 스모크: `echo '{"action":"validate_aes_oid","oid":"2.16.840.1.101.3.4.1.42"}' | python -m app.operations.internal_data_bundle_contracts --rpc` → `{"status": "ok"}`, exit 0. 잘못된 OID 입력 시 `aes-oid-mismatch`, exit 1 확인.
- PowerShell AST 파서로 5개 신규 `.ps1` 전부 구문 오류 0건 확인(`[System.Management.Automation.Language.Parser]::ParseFile`).
- `Add-Type -AssemblyName System.Security; [System.Security.Cryptography.Pkcs.SignedCms]` 로드 성공 확인(신규 crypto 패키지 불필요, in-box assembly만 사용).

## 의도적으로 수행하지 않은 항목 (gap)

- PowerShell 스크립트의 **실제 SignedCms/EnvelopedCms 실행(라이브 서명/암호화/복호화)은 이 sandbox에서 수행하지 않음**. 이유: `New-SelfSignedCertificate`는 PowerShell 5.1에서 `Cert:\CurrentUser\My`(실 스토어) 외의 위치에는 인증서를 생성할 수 없고(`Cannot find path ... AeroOneInternalDataTest` → 스토어를 미리 만들어도 `New-SelfSignedCertificate`는 "A new certificate can only be installed into MY store" 오류로 거부), .NET Framework(PS 5.1 런타임)에는 `CertificateRequest` API가 in-box로 없어 순수 격리 스토어에 self-signed cert를 직접 생성할 방법이 없음을 실측 확인. 이 상태에서 라이브 크립토 통합 테스트를 강행하면 반드시 실 `Cert:\CurrentUser\My`를 (일시적으로라도) 건드리게 되어 "실제 인증서를 이 환경에 설치하지 말 것" 제약을 위반한다. 따라서 라이브 크립토 실행은 생략하고, 정적 구문 검증 + Python 경계 계층(전체 정책 판정 로직)의 pytest GREEN으로 대체했다.
- 이에 따라 "Happy: distinct owner/security/recipient cert로 normal/NSA `.p7m` build/import → exit 0" 시나리오는 **로직 상으로 구현되어 있으나 이 sandbox에서 실행 증적은 없음**. 실 인증서 provisioning이 가능한 환경(리더의 워크스테이션, 격리된 CI)에서 `Sign-AeroOneInternalApproval.ps1` → `build_internal_data_bundle.ps1` → `Import-AeroOneInternalDataBundle.ps1` 순서로 실행해 exit code/hash를 확인하는 것을 후속 검증으로 남긴다.
- 실제 trust provisioning, real bundle 생성/배포는 범위 밖(지시사항대로 미수행).
- 프로젝트 전역 pytest/ruff/basedpyright/포매터 실행은 하지 않음(과제 지시에 따라 focused 테스트만 실행).
- 커밋/push는 하지 않음.
