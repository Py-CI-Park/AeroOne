# AeroOne 저장소 안내 (AI 에이전트 / 협업자 진입점)

이 문서는 본 저장소를 처음 다루는 **AI 에이전트와 사람 협업자가 가장 먼저 읽어야 할 진입점** 입니다. 사람 운영자용 입구는 [`README.md`](README.md), 폐쇄망 운영 종합 가이드는 [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md), 전체 문서 색인은 [`docs/INDEX.md`](docs/INDEX.md) 입니다.

- 기준 release candidate: `1.13.0-dev`
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
- (1.0.22 정책 변경) `setup_offline.bat` / `start_offline.bat` 의 **기본 바인딩이 LAN(0.0.0.0, LAN IP 자동 감지)** 으로 바뀌었다(운영자 명시 요청). 위험 신호는 이제 반대 방향이다 — `--local`(loopback 전용) 옵트아웃이 제거되거나, LAN IP 미감지 시 loopback 폴백이 사라지거나, `scripts/allow_lan_firewall.cmd` 의 `remoteip=LocalSubnet` 스코프가 풀려 LAN 외부까지 노출되는 변경
- `offline_package.bat` 이 `scripts/build_offline_package.ps1` 위임을 제거하거나, builder의 `git archive` allow-list·Task 5 pre/post verifier·production requirements 전용·정확한 인스톨러 검증을 우회하는 변경

---

## 7. 코드 진실 원천 (빠른 색인)

| 영역 | 코드 위치 |
|---|---|
| 모드 / secure cookie / secret 검증 | `backend/app/core/config.py:14, 82-95` |
| 부팅 검증 호출 | `backend/app/main.py:18` |
| 쿠키 발급 | `backend/app/modules/auth/api.py:31, 40` (`secure=settings.secure_cookies`) |
| DB 상태 점검 (배치) | `backend/scripts/ensure_db_state.py` (docstring 에 종료 코드 표) |
| 폐쇄망 LAN 옵션 | `setup_offline.bat`, `start_offline.bat` 의 `:parse_args` / `:capture_host` |
| 공개 오프라인 패키징 | `offline_package.bat`, `scripts/build_offline_package.ps1`, `backend/app/operations/offline_package_policy.py`, `packaging/installer-policy.json` | 배치는 호환 wrapper이고, builder가 tracked source allow-list→clean build→Task 5 pre/post ZIP 검증을 강제. `.gjc`, `.omo`, `.env`, DB, runtime data, dev dependency/artifact는 정책에서 제외 |
| Open Notebook co-deploy | [`docs/runbook/open-notebook-airgap.md`](docs/runbook/open-notebook-airgap.md), `scripts/run_all.bat` / `scripts/stop_all.bat` |

자세한 분포: [`docs/INDEX.md`](docs/INDEX.md) §6, [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) §15.1.

---

## 8. 회귀 테스트 입구

```cmd
cd backend && .venv\Scripts\activate && set PYTHONPATH=. && python -m pytest tests -q
```

현재 `1.13.0-dev` 릴리스 후보에서 backend **567 passed**, frontend **397 passed / 73 files**를 유지합니다. 회귀 발생 시 [`docs/INDEX.md`](docs/INDEX.md) §7 표와 [`docs/reports/INDEX.md`](docs/reports/INDEX.md) 를 참고해 어느 단계의 회귀인지 진단합니다.

---

## 9. 릴리즈 사이클

본 저장소는 시멘틱 버전 (예: `1.0.3`) 단위로 릴리즈합니다. 1.0.0 부터 1.0.3 까지 정착된 사이클을 같은 모양으로 반복합니다.

### 9.1 표준 5 단계

1. **새 dev 브랜치 분기** — `<버전>-dev` 형식 (예: `1.0.4-dev`). 직전 태그 또는 최신 main 에서 분기.
2. **개발 commit 누적** — §3 커밋 규칙 (한국어 제목 + 한국어 본문 + Lore trailer) 을 모든 commit 에 적용. dev 브랜치에만 push 하고 main 에 직접 commit 하지 않음.
3. **버전 표기 갱신** — 정식 릴리즈 직전 마지막 commit 으로 README.md 의 두 자리만 업데이트:
   - `![version](https://img.shields.io/badge/version-X.Y.Z-1f6feb)`
   - "검증" 섹션의 "릴리스 X.Y.Z 기준" 한 줄
4. **main 병합** — `git merge --no-ff <버전>-dev`. squash 금지 — commit 단위 추적이 깨진다. 병합 commit 메시지는 §3 규칙 그대로 한국어 + Lore trailer 사용.
5. **annotated tag + GitHub release + ZIP asset upload** —
   ```
   git tag -a X.Y.Z -m "X.Y.Z — 한 줄 설명"
   git push origin main X.Y.Z
   gh release create X.Y.Z --title "..." --notes "..."

   :: ZIP 빌드 (exact annotated tag=HEAD=version, clean tree에서만 publishable=true)
   offline_package.bat
   :: 산출물: dist\AeroOne-offline-X.Y.Z.zip + .sha256

   :: GitHub Release 에 ZIP + sha256 asset 첨부 (운영자가 GitHub 에서 직접 받을 수 있도록)
   gh release upload X.Y.Z dist\AeroOne-offline-X.Y.Z.zip dist\AeroOne-offline-X.Y.Z.zip.sha256
   ```

### 9.2 브랜치 보존 정책

`<버전>-dev` 브랜치는 릴리즈 후에도 **삭제하지 않습니다**. 각 dev 브랜치는 그 버전의 변경 의도와 검증 흔적을 보존하는 release archaeology 입니다. 1.0.2-dev / 1.0.3-dev 가 origin 에 그대로 남아있는 것이 정상 상태.

### 9.3 검증 게이트 (병합 직전)

- backend `pytest tests` — 현재 release phase report의 전체 건수(**1.13.0 RC: 567 passed**) 유지 (실패 0).
- 코드 / 배치 / 문서 변경의 §6 위험 신호 6 가지를 commit 직전 자체 점검.
- UI 변경이면 운영자가 dev 서버에서 직접 화면 확인 + Playwright 자동 검증 (preview, 셀, iframe 등 의도된 자리의 측정값).
- 문서 변경이면 broken-link grep + 정합성 검증 (참조 commit / 코드 라인 번호가 실재).

### 9.4 예외 — 긴급 hotfix

긴급 보안 패치나 1 줄 fix 처럼 별 dev 브랜치 분기가 과한 경우는 다음 흐름을 허용합니다.

1. main 에서 직접 hotfix commit (단, §3 한국어 + Lore trailer 규칙은 그대로).
2. 같은 자리에서 patch 버전 (예: `1.0.4` -> `1.0.4.1` 또는 다음 patch 인 `1.0.5`) annotated tag 부착.
3. README 버전 갱신은 다음 정규 release 사이클 때 한 번에 처리.

긴급 hotfix 의 기준은 다음 중 하나 이상 — 보안 결함, 부팅 불가, 데이터 손상 위험. 단순 UI 개선이나 문서 보강은 정규 사이클로 가야 합니다.

### 9.5 dist/ 와 ZIP asset 관리 정책

`dist/` 는 `.gitignore` 로 git 에서 제외되어 본 PC 의 디스크에만 존재합니다. 운영자가 GitHub 외부에서 ZIP 을 받을 수 있는 경로는 **GitHub Release 의 asset** 한 자리뿐 — `gh release upload X.Y.Z dist\AeroOne-offline-X.Y.Z.zip dist\AeroOne-offline-X.Y.Z.zip.sha256` 으로 매 release 의 단계 5 에서 반드시 첨부합니다.

본 PC 의 `dist/` 보존 정책:

- 최신 ZIP 1개와 그 sha256 파일만 보존 권장. 이전 exact-version 산출물은 GitHub Release asset에 올라간 뒤 로컬에서 정리할 수 있습니다.
- release mode는 clean tree의 접두사 없는 exact annotated tag `X.Y.Z`가 HEAD와 일치할 때만 `dist/AeroOne-offline-X.Y.Z.zip`을 생성합니다.
- tag가 없거나 version과 다르면 timestamp fallback 없이 `artifacts/qa/X.Y.Z/X.Y.Z-pr-<SHA>/`에 `publishable=false` QA 산출물을 생성합니다. dirty tree는 release/QA 모두 fail-closed입니다.

### 9.6 minor / major 트리거

본 저장소의 버전 의미는 다음과 같이 합의되어 있습니다.

| 변경 | 사이클 |
|---|---|
| 버그 픽스, UI 정리, 문서 보강, 폐쇄망 흐름 강화 | patch 증가 (`1.0.X`) |
| 신기능 추가 (예: PDF 썸네일 파이프라인, Markdown CRUD UI), 새 운영 모드, 새 모듈 | minor 증가 (`1.X.0`) |
| 데이터 스키마 breaking change, 명령 시그니처 호환 깨짐, `.env` 키 호환 깨짐 | major 증가 (`X.0.0`) |

major 또는 minor 사이클은 정식 PR + `docs/reports/phase-N-...md` 형태의 단계 보고서 1 건 이상이 함께 요구됩니다. patch 사이클은 단계 보고서가 없어도 됩니다.

---

## 10. 진입점 색인

| 독자 | 첫 입구 |
|---|---|
| 처음 보는 사람 | [`README.md`](README.md) |
| 폐쇄망 운영자 | [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) |
| 개발자 | [`docs/runbook/local-dev.md`](docs/runbook/local-dev.md) |
| AI 에이전트 | 본 문서 + [`docs/CLOSED_NETWORK_GUIDE.md`](docs/CLOSED_NETWORK_GUIDE.md) §14 |
| Claude Code | [`CLAUDE.md`](CLAUDE.md) |
| 기여자 | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| 전체 문서 색인 | [`docs/INDEX.md`](docs/INDEX.md) |
| Open Notebook co-deploy | [`docs/runbook/open-notebook-airgap.md`](docs/runbook/open-notebook-airgap.md) |
