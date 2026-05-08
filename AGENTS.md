# AeroOne 저장소 안내 (AI 에이전트 / 협업자 진입점)

이 문서는 본 저장소를 처음 다루는 **AI 에이전트와 사람 협업자가 가장 먼저 읽어야 할 진입점** 입니다. 사람 운영자용 입구는 [`README.md`](README.md), 폐쇄망 운영 종합 가이드는 [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md), 전체 문서 색인은 [`docs/INDEX.md`](docs/INDEX.md) 입니다.

- 기준 commit: `bb94269`
- 한국어 커밋·PR 규칙은 §3, §4. Claude Code 전용 추가 규칙은 [`CLAUDE.md`](CLAUDE.md).

---

## 1. 프로젝트 정체성 (한 문단)

AeroOne 은 사내 폐쇄망 환경에서 그대로 동작하는 뉴스레터·문서 열람 modular monolith 입니다. 인터넷 가능한 Windows PC 에서 ZIP 1개 (`offline_package.bat`) 로 만들어 단방향 경로로 옮긴 뒤, 폐쇄망 PC 에서 `setup_offline.bat` → `start_offline.bat` 두 명령으로 같은 코드 / 같은 의존성 / 같은 시드로 부팅합니다. backend FastAPI + frontend Next.js (App Router) + SQLite (PostgreSQL 전환 가능).

---

## 2. 운영 모드 4종

`backend/.env` 의 `APP_ENV` 값에 따라 분기됩니다.

| 모드 | secure cookie | secret 강도 검증 | 용도 |
|---|---|---|---|
| `development` | OFF | OFF | 개발자 로컬 (`setup.bat` 기본) |
| `test` | OFF | OFF | pytest 픽스처 전용 |
| `closed_network` | OFF | **ON** | 폐쇄망 HTTP 운영 (`setup_offline.bat` 기본) |
| `production` | **ON** | **ON** | 인터넷 노출 HTTPS (HTTPS + 리버스 프록시 별도 준비 필수) |

근거: [`docs/reports/phase-6-app-env-production.md`](docs/reports/phase-6-app-env-production.md).

---

## 3. 커밋 규칙

### 3.1 형식

- **제목과 본문 모두 한국어**.
- 제목은 변경의 **의도(왜 이 변경을 하는지)** 를 한 줄로. 단순한 파일 나열, 영문 한 줄, `fix` / `update` / `cleanup` 같은 모호한 메시지 금지.
- 본문은 짧게 끝내지 않고 다음을 한국어 문단 1~3개로:
  - 변경 배경
  - 선택한 접근 방식
  - 고려한 제약
  - 제외한 대안과 그 이유
- 마지막에 Lore protocol trailer 를 한국어 값으로 채움.

### 3.2 Lore Trailer 키

| 키 | 의미 |
|---|---|
| `Constraint:` | 이 변경에서 반드시 지켜야 했던 제약 |
| `Rejected:` | 고려했지만 채택하지 않은 대안 + 그 이유 |
| `Confidence:` | 변경의 자신감 수준 (예: high / medium / low 또는 한국어) |
| `Scope-risk:` | 영향 범위 위험 (예: low / medium / high) |
| `Directive:` | 후속 작업자가 따라야 할 지침 |
| `Tested:` | 어떤 검증을 수행했는지 |
| `Not-tested:` | 일부러 또는 환경 제약으로 검증하지 못한 부분 |

### 3.3 금지

- 한 줄짜리 영문 커밋
- 제목만 있고 본문이 없는 커밋
- 맥락 없이 `fix`, `update`, `cleanup` 같은 모호한 메시지
- 실제 의도보다 구현 세부만 나열한 메시지
- 시크릿 (`.env`, JWT 키, 관리자 비밀번호) 을 포함한 커밋

자세한 예시: [`CONTRIBUTING.md`](CONTRIBUTING.md) §2.

---

## 4. PR 규칙

- 제목과 본문 모두 가능한 한 한국어.
- 본문 마크다운 항목: 변경 배경 / 핵심 수정 사항 / 검증 결과 (실행 명령 + 출력) / 영향 범위 / 후속 작업.
- 머지 커밋도 한국어 제목 + 한국어 본문 + Lore trailer.
- 자기 PR 자기 승인은 GitHub 정책상 제한 — 검증 결과 섹션을 충분히 적어 셀프 머지 시 근거를 남김.

자세한 절차: [`CONTRIBUTING.md`](CONTRIBUTING.md) §3.

---

## 5. AI 에이전트가 변경 시 따라야 할 순서

1. 변경 의도를 한국어 commit 메시지 본문 형식 (제목 + 본문 + Lore trailer) 으로 미리 적어 둔다.
2. 코드/배치 변경과 동시에 [`docs/INDEX.md`](docs/INDEX.md), [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) 의 해당 섹션을 갱신한다 (가능하면 동일 commit).
3. 분기 의미가 바뀌면 다음 4자리를 동시에 동기화한다 — 본 INDEX 들, `docs/runbook/windows-offline.md`, 코드 docstring, 회귀 테스트.
4. 새 모드 / 새 옵션을 추가하면 위 §2 표와 [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) §4 / §6 / §7 에 행을 추가한다.

---

## 6. 위험 신호 (즉시 멈추고 사용자에게 물어보기)

- `APP_ENV` Literal 의 값이 줄어드는 변경 (특히 `closed_network` 또는 `test` 제거)
- `validate_runtime_security` 가 `closed_network` 또는 `production` 에서 면제로 바뀌는 변경
- `setup_offline.bat` 가 `APP_ENV=development` 로 회귀
- `backend/scripts/ensure_db_state.py` 의 종료 코드 매핑 (0/1/2/3) 이 바뀌는 변경
- LAN 모드에서 `0.0.0.0` 바인딩이 옵션 미지정 시에도 켜지는 변경 (회귀 0 원칙 위반)
- `offline_package.bat` 의 robocopy `/XD` 제외 목록에서 `.git`, `.omc`, `.worktrees`, `.venv`, `node_modules` 가 빠지는 변경

---

## 7. 코드 진실 원천 (빠른 색인)

| 영역 | 코드 위치 |
|---|---|
| 모드 / secure cookie / secret 검증 | `backend/app/core/config.py:14, 82-95` |
| 부팅 검증 호출 | `backend/app/main.py:18` |
| 쿠키 발급 | `backend/app/modules/auth/api.py:31, 40` (`secure=settings.secure_cookies`) |
| DB 상태 점검 (배치) | `backend/scripts/ensure_db_state.py` (docstring 에 종료 코드 표) |
| 폐쇄망 LAN 옵션 | `setup_offline.bat`, `start_offline.bat` 의 `:parse_args` / `:capture_host` |
| 패키징 제외 목록 | `offline_package.bat:34` (`/XD` 인자) |

자세한 분포: [`docs/INDEX.md`](docs/INDEX.md) §6, [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) §15.1.

---

## 8. 회귀 테스트 입구

```cmd
cd backend && .venv\Scripts\activate && set PYTHONPATH=. && python -m pytest tests -q
```

기준 commit `bb94269` 에서 **66 passed**. 회귀 발생 시 [`docs/INDEX.md`](docs/INDEX.md) §7 표와 [`docs/reports/INDEX.md`](docs/reports/INDEX.md) 를 참고해 어느 단계의 회귀인지 진단합니다.

---

## 9. 진입점 색인

| 독자 | 첫 입구 |
|---|---|
| 처음 보는 사람 | [`README.md`](README.md) |
| 폐쇄망 운영자 | [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) |
| 개발자 | [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) |
| AI 에이전트 | 본 문서 + [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) §14 |
| Claude Code | [`CLAUDE.md`](CLAUDE.md) |
| 기여자 | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| 전체 문서 색인 | [`docs/INDEX.md`](docs/INDEX.md) |
