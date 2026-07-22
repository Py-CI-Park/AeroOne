# 폐쇄망 start_offline.bat exit 98(유지보수 게이트 경합) 조사 기록

- 작성일: 2026-07-22
- 상태: **1.19.1 로 실제 결함(복구 도구 누락) 해결·게시 완료. 근본 재현 여부는 운영자 재부팅 클린 부팅 확인 대기(재검토 예정).**
- 관련 릴리스: 1.19.1 (Latest, immutable). 개발 승계: 1.20.0-dev.

> 이 문서는 운영자 요청으로 "나중에 재검토"를 위해 조사 내용·결론·후속 확인 단계를 기록만 해 둔 것이다.

---

## 1. 증상 (운영자 보고)

폐쇄망 PC 에서 1.19.0 릴리스를 받아 설치(setup_offline.bat) 후 start_offline.bat 실행 시:

```
[ERROR] Startup maintenance preflight did not pass (exit 98).
[INFO ] An AeroOne backend from a previous run is still holding the maintenance gate.
        Close its window, run stop_offline.bat, or reboot, then rerun start_offline.bat.
```

- 안내하는 `stop_offline.bat` 이 패키지 안에 없음.
- "이전 버전 실행할 때는 잘 되었다"고 함.

---

## 2. 근본 원인 (코드 추적 결과)

| 사실 | 근거(파일·라인) |
|---|---|
| 실행 중인 백엔드가 Global 유지보수 뮤텍스를 점유한다 | `backend/app/main.py:46` `assert _maintenance_gate_ready` → `backend/app/core/maintenance_gate.py:45` `acquire_backend_maintenance_gate()` 가 `scripts/windows/hold_maintenance_gate.ps1` lease 프로세스를 띄워 뮤텍스 점유, `atexit`(L94)로 해제 |
| lease 는 백엔드의 자식(창/트리 공유), stdin=PIPE | `maintenance_gate.py:63-80` Popen(creationflags 없음, stdin/stdout/stderr=PIPE) |
| 깨끗한 종료·크래시는 98을 유발하지 않는다 | `scripts/credential_rotation/Rotation.ProcessLock.psm1:101-102` `Enter-RotationMutex` 가 **AbandonedMutexException 을 잡아 뮤텍스를 정상 인수**. 즉 백엔드/ lease 가 죽으면 뮤텍스는 abandoned → 다음 start 가 그대로 획득 |
| exit 98 = 살아있는 홀더가 대기 타임아웃(20s)까지 점유 | `Rotation.ProcessLock.psm1:97-99` `WaitOne` 이 false → null 반환 → `invoke_with_maintenance_gate.ps1:46-48` 이 exit 98. start_offline.bat:98 은 `-WaitTimeoutSeconds 20` |
| exit 97 은 게이트 생성 불가(폴백, 정상) | `invoke_with_maintenance_gate.ps1:15-19,40-42` (SeCreateGlobalPrivilege 없음/ reparse) → 직접 preflight 폴백 |
| start 전 이미 실행 감지가 앞단에 있음 | `start_offline.bat:96` `:check_already_running`(포트 점유 시 exit 1, 98 아님). 즉 98 은 "포트는 비었는데 게이트만 점유" 상태 |

### 결론
- **신선 설치 자체가 98을 내는 코드 결함은 확인되지 않음**(abandoned 뮤텍스 정상 처리).
- exit 98 은 **직전 start 시도가 남긴 백엔드/lease 프로세스가 게이트를 계속 쥐고 있을 때** 발생.
- "이전 버전은 잘 됨" 은 그 버전이 게이트 도입(≈1.16.x) 전이었거나, 그때는 잔여 프로세스가 없었기 때문으로 추정.
- **유일하게 확인된 실제 결함 = 복구 도구 stop_offline.bat 이 어떤 오프라인 ZIP 에도 실린 적이 없던 것.**

---

## 3. 실제 결함과 수정 (1.19.1, 게시 완료)

- 원인: `packaging/installer-policy.json` 의 `allow_top_level_entries` 에 `stop_offline.bat` 이 없어(git-archive allow-list 빌드) 어떤 ZIP 에도 포함되지 않음. start/setup_offline.bat 은 포함, stop 만 누락. start/게이트 코드는 1.17.1 이후 불변.
- 수정: allow-list 에 `stop_offline.bat` 추가. 재발 방지로 `backend/tests/unit/test_installer_policy_json.py` 에 setup/start/stop 세 배치 포함 강제 테스트 추가.
- 검증: 1.19.1 ZIP 안에 stop_offline.bat 포함 실측(selected_count 646→647, Task5 entry_count 21426), backend 89 passed·frontend tsc 0·10 passed.
- 게시: GitHub Release **1.19.1 Latest·immutable**, ZIP+sha256(`fb4e4a5e8589f86afe0a8e3ccbad889423ae7eb3dd2a16e18fa644c7ad06fa9c`). 1.20.0-dev 로 패키징 fix 승계(커밋 50c6497).

### 자동 복구를 넣지 않은 이유
게이트는 자격증명 회전(credential rotation)도 보호한다. "포트 비었는데 게이트 점유" 는 *잔여 lease* 일 수도 *진행 중 회전* 일 수도 있어(회전 중엔 백엔드 포트도 비어 있음), 자동 종료 시 회전을 깨 데이터 손상 위험. 따라서 운영자가 명시적으로 stop_offline.bat 을 실행하는 것이 안전한 설계다.

---

## 4. 즉시 복구 절차 (운영자)

1. **재부팅** → start_offline.bat (재부팅이 잔여 홀더를 정리) — 가장 확실.
2. **1.19.1 ZIP** 으로 교체 → stop_offline.bat → start_offline.bat.
3. 재부팅 없이(관리자 PowerShell, = stop_offline.bat 동작):
```powershell
powershell -NoProfile -Command "foreach($p in 18437,29501){Get-NetTCPConnection -LocalPort $p -State Listen -EA SilentlyContinue|Select -Expand OwningProcess -Unique|%{Stop-Process -Id $_ -Force -EA SilentlyContinue}}; Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\"|?{$_.CommandLine -match 'hold_maintenance_gate|invoke_with_maintenance_gate'}|%{Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue}"
```

---

## 5. 후속 확인 단계 (재검토 시 판단 근거)

**1.19.1 로 교체 → 완전 재부팅 → setup_offline → start_offline** 순서로 1회 확인:

- **재부팅 직후(클린) 첫 start 부터 98** → 잔여 프로세스가 아니라 더 깊은 원인. 후보:
  - `start_offline.bat` `:check_already_running` 의 포트 감지 사각(예: LAN 바인딩 0.0.0.0 IP 와 프로브 대상 불일치)로, 실제 서빙 중 백엔드를 못 잡고 게이트 경합만 노출.
  - lease 가 백엔드 사망 후에도 stdin EOF 를 못 받고 생존하는 특정 환경(콘솔/재부모화).
  → 이 경우 98 이 뜬 정확한 단계·로그를 수집해 **1.19.2 로 근본 수정**.
- **재부팅 직후엔 정상, 창을 닫은 뒤 재실행에서만 98** → 설계대로이며 stop_offline.bat(1.19.1 포함)이 정답. 추가 코드 수정 불필요.

### 코드 수정 판단
현재까지 근거로는 shipped fix(stop_offline.bat 포함) 외에 코드로 더 손댈 확정 근거 없음. 추측성 게이트 수정은 하지 않는다. 위 클린 부팅 재현 시 그 증거로 착수.

---

## 참조 코드
- `backend/app/main.py:46`, `backend/app/core/maintenance_gate.py:45-94`
- `scripts/windows/hold_maintenance_gate.ps1`, `scripts/windows/invoke_with_maintenance_gate.ps1`
- `scripts/credential_rotation/Rotation.ProcessLock.psm1`(Enter-RotationMutex/Enter-AeroOneMaintenanceGate)
- `start_offline.bat`(:maintenance_preflight, :check_already_running, :run_startup_preflight)
- `stop_offline.bat`, `packaging/installer-policy.json`, `backend/tests/unit/test_installer_policy_json.py`
