# 자격 증명 사고 대응 회전 런북

이 런북은 자격 증명 노출이 의심될 때 AeroOne의 JWT, 전체 사용자 비밀번호, 세션을 하나의 사고 단위로 회전하는 절차입니다. `setup.bat`과 `setup_offline.bat`은 설치·의존성·환경 파일·초기 시드를 준비하는 도구이지, 기존 DB의 모든 사용자 비밀번호와 세션을 원자적으로 회전하는 사고 대응 도구가 아닙니다.

> [!CAUTION]
> `1.12.2` Release/ZIP은 철회되었습니다. 신규 설치나 재배포에 사용하지 말고, 이미 반입한 환경은 서비스를 중지한 뒤 정식 `1.13.0`으로 교체하고 이 런북의 전체 회전을 수행합니다. `1.13.0-dev` 중간 산출물로 운영 회전을 실행하지 않습니다.

## 1. 실행 전 조건

1. AeroOne backend/frontend를 중지합니다. 실행 중인 서비스를 그대로 둔 채 회전하지 않습니다. 도구도 알려진 `AeroOne`, `AeroOneBackend`, `AeroOneFrontend` Windows 서비스와 root/backend 환경의 `BACKEND_PORT`, `FRONTEND_PORT` listener를 확인하고 남아 있으면 파일·DB 변경 전에 거부합니다. 이 검사는 프로세스를 자동 종료하지 않습니다.
2. `backend\data\aeroone.db`, `.env`, `backend\.env`를 별도 매체에 백업합니다.
3. 회전 명령은 저장소의 고정 production 경로와 canonical SQLite DB만 허용합니다. 임의 workspace/provider 인자는 제공하지 않습니다.
4. 현재 Windows 사용자로 생성한 DPAPI 산출물은 같은 Windows 사용자만 복호화할 수 있습니다.
5. 설정된 `ADMIN_USERNAME` 사용자는 DB에서 `role=admin`, `is_active=true`여야 하며 최소 한 명의 활성 관리자가 남아 있어야 합니다.

먼저 쓰기 없는 검증을 실행합니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\rotate_aeroone_credentials.ps1 -DryRun
```

검증이 성공하면 실제 회전을 실행합니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\rotate_aeroone_credentials.ps1
```

`-TestMode`, `-TestWorkspaceRoot`, failpoint는 합성 테스트 전용입니다. production에서 사용할 수 없습니다.

## 2. 회전 범위와 원자성

- `JWT_SECRET_KEY`와 `ADMIN_PASSWORD`를 새 CSPRNG 값으로 교체합니다.
- DB의 모든 사용자 비밀번호를 서로 다른 새 값으로 교체하고 `session_version`을 올립니다.
- 모든 `user_session_activity` 행을 같은 `BEGIN IMMEDIATE` 트랜잭션에서 삭제합니다.
- recovery logical snapshot을 만든 연결의 `BEGIN IMMEDIATE` writer lock을 journal 준비와 credential commit까지 끊지 않습니다. 별도 writer는 그 사이 `database is locked`로 거부됩니다.
- 회전 ID, DB ID, 자격 재료 fingerprint, 전후 상태 fingerprint를 `credential_rotation_ledger`에 한 번만 기록합니다.
- configured admin과 최소 한 명의 활성 admin을 prepare와 commit 양쪽에서 다시 검증합니다.
- 비활성 사용자를 활성화하거나 role을 바꾸지 않습니다. 비활성 계정 로그인은 사용자 상태 노출을 막기 위해 기존 정책대로 **401**이며 403으로 바꾸지 않습니다.

## 3. 보호 산출물과 경로

production 기본 경로는 `%USERPROFILE%\AeroOne-secure\incident-20260710\`입니다. 디렉터리와 파일은 생성 시점부터 현재 Windows SID와 SYSTEM만 FullControl을 갖는 보호 DACL을 사용합니다.

| 경로 | 의미 |
|---|---|
| `bootstrap-marker.json.dpapi` | 물리 workspace ID에 묶인 초기화 소유권 marker |
| `rotation-state.json.dpapi` | strict schema·sequence·checksum·artifact binding을 가진 현재 journal |
| `rotation-state.previous.json.dpapi` | current가 torn/corrupt일 때 사용하는 직전 journal |
| `pending\credentials.dpapi` | 사용자별 새 비밀번호와 JWT가 든 DPAPI bundle |
| `pending\root-env.dpapi`, `pending\backend-env.dpapi` | 목적별 entropy가 분리된 pending 환경 파일 |
| `recovery\aeroone-db-before-rotation.<rotation-id>.dpapi` | 회전 ID에 묶이고 WAL frame을 포함한 SQLite online backup |
| `quarantine\environment\*` | 교체 전 두 환경 파일의 검증된 보존본 |
| `quarantine\quarantine-manifest.json` | rotation/DB ID, retention, 두 환경 항목, canonical SHA-256 checksum에 묶인 strict manifest |
| `credentials.dpapi` | 릴리스 번호와 무관한 최종 운영자 인계 bundle. secure root 내부에 있어 history archive에 함께 포함됨 |

journal과 pending/recovery/bundle은 서로 다른 DPAPI purpose에 묶입니다. artifact를 다른 위치와 맞바꾸면 복호화 또는 digest/binding 검증에서 live 환경 변경 전에 실패합니다.

### 3.1 운영자 자격 확인 뷰어

먼저 WPF를 열지 않는 검증을 실행합니다. 성공 시 stdout/stderr나 별도 파일에 평문 자격을 기록하지 않습니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\view_aeroone_credentials.ps1 -ValidateOnly
```

그 다음 회전을 수행한 **같은 Windows 사용자 세션**에서 뷰어를 엽니다.

```powershell
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File scripts\view_aeroone_credentials.ps1
```

- 임의 bundle 경로를 받지 않으며 `%USERPROFILE%\AeroOne-secure\incident-20260710\credentials.dpapi` 한 자리만 읽습니다.
- current Windows SID의 DPAPI purpose, physical containment, single-link, exact ACL, strict bundle schema를 모두 검증합니다.
- 계정을 선택할 수 있고 비밀번호는 기본 마스킹입니다. 표시와 복사는 운영자가 명시적으로 선택합니다.
- 복사 시 Windows clipboard history와 cloud roaming에서 제외하는 형식을 함께 게시합니다. 다른 앱의 일시적 clipboard 점유는 250ms 간격, 최대 20회로 제한해 게시·확인을 재시도합니다. clipboard가 여전히 방금 복사한 비밀번호일 때만 30초 후 원자적으로 삭제하며, 그 뒤 운영자가 복사한 다른 내용은 지우지 않습니다.
- 자동 삭제가 일시적으로 실패하면 최대 5회 재시도합니다. 마지막 실패 뒤에도 소유 상태를 잊지 않고 명시적 재시도 버튼을 표시하며, 해당 비밀번호가 clipboard에 남아 있는 동안 창 닫기를 거부합니다.
- 콘솔 출력, transcript, 별도 평문 파일로 자격을 내보내지 않습니다.

## 4. 중단과 재개

동일 workspace에서는 물리 디렉터리 ID 기반 mutex 한 개만 회전을 허용합니다. 프로세스가 중단되면 서비스를 시작하지 말고 같은 명령을 다시 실행합니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\rotate_aeroone_credentials.ps1
```

재개는 live `.env`보다 journal/current+previous, ACL, single-link, checksum, recovery/bundle/pending digest, strict quarantine manifest, DB ledger를 먼저 확인합니다. quarantine copy는 볼륨과 무관하게 `CreateNew` temp → flush/readback → final 원자 승격 → size/SHA-256 검증 → source 삭제 순서입니다. 프로세스 사망으로 남은 정확한 이름의 temp는 mutex 획득 후 single-link와 exact ACL을 확인한 경우에만 0으로 덮고 삭제합니다. bootstrap 소유 파일도 읽기·삭제 전에 exact ACL을 통과해야 합니다.

## 5. DB 복원 후 새 회전

완료된 회전의 DB를 `recovery\aeroone-db-before-rotation.<rotation-id>.dpapi`와 논리적으로 같은 독립 일반 백업 상태로 복원한 뒤에는 old completed bundle을 재사용할 수 없습니다. SQLite의 비논리적 header change counter는 canonicalize하지만 schema·테이블·행·DB ID·integrity는 exact 비교합니다. 다음 순서를 지킵니다.

1. 서비스를 계속 중지한 상태로 둡니다.
2. 검증된 일반 SQLite 백업 또는 recovery snapshot을 canonical DB에 복원하고 `aeroone.db-wal`, `aeroone.db-shm`이 없는지 확인합니다.
3. 일반 회전 명령이 old completed artifact/ledger 불일치로 실패하는지 확인합니다. 이 시점에 서비스를 재개하지 않습니다.
4. 다음 exact confirmation으로 completed 상태와 복원 DB의 logical snapshot 일치를 검증하고 old secure root 전체를 보존합니다.

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\rotate_aeroone_credentials.ps1 `
  -RestoreConfirmation ARCHIVE_COMPLETED_ROTATION_AND_START_NEW
```

성공 시 `status=archived`를 출력하고 종료합니다. old root는 삭제되지 않고 같은 secure parent의 `history\<old-rotation-id>\`로 원자 rename됩니다.

5. 일반 회전 명령을 다시 실행해 새 secure root, 새 rotation ID, 새 credential material을 만듭니다.
6. 새 bundle을 §3.1의 `-ValidateOnly`와 WPF 뷰어로 확인합니다.
7. 새 admin 자격으로 실제 `/api/v1/auth/login`이 200인지, 복원된 old 비밀번호와 보관된 completed bundle의 비밀번호가 모두 401인지 확인한 뒤에만 서비스를 재개합니다.

## 6. 보존과 삭제 책임

journal의 현재 retention은 `2027-07-10T00:00:00+09:00`입니다. 스크립트는 completed secure root와 `history\<rotation-id>`를 자동 삭제하지 않습니다. retention은 자동 삭제 시각이 아니라 최소 보존 기준입니다.

삭제 결정은 운영 보안 책임자가 다음을 확인한 뒤 별도 승인 절차로 수행합니다.

- 새 자격으로 서비스가 정상화되었고 old 자격이 거부됨
- 독립 백업과 감사 증적이 보존됨
- 해당 Windows 사용자로 DPAPI 복구가 더 이상 필요하지 않음
- 조직의 사고 대응·법적 보존 기간이 끝남

## 7. 검증 근거

- Round 4 (`1.12.3-hotfix`, main@d6628dd): backend 369 passed(credential-rotation focused 100 passed + 부하 flake 1건 단독 격리 재실행 PASS, 비-credential 268 passed), frontend 313 passed / 66 files + typecheck + production build 통과. 외부 호스트 포화로 credential 게이트는 격리 focused, 비-credential은 별도 실행으로 회수.
- production changed Python: ruff, basedpyright, compileall
- PowerShell: main/모듈/뷰어 전체 AST parse
- actual process: service listener, 연속 SQLite writer lock, secure-root/quarantine/env/credential crash 재개, ordinary backup restore→archive→fresh rotation
- viewer: `-ValidateOnly` 무출력·무변조, wrong purpose/extra schema/insecure ACL 거부, WPF masking/clipboard timer 정적 계약
- 미검증: 실제 WPF 창 시각 조작과 web 브라우저 smoke(이번 보안 변경은 web UI를 수정하지 않음)
