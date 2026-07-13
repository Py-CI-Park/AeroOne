# Task 7 — 실패 경로 증적

## 기대 실패 검증 (synthetic fixture, 실제 파일명/경로/비밀값 미기재)

모든 케이스는 `pytest.raises(InternalDataBundleError)`로 예외를 강제하며
`excinfo.value.code`가 표에 명시한 코드와 정확히 일치할 때만 GREEN으로 판정한다.
비교/암호 검증이 필요한 실패(서명 bit-flip, 동일 signer dual-role, 잘못된 EKU,
recipient private key 부재, cert 유효기간)는 PowerShell CMS 계층이 추출할
evidence(`SignatureEvidence`/`RecipientEvidence`)를 synthetic하게 주입해 Python
경계 계층의 판정 로직만 검증한다(실제 인증서/서명 불필요).

| 위반 유형 | 코드 | 검증 위치 |
| --- | --- | --- |
| duplicate JSON key | `duplicate-json-key` | strict parser |
| 잘못된 UTF-8 | `invalid-json` | strict parser |
| 배열/비-object root | `invalid-json` | strict parser |
| 잘림(ciphertext bit-flip 후 평문 손상 대리) | `invalid-json` | strict parser |
| approval에 미정의 필드 추가 | `schema-violation` | pydantic `extra=forbid` |
| approval 필수 필드 누락 | `schema-violation` | pydantic |
| approval 내 duplicate key | `duplicate-json-key` | strict parser |
| TTL > 24h | `ttl-exceeded` | `parse_approval_strict` |
| TTL 정확히 24h | (성공) | `parse_approval_strict` |
| expires_at ≤ issued_at | `expires-before-issued` | `parse_approval_strict` |
| approval 만료 후 사용(expired) | `approval-expired` | `parse_approval_strict` |
| approval 발효 전 사용(future) | `approval-not-yet-valid` | `parse_approval_strict` |
| `nsa` + 다른 root 혼합 | `mixed-roots` | `parse_approval_strict` |
| `include_nsa=true`인데 root가 nsa 아님 | `roots-nsa-flag-mismatch` | `parse_approval_strict` |
| root가 `{nsa}`인데 `include_nsa=false` | `roots-nsa-flag-mismatch` | `parse_approval_strict` |
| 정의되지 않은 root 문자열 | `unknown-root` | `parse_approval_strict` |
| `allowed_roots` 중복 항목 | `schema-violation` | pydantic validator |
| thumbprint 형식 불일치 | `schema-violation` | pydantic `pattern` |
| 동일 signer(동일 thumbprint) dual-role | `signer-same-thumbprint` | `validate_signers` |
| NSA bundle에 normal-owner(`data_owner`) 서명 | `signer-role-set-mismatch` | `validate_signers` |
| signer role 집합 불일치 | `signer-role-set-mismatch` | `validate_signers` |
| 서명 2개가 아님(1개만) | `signer-role-set-mismatch` | `validate_signers` |
| 서명 bit-flip(`signature_valid=false`) | `signature-invalid` | `validate_signers` |
| 체인 검증 실패 | `chain-invalid` | `validate_signers` |
| signer 인증서 wrong EKU | `eku-mismatch` | `validate_signers` |
| signer 인증서 만료 | `cert-expired` | `validate_signers` |
| signer 인증서 발효 전 | `cert-not-yet-valid` | `validate_signers` |
| recipient thumbprint 불일치 | `recipient-mismatch` | `validate_recipient` |
| recipient environment 불일치 | `recipient-environment-mismatch` | `validate_recipient` |
| recipient private key 부재 | `recipient-private-key-missing` | `validate_recipient` |
| recipient 인증서 wrong EKU | `eku-mismatch` | `validate_recipient` |
| recipient 인증서 만료 | `cert-expired` | `validate_recipient` |
| AES 알고리즘 OID가 AES-256-CBC 아님 | `aes-oid-mismatch` | `validate_aes_oid` |
| 레지스트리 pin 부재 | `trust-policy-digest-absent` | `parse_trust_policy` |
| 레지스트리 pin과 실제 policy digest 불일치 | `trust-policy-digest-mismatch` | `parse_trust_policy` |
| trust policy 만료 | `trust-policy-expired` | `parse_trust_policy` |
| trust policy에 미정의 필드 추가 | `schema-violation` | pydantic |
| approval root가 policy `allowed_roots`의 subset 아님(mixed roots at policy level) | `allowed-roots-not-subset` | `validate_approval_against_trust_policy` |
| approval TTL이 policy `max_approval_ttl_hours` 초과 | `ttl-exceeded` | `validate_approval_against_trust_policy` |
| ACL에 승인되지 않은 추가 ACE(broad ACL, 예: Everyone) | `acl-mismatch` | `validate_trust_policy_acl` |
| ACL에 미승인 SID | `acl-mismatch` | `validate_trust_policy_acl` |
| ACL rights가 Read가 아님(쓰기 권한 포함) | `acl-mismatch` | `validate_trust_policy_acl` |
| ACE가 상속됨 | `acl-mismatch` | `validate_trust_policy_acl` |
| 상속이 비활성화되지 않음 | `acl-mismatch` | `validate_trust_policy_acl` |
| path traversal(`../`, `./`, 절대경로, 드라이브 문자) | `path-traversal` | `validate_target_root` |
| 승인되지 않은 root로의 경로 | `path-escapes-allowed-roots` | `validate_target_root` |
| inventory 변조(hash 불일치) | `inventory-hash-mismatch` | `validate_inventory` |
| envelope에 inventory.json 누락 | `envelope-entry-mismatch` | `validate_envelope_entries` |
| envelope 서명 파일이 정확히 2개가 아님 | `signer-role-set-mismatch` | `validate_envelope_entries` |
| envelope content가 allowed_roots 밖 | `path-escapes-allowed-roots` | `validate_envelope_entries` |
| envelope content에 path traversal | `path-traversal` | `validate_envelope_entries` |
| envelope entry 이름 중복 | `envelope-entry-mismatch` | `validate_envelope_entries` |

## 구현 중 발견하고 해결한 실패 (RED → GREEN)

- 최초 `ApprovalRecord`/`TrustPolicy`/`TrustSigner`/`TrustRecipient`에 남긴
  `strict=True`가 JSON에서 읽은 ISO-8601 문자열을 `datetime`으로, `list`를
  `tuple`로 코어션하는 것을 거부해 68개 중 25개가 `schema-violation`으로
  실패했다. 컨테이너/날짜 필드를 포함한 모델의 `strict=True`를 제거하고
  (개별 필드의 `pattern`/`min_length`/`Field` 제약은 유지) 해결했다.
- `validate_target_root`가 `pathlib.PurePosixPath`를 사용했는데, `PurePosixPath`가
  `./` 세그먼트를 자동으로 정규화(제거)해 `civil_aircraft/./file.json`이
  traversal로 검출되지 않고 `DID NOT RAISE`로 실패했다. `PurePosixPath`를
  제거하고 raw 문자열을 `/`로 분리해 각 컴포넌트를 `.`/`..`와 명시 비교하는
  방식으로 재작성해 해결했다.
- fixture의 owner/security/nsa_owner thumbprint가 38자였다(40자 hex 요구).
  관련 서명/trust-policy 케이스 5개가 `schema-violation`으로 실패했다.
  40자 hex 리터럴로 교정해 해결했다.

## 미해결 오류

- 없음 (focused 테스트: `backend/tests/unit/test_internal_data_bundle.py` 68 passed, 0 failed)

## 민감정보 원칙

- 본 증적에는 암호, JWT 비밀, DB 원문, 실제 `.env` 파일명/경로, DPAPI payload,
  실제 인증서/thumbprint, 실제 운영 데이터가 포함되지 않는다. 모든 fixture는
  synthetic literal(예: `1111...AA` 반복 패턴 thumbprint, `req-0001` 등)이다.
- PowerShell CMS 계층은 이 sandbox에서 실제 인증서로 실행하지 않았으므로
  라이브 서명/암호화 스택 트레이스 등 민감할 수 있는 실행 로그도 존재하지
  않는다.
