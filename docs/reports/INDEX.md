# 단계별 변경 보고서 색인

폐쇄망 운영 보강 4단계 + 기능 모듈 1건(읽음추적)의 의도·합의안·구현·검증을 단일 commit 단위로 묶어 둔 보고서 5종 입니다. 본 디렉토리는 "왜 그렇게 만들었는가" 의 진실 원천이며, "어떻게 사용하는가" 는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) 와 [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md) 에 있습니다.

---

## 권장 읽기 순서

1. [단계 8 — 시뮬레이션](phase-8-offline-simulation.md) — 변경 직전 운영 신뢰도 확보
2. [단계 6 — `closed_network` 모드](phase-6-app-env-production.md) — 정책 합의
3. [단계 7 — `--allow-host` LAN 모드](phase-7-lan-mode.md) — 운영 폭 확장
4. [단계 9 — `ensure_db_state.py` docstring](phase-9-docstring.md) — 코드 안 진실 원천 매듭

---

## 단계별 요약

### 단계 6 — `closed_network` 모드 신설

- 파일: [`phase-6-app-env-production.md`](phase-6-app-env-production.md) (151줄)
- commit: `f43ae04`
- 무엇: `app_env` Literal 에 `closed_network` 추가. secure cookie 는 OFF 유지하면서 `JWT_SECRET_KEY` / `ADMIN_PASSWORD` 강도 검증을 강제.
- 코드: `backend/app/core/config.py:14, 82-95`
- 회귀 방지: `backend/tests/unit/test_config.py` (10건)

### 단계 7 — `--allow-host` LAN 운영 모드

- 파일: [`phase-7-lan-mode.md`](phase-7-lan-mode.md) (119줄)
- commit: `7a6879e`
- 무엇: 옵션 1개로 backend 호스트, frontend 호스트, CORS_ORIGINS, NEXT_PUBLIC_API_BASE_URL, 자동 오픈 URL 5자리를 일괄 LAN 모드로 전환.
- 코드: `setup_offline.bat`, `start_offline.bat`, `scripts/start_frontend_offline.cmd`
- 회귀 방지: `backend/tests/unit/shared/test_windows_batch_scripts.py` (--allow-host 6건 + 기존 11건)

### 단계 8 — 폐쇄망 배포 시뮬레이션

- 파일: [`phase-8-offline-simulation.md`](phase-8-offline-simulation.md) (205줄)
- commit: `d2cec35`
- 무엇: dry-run 3종 (setup_offline / start_offline / offline_package) + 라이브 5단계 검증 (health, list, login) + 실 PC 시뮬레이션 플레이북.
- 부수: `docs/runbook/windows-offline.md` §10 의 `?limit=1` 잘못된 가이드 정정.

### 단계 9 — `ensure_db_state.py` docstring + 단위 테스트

- 파일: [`phase-9-docstring.md`](phase-9-docstring.md) (73줄)
- commit: `2e69b4b`
- 무엇: 종료 코드 0/1/2/3 의 의미를 모듈/함수 docstring 에 직접 새기고, 4분기를 회귀 차단하는 단위 테스트 7건 추가.
- 코드: `backend/scripts/ensure_db_state.py`
- 회귀 방지: `backend/tests/unit/test_ensure_db_state.py` (7건)

### 단계 10 — IP 기반 읽음추적(열람 횟수) 모듈

- 파일: [`phase-10-read-tracking.md`](phase-10-read-tracking.md)
- 분류: minor (`1.1.0`) — 신규 모듈. commit: `2ec9016` (dev 브랜치 `1.1.0-dev`)
- 무엇: 브라우저 직접 호출 read-beacon 으로 접속 IP 를 잡아 `(newsletter_id, client_ip)` 30분 디바운스 upsert 로 열람 횟수를 집계하고, 관리자만 조회·수동 purge. SSR loopback 우회가 핵심.
- 코드: `backend/app/modules/read_tracking/`, `frontend/components/newsletter/read-beacon.tsx`, `frontend/app/admin/read-events/`
- 회귀 방지: `backend/tests/unit/read_tracking/` (6), `backend/tests/integration/test_read_tracking_api.py` (7), frontend Vitest 6건

---

## 보고서가 다루지 않는 자리

- 운영 절차: [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md), [`docs/runbook/windows-offline.md`](../runbook/windows-offline.md)
- 코드 진실 원천: 각 보고서의 "코드" 항목 + [`docs/INDEX.md`](../INDEX.md) §6
- 회귀 테스트 인벤토리: [`docs/INDEX.md`](../INDEX.md) §7
