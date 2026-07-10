# 단계 26 — 자격 증명 사고 대응 회전 강화

## 배경

설치 스크립트 재실행은 환경 파일의 JWT/admin 초기값을 다시 만들 수 있지만 기존 DB 전체 사용자의 비밀번호, session version, live session, 복구 journal을 하나의 원자적 사고 단위로 처리하지 않습니다. 자격 노출 대응을 setup-only 절차로 안내하면 환경 파일과 DB 자격이 갈라지고 old session이 남을 수 있어 별도 회전 경로가 필요했습니다.

## 구현 결과

- `scripts/rotate_aeroone_credentials.ps1`을 고정 production provenance와 강한 TestMode nonce 경계로 제한했습니다.
- canonical SQLite physical path, reparse/hardlink, exact env allow-list, exact DACL을 mutation 전에 검증합니다.
- 전체 사용자 비밀번호 변경, session version 증가, session 삭제, ledger/audit를 `BEGIN IMMEDIATE` 단일 트랜잭션으로 처리합니다.
- WAL-safe online backup을 목적별 DPAPI envelope로 보존하고 rotation ID/DB ID/size/SHA-256에 묶었습니다.
- current/previous journal에 strict Pydantic schema, sequence, canonical checksum과 모든 artifact/env binding을 기록했습니다.
- quarantine는 cross-volume-safe copy/flush/readback/finalize/verify/source-delete 순서를 사용합니다.
- 실제 process kill seam과 reconciliation을 추가해 partial temp, env 이동, credential 이동, torn current를 재개합니다.
- DB restore 후 exact confirmation을 거쳐 old completed root를 `history/<rotation-id>`로 원자 보존하고 새 rotation ID로 재회전하는 2단계 계약을 추가했습니다.
- production credential bundle을 secure root 내부로 옮겨 journal/recovery/quarantine와 함께 한 번의 directory archive에 포함했습니다.

## 보안 정책 정정

- setup 재실행은 설치/시드 절차이며 자격 증명 사고 대응 회전의 대체 수단이 아닙니다.
- inactive 계정은 회전으로 활성화하지 않습니다. 로그인 응답은 계정 상태 비공개 정책에 따라 기존 401을 유지하며 403으로 바꾸지 않습니다.
- completed/history 산출물은 자동 삭제하지 않습니다. retention 이후 삭제 책임은 독립 백업·감사·법적 보존을 확인한 운영 보안 책임자에게 있습니다.

## 구조

PowerShell은 Runtime, PathSecurity, Security, SecureIO, Crypto, Bootstrap, Environment, Journal, Reconciliation, Quarantine, Archive, ProcessLock 모듈로 분리했습니다. Python은 strict command boundary와 handler, contracts, fingerprints, audit, ledger, recovery, artifact schema로 분리했습니다.

## 검증

- Task3 focused: `56 passed, 3 warnings` (기존 비대상 Pydantic deprecation 3건)
- ruff: PASS
- production changed Python basedpyright: `0 errors, 0 warnings, 0 notes`
- 모든 PowerShell AST parse: PASS
- PowerShell 함수 50 LOC 초과: 0
- 실제 새 admin login 200 / old restored admin login 401

상세 운영 절차는 [`../runbook/credential-rotation.md`](../runbook/credential-rotation.md)를 따릅니다.
