# 단계 6 보고서 — H2 APP_ENV=production 정책 합의

- 작성일: 2026-05-07
- 형식: ralplan 식 3관점 합의 (Planner / Architect / Critic) → 결정 → 구현 → 검증
- 결과: **CONSENSUS — 4번째 모드 `closed_network` 신설로 production 보안 강제와 HTTP 쿠키 호환을 분리**

---

## 1. 문제 정의 (H2)

폐쇄망 PC 는 HTTP-only 환경이라 production 의 secure cookie 동작을 켜면 로그인 쿠키가 브라우저에 저장되지 않는다. 그러나 현재 코드는 `validate_runtime_security` 가 `app_env == 'production'` 일 때만 실행되므로, HTTP 환경을 위해 `APP_ENV=development` 를 유지하면 다음 두 안전 장치가 모두 비활성화된다.

| 보호 대상 | 발동 조건 | 현재 폐쇄망 (development) 에서 |
|---|---|---|
|| `JWT_SECRET_KEY` 가 기본 sentinel이거나 32자 미만일 때 거부 | `app_env == 'production'` | 비활성 — 운영자가 잘못 편집해도 통과 |
|| `ADMIN_PASSWORD` 가 기본 sentinel이거나 12자 미만일 때 거부 | `app_env == 'production'` | 비활성 — 동일 |

`setup_offline.bat` 가 매 실행마다 강한 랜덤 값을 생성해 주긴 하지만, 운영자가 추후 `.env` 를 수동 편집하거나 `.bak` 으로 복원했을 때를 막아주는 안전망이 닫혀 있는 셈이다.

---

## 2. 검토한 대안

| ID | 안 | 핵심 | 장점 | 단점 |
|---|---|---|---|---|
| A | 신규 모드 `closed_network` 추가 | `APP_ENV=closed_network` 일 때 secret 강제 ON, secure cookies OFF | 의도가 코드에 직접 표현됨, 운영자 친화적 | 모드가 4개로 늘어나 enum 관리 부담 약간 증가 |
| B | `secure_cookies` 를 독립 환경 변수로 분리 | `APP_ENV=production` + `SECURE_COOKIES=false` | 자유도 높음 | 운영자가 인터넷 production + Secure=off 같은 위험 조합을 만들 수 있음 |
| C | `--allow-http-production` 같은 백도어 플래그 | production 그대로 두고 secure 만 바이패스 | 변경 최소 | 의미가 모호하고 production 표지의 신뢰가 깨짐 |
| D | 정책 변경 없이 운영 가이드만 강화 | runbook 으로만 안내 | 코드 변경 0 | 운영자 실수에 무방비, H2 미해결 |

---

## 3. 3관점 합의

### 3.1 Planner (목표 정렬)

> "production 의 보안 검증을 잃지 않으면서 HTTP 폐쇄망에서 쿠키가 살아있게 한다." 두 요구를 동시에 만족하는 가장 짧은 길은 **모드를 하나 더 추가하는 것**이다. (B) 처럼 두 차원을 곱셈으로 만들면 검증해야 할 조합이 4배가 된다. (D) 는 H2 자체를 미해결로 두는 셈이라 거부.

### 3.2 Architect (구조 영향)

> 변경 표면은 작다. `Settings.app_env` 의 Literal 에 값 1개 추가, `secure_cookies` 와 `validate_runtime_security` 의 분기 1줄씩 변경, `auth/api.py` 와 `main.py` 는 그대로 유지. setup_offline.bat 가 `.env` 를 매번 새로 쓰므로 기존 폐쇄망 PC 에서 setup 재실행 한 번이면 자동으로 새 모드로 진입한다. 마이그레이션 스크립트 불필요.

### 3.3 Critic (위험 평가)

> 모드 4개는 enum 1줄로 끝나는 비용이라 (A) 의 단점은 무시해도 좋다. (B) 의 장점인 "유연성" 은 폐쇄망 운영의 일관성과 정면으로 충돌 — 동일 환경에서 모든 PC 가 같은 모드면 충분하다. (C) 의 위험("production" 의 의미 훼손) 은 후속 보안 감사에서 즉각 문제로 잡힐 가능성이 크다.

### 3.4 결정

**A 채택.** 모드 추가가 의도(보안 강제 + HTTP 쿠키 호환)를 가장 직접적으로 코드에 새겨 넣는다.

---

## 4. 합의 사항

### 4.1 `app_env` Literal 확장

```python
# Before
app_env: Literal['development', 'test', 'production'] = 'development'

# After
app_env: Literal['development', 'test', 'production', 'closed_network'] = 'development'
```

### 4.2 `secure_cookies` 분기

`production` 만 True. `closed_network` 는 HTTP 환경이므로 False 유지.

```python
@property
def secure_cookies(self) -> bool:
    return self.app_env == 'production'
```

### 4.3 `validate_runtime_security` 분기

`production` 과 `closed_network` 모두 secret 강도 검증 실행. 그 외 (development/test) 는 면제.

```python
def validate_runtime_security(self) -> None:
    if self.app_env not in {'production', 'closed_network'}:
        return
    # ... existing checks unchanged
```

### 4.4 `setup_offline.bat` 기본값

```diff
->"%BACKEND_ENV%" echo APP_ENV=development
+>"%BACKEND_ENV%" echo APP_ENV=closed_network
```

setup_offline.bat 는 매 실행 시 64자 hex JWT 와 48자 hex ADMIN_PASSWORD 를 새로 생성하므로 새 검증을 자연스럽게 통과한다.

### 4.5 runbook §9 갱신

기존: "setup_offline.bat 는 폐쇄망 PC 의 APP_ENV 을 기본 development 로 둡니다." → "기본 closed_network 로 둡니다." 로 정정. closed_network 의 의미를 한 단락으로 설명.

---

## 5. 구현 영향 범위

| 파일 | 변경 종류 | 라인 수 |
|---|---|---|
| `backend/app/core/config.py` | enum 1줄 + 분기 1줄 | +2 -2 |
| `setup_offline.bat` | 기본 APP_ENV 1줄 | +1 -1 |
| `docs/runbook/windows-offline.md` | §9 한 단락 | +6 -2 |
| `backend/tests/unit/test_config.py` | 신규 (4개 테스트) | +50 |

기존 development/test/production 흐름은 모두 무영향. `auth/api.py` 와 `main.py` 는 `secure_cookies` / `validate_runtime_security` 를 통해서만 정책에 접근하므로 변경 불필요.

---

## 6. 테스트 전략

### 6.1 신규 단위 테스트 (`tests/unit/test_config.py`)

| 테스트 | 시나리오 | 기대 |
|---|---|---|
|| `test_closed_network_rejects_default_jwt_secret` | `APP_ENV=closed_network` + `JWT_SECRET_KEY=<기본 sentinel>` | `ValueError` |
| `test_closed_network_rejects_short_admin_password` | `APP_ENV=closed_network` + `ADMIN_PASSWORD=short` | `ValueError` |
| `test_closed_network_passes_with_strong_secrets` | 64자 hex JWT + 48자 hex ADMIN | 통과 |
| `test_closed_network_secure_cookies_false` | `APP_ENV=closed_network` | `secure_cookies == False` |
| `test_production_still_enforces` | 기존 production 동작 유지 회귀 방지 | `ValueError` |
| `test_development_bypasses_validation` | 기존 development 동작 유지 회귀 방지 | 통과 |

### 6.2 회귀 검증

- `pytest backend/tests/unit/test_config.py` — 신규 10건 PASS
- 기존 `app_env='test'` 픽스처는 본 변경 무영향 (Literal 확장은 추가일 뿐)
- `setup_offline.bat --dry-run` 통과 — dry-run 분기는 .env 를 쓰지 않음

### 6.3 사전 실패 9건 (이번 변경과 무관)

`tests/unit/shared/test_windows_batch_scripts.py` 와 `test_windows_frontend_cmd_scripts.py` 에서 9건이 실패하지만, 모두 이전 커밋 `c5e9de6 폐쇄망 운영 일관성과 사용자 안내를 보강한다` 에서 setup.bat / start.bat / start_frontend_offline.cmd 출력 포맷이 바뀐 뒤 테스트 어서션이 갱신되지 않아 발생한 stale 실패다. 본 phase 6 변경을 stash 한 상태에서도 동일하게 9건이 실패함을 직접 확인했다. 별 sub-step "stale 배치 테스트 보정" 으로 같은 ralph 루프 안에서 해결한다.

---

## 7. 미정 사항 (후속 단계로 이월)

| 항목 | 사유 |
|---|---|
| HTTPS 리버스 프록시 가이드 | 본 단계는 "HTTP 폐쇄망에서도 보안 검증 켜기" 가 목표. 인증서 운영은 단계 7 (LAN 모드) 이후 별 PR 로 다룸 |
| 쿠키 `__Host-` prefix 도입 | secure cookie 가 켜져야 의미가 있어 production HTTPS 경로에서 검토 |
| `validate_runtime_security` 에 CORS_ORIGINS 검증 추가 | LAN 모드(단계 7) 와 직접 연결되어 그쪽에서 함께 처리 |

---

## 8. 결론

`closed_network` 모드 신설은 **enum 1줄 + 분기 2줄** 이라는 가장 작은 변경으로 H2 의 핵심 모순(보안 강제 vs HTTP 쿠키)을 해소한다. 폐쇄망 PC 는 setup 재실행 한 번이면 자동 적용되며, 기존 development/test/production 흐름은 무영향이다. 본 단계 commit 에 코드·배치·문서·테스트를 한 묶음으로 반영한다.
