# 단계 7 보고서 — M2 LAN 운영 모드 (`--allow-host`)

- 작성일: 2026-05-07
- 형식: planner-led 설계 + 작은 변경의 묶음 commit
- 결과: **`--allow-host=<host>` 옵션 신설로 단일 PC 의 LAN 노출을 안전하고 일관되게 지원**

---

## 1. 문제 정의 (M2)

지금까지 폐쇄망 배포는 단일 PC 의 브라우저에서만 접속 가능한 loopback 모드(`127.0.0.1` 바인딩)였다. runbook §11 트러블슈팅이 "LAN 내 다른 PC 에서 접근하려면 backend 호스트와 frontend `-H`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`, `SERVER_API_BASE_URL` 을 같은 외부 IP/호스트명으로 모두 일관되게 맞춰야 한다" 고 안내해 왔으나, 실제 운영자가 그걸 한 번에 수행하기는 어렵다. 5개 자리 중 한 곳만 어긋나도 쿠키 도메인 격리 또는 CORS 차단으로 로그인이 실패한다.

따라서 단일 옵션으로 다섯 자리를 한 번에 일관되게 채우는 운영 채널이 필요하다.

---

## 2. 검토한 대안

| ID | 안 | 핵심 | 평가 |
|---|---|---|---|
| A | `setup_offline.bat --allow-host=<host>` 옵션 | 옵션 1개 → .env 5자리 일괄 | ✅ 가장 짧고 명시적 |
| B | 환경 변수 `AEROONE_ALLOW_HOST` 만 사용 | 사전에 export 후 setup 실행 | 인자 노출 X, --help 에 안 보임 |
| C | 별 모드 `lan_network` 추가 | `app_env` Literal 다섯 번째 값 | closed_network 와 분리 가치 낮음, 모드 증식 |
| D | 변경 없이 운영 가이드만 강화 | 런북 5단계 체크리스트 | 운영자 실수 여전히 무방비 |

(A) 채택. 옵션 1개로 5자리를 한 번에 묶고, --help 에서 1줄 안내한다. 환경 변수 fallback 도 함께 지원해 자동화 스크립트에서 쉽게 쓸 수 있게 한다.

---

## 3. 합의 사항

### 3.1 옵션 시그니처

```
setup_offline.bat [--dry-run] [--no-pause] [--allow-host=<host>]
start_offline.bat [--dry-run] [--allow-host=<host>] [--open-browser]
```

또는 환경 변수:

```cmd
set AEROONE_ALLOW_HOST=192.168.1.10
setup_offline.bat
start_offline.bat
```

옵션이 환경 변수보다 우선. 둘 다 없으면 기존 loopback 모드 그대로 (호환성 유지).

### 3.2 `--allow-host=<host>` 가 주어졌을 때 일괄 변경되는 5자리

| 위치 | 기존 (loopback) | LAN 모드 |
|---|---|---|
| backend uvicorn 바인딩 | `127.0.0.1` | `0.0.0.0` |
| frontend next start `-H` | `127.0.0.1` | `0.0.0.0` |
| `backend\.env` `CORS_ORIGINS` | `http://localhost:29501` | `http://localhost:29501,http://<host>:29501` |
| `backend\.env` `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:18437` | `http://<host>:18437` |
| `backend\.env` `SERVER_API_BASE_URL` | `http://localhost:18437` | `http://localhost:18437` (Next.js 가 같은 PC 에서 자기 자신을 호출하므로 loopback 유지) |
| 브라우저 자동 오픈 URL | `http://localhost:29501/` | `http://<host>:29501/` |
| `backend\.env` `LAN_HOST` (신규 metadata) | `(unset)` | `<host>` |

`SERVER_API_BASE_URL` 만 loopback 으로 남는 이유: Next.js 서버 사이드 렌더링은 같은 PC 에서 자기 자신의 backend 를 호출하므로 외부 IP 로 우회할 필요가 없고, loopback 이 더 빠르고 트래픽이 LAN 으로 새지 않는다.

### 3.3 쿠키 도메인 일관성

- 운영자가 LAN 모드에서 자기 PC 를 통해 접속할 때도 반드시 `http://<host>:29501/` 로 들어가야 한다. `http://localhost:29501/` 로 들어가면 페이지 호스트(`localhost`) 와 API 호스트(`<host>`) 가 달라 쿠키가 격리됨.
- runbook §11 의 기존 "Failed to fetch" 진단 항목을 LAN 모드 전용 문구로 보강.
- 자동 오픈 URL 을 `<host>` 로 바꿔 운영자가 자연스럽게 올바른 도메인으로 진입하도록 유도.

### 3.4 보안 고려

| 항목 | 폐쇄망 LAN 모드의 입장 |
|---|---|
| 트래픽 암호화 | HTTP 평문. 폐쇄망 LAN 신뢰 가정 하에서만 허용 가능. 본 모드는 인터넷 노출 production 으로 사용 금지. |
| 쿠키 secure 플래그 | `app_env=closed_network` 이므로 OFF 유지. HTTP 환경에서 쿠키 전달 보장. |
| secret 검증 | `closed_network` 모드 검증 (단계 6) 그대로 적용. 약한 secret 거부 안전망 동일. |
| CORS | 정확히 두 origin (`localhost:29501`, `<host>:29501`) 만 허용. 와일드카드 금지. |
| 0.0.0.0 바인딩 | LAN 노출이 의도이므로 허용. runbook §9 와 §11 에서 "방화벽으로 LAN 외부 차단 권장" 명시. |

### 3.5 변경 표면

| 파일 | 변경 |
|---|---|
| `setup_offline.bat` | `--allow-host=` 인자 파싱, .env 5자리 분기 작성, 새 LAN_HOST 메타 |
| `start_offline.bat` | `--allow-host=` 인자 파싱, backend uvicorn host 변수, 브라우저 URL 변수, frontend 호출 시 `AEROONE_ALLOW_HOST` 전달 |
| `scripts/start_frontend_offline.cmd` | `AEROONE_ALLOW_HOST` 환경 변수가 있으면 `-H 0.0.0.0` 사용, 없으면 기존 `-H 127.0.0.1` |
| `docs/runbook/windows-offline.md` §5, §9, §11 | LAN 모드 절차/위험/체크리스트 추가 |
| `backend/tests/unit/shared/test_windows_batch_scripts.py` | `--allow-host` 동작을 검증하는 신규 테스트 4건 |

기존 loopback 흐름은 옵션 미지정 시 그대로 동작 — 회귀 위험 0.

---

## 4. 구현 후 검증 결과

| 검증 | 결과 |
|---|---|
| 신규 단위 테스트 6건 | 6 passed |
| 신규 테스트 명세 | `test_setup_offline_dry_run_allow_host_prints_lan_info`, `test_setup_offline_dry_run_default_loopback_only`, `test_start_offline_dry_run_allow_host_uses_external_binding`, `test_start_offline_dry_run_default_keeps_loopback`, `test_start_offline_allow_host_missing_value_fails`, `test_start_frontend_offline_script_supports_allow_host_branch` |
| 전체 백엔드 회귀 (`pytest tests`) | 59 passed (직전 53 + 신규 6) |
| `setup_offline.bat --dry-run --allow-host=192.168.1.10` 직접 실행 | `LAN host = 192.168.1.10` / `CORS_ORIGINS = http://localhost:29501,http://192.168.1.10:29501` / `NEXT_PUBLIC_API_BASE_URL = http://192.168.1.10:18437` 출력 확인 |
| `start_offline.bat --dry-run --allow-host=10.0.0.5` 직접 실행 | uvicorn `--host 0.0.0.0 --port 18437` / 브라우저 URL `http://10.0.0.5:29501/` / `LAN host = 10.0.0.5 (backend / frontend bind 0.0.0.0)` 출력 확인 |
| `start_offline.bat --allow-host` (값 누락) 직접 실행 | `[ERROR] --allow-host requires a host argument (IP or hostname).` 출력 + exit 1 |
| 두 배치 모두 옵션 없이 실행 | 기존 `127.0.0.1` 바인딩 + `http://localhost:...` URL 그대로 (회귀 0) |

---

## 5. 미정 사항 (후속 단계로 이월)

| 항목 | 사유 |
|---|---|
| HTTPS 리버스 프록시 자동 구성 | LAN 모드의 다음 단계. 인증서 운영과 nginx/IIS 가이드는 별 PR 로 분리 |
| 호스트명 DNS 검증 | 입력 IP/호스트명의 실제 도달성 점검은 PowerShell `Resolve-DnsName` 으로 가능하나 폐쇄망 DNS 정책에 따라 실패할 수 있어 본 단계에서 제외 |
| 다중 LAN_HOST 동시 지원 | 같은 PC 가 여러 IP/호스트명으로 노출되어야 할 때. 현재는 1개만 허용 (CORS_ORIGINS 가 두 origin) |

---

## 6. 결론

옵션 1개 (`--allow-host=<host>`) 가 5자리를 한 번에 묶어 폐쇄망 LAN 노출을 일관되게 만든다. 옵션 미지정 시 기존 loopback 흐름 그대로라 회귀 위험이 0 이고, 신규 테스트 4건과 기존 53건이 모두 통과한다. closed_network 모드(단계 6)와 자연스럽게 결합되어, 폐쇄망 운영자는 보안 검증을 잃지 않고도 단일 PC 에서 다중 PC LAN 으로 운영 폭을 넓힐 수 있다.
