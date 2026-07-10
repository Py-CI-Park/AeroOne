# 단계 26 — 자격 증명 사고 대응 회전 강화

## 배경

설치 스크립트 재실행은 환경 파일의 JWT/admin 초기값을 다시 만들 수 있지만 기존 DB 전체 사용자의 비밀번호, session version, live session, 복구 journal을 하나의 원자적 사고 단위로 처리하지 않습니다. 자격 노출 대응을 setup-only 절차로 안내하면 환경 파일과 DB 자격이 갈라지고 old session이 남을 수 있어 별도 회전 경로가 필요했습니다.

## 구현 결과

- `scripts/rotate_aeroone_credentials.ps1`을 고정 production provenance와 강한 TestMode nonce 경계로 제한했습니다.
- 알려진 AeroOne Windows 서비스와 root/backend 환경의 backend/frontend listener가 남아 있으면 mutation 전에 fail closed 합니다. 자동 종료는 하지 않습니다.
- canonical SQLite physical path, reparse/hardlink, exact env allow-list, exact DACL을 mutation 전에 검증합니다.
- 전체 사용자 비밀번호 변경, session version 증가, session 삭제, ledger/audit를 `BEGIN IMMEDIATE` 단일 트랜잭션으로 처리합니다. recovery logical snapshot 준비부터 commit까지 같은 연결의 writer lock을 유지합니다.
- WAL-aware logical snapshot을 목적별 DPAPI envelope로 보존하고 rotation ID/DB ID/size/SHA-256에 묶었습니다. SQLite schema cookie와 file change counter만 canonicalize하고 deserialize+integrity check를 다시 수행해 독립 일반 백업의 동일 logical state를 exact confirmation 할 수 있습니다.
- current/previous journal에 strict Pydantic schema, sequence, canonical checksum과 모든 artifact/env binding을 기록했습니다.
- quarantine는 cross-volume-safe copy/flush/readback/finalize/verify/source-delete 순서를 사용하며, manifest도 exact schema·checksum·rotation/DB journal binding을 검증합니다.
- 실제 process kill seam과 reconciliation을 추가해 partial temp, env 이동, credential 이동, torn current를 재개합니다.
- DB restore 후 exact confirmation을 거쳐 old completed root를 `history/<rotation-id>`로 원자 보존하고 새 rotation ID로 재회전하는 2단계 계약을 추가했습니다.
- production credential bundle을 secure root 내부로 옮겨 journal/recovery/quarantine와 함께 한 번의 directory archive에 포함했습니다.
- `scripts/view_aeroone_credentials.ps1`은 current Windows SID, 고정 secure path, single-link/exact ACL, DPAPI purpose, strict bundle schema를 검증합니다. WPF에서 계정 선택·기본 마스킹·명시적 reveal/copy를 제공하고 owned clipboard만 30초 뒤 삭제합니다. `-ValidateOnly`는 WPF를 열거나 평문을 출력·저장하지 않습니다.
- Python DPAPI native output buffer는 성공과 copy 실패 경로 모두 `RtlZeroMemory` 후 `LocalFree` 순서로 정리합니다. bootstrap 소유 파일도 읽기·삭제 전에 exact ACL을 확인합니다.

## 보안 정책 정정

- `1.12.2` Release/ZIP은 철회했으며 신규 설치·재배포에 사용할 수 없습니다. 정식 `1.13.0` asset이 게시되기 전에는 새 폐쇄망 반입을 보류합니다.
- setup 재실행은 설치/시드 절차이며 자격 증명 사고 대응 회전의 대체 수단이 아닙니다.
- inactive 계정은 회전으로 활성화하지 않습니다. 로그인 응답은 계정 상태 비공개 정책에 따라 기존 401을 유지하며 403으로 바꾸지 않습니다.
- completed/history 산출물은 자동 삭제하지 않습니다. retention 이후 삭제 책임은 독립 백업·감사·법적 보존을 확인한 운영 보안 책임자에게 있습니다.

## 구조

PowerShell은 Runtime, PathSecurity, Security, SecureIO, Crypto, Bootstrap, Environment, Journal, Reconciliation, Quarantine, Archive, ProcessLock, ServicePreflight, DatabaseTransaction, CredentialViewer 모듈로 분리했습니다. Python은 strict command boundary와 handler, contracts, fingerprints, audit, ledger, streaming transaction, recovery, artifact schema, native DPAPI 경계로 분리했습니다.

## 검증

- 최종 수치: backend full **347 passed**, credential focused **79 passed**, frontend **313 passed / 66 files**.
- 현재 증적: 실제 listener 차단, recovery→commit 연속 writer lock, precommit rollback/resume exactly-once, ordinary backup restore→archive→fresh rotation, old 401/new 200, actual process-kill 재개, WPF `-ValidateOnly`, DPAPI native zeroize.
- 정적/빌드 gate: production Python ruff·basedpyright·compileall, 모든 PowerShell AST, frontend `tsc --noEmit`·`next build`, 문서 링크·버전 정합성.
- 미검증: 실제 WPF 창 시각 조작과 web 브라우저 smoke. 이번 단계는 web UI를 변경하지 않았고 운영 경로는 실행하지 않았습니다.
- 실제 운영 `.env`, `backend\.env`, `backend\data\aeroone.db`와 production secure root는 개발 검증에서 회전하지 않습니다.

상세 운영 절차는 [`../runbook/credential-rotation.md`](../runbook/credential-rotation.md)를 따릅니다.
