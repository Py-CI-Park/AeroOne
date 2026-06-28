# Open Notebook 폐쇄망 co-deploy 런북 (AeroOne 동거 배포)

이 문서는 AeroOne 옆에 **Open Notebook**(NotebookLM 대안, MIT)을 **별도 프로세스 군으로 나란히(co-deploy)** 배치해 폐쇄망에서 함께 운영하기 위한 단일 진실 원천(SoT)입니다. 근거 계획: 승인된 ralplan `2026-06-13-0254-bd02` (`.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`).

> **경계(절대 규칙).** 두 스택은 코드 병합 없이 동거합니다. DB(AeroOne SQLite vs Open Notebook SurrealDB)·세션·포트를 공유하지 않으며 결합점은 단 둘 — **대시보드 진입 링크**(AeroAI 섹션의 Notebook 카드 → `http://<host>:8502`)와 **공유 Ollama 엔드포인트**. AeroOne 자체 스택(same-origin proxy / backend-only Ollama / SQLite / path-guard)과 `AGENTS.md` §6 위험신호 6종은 미접촉입니다.

---

## 0. 한눈에 — 두 스택 / 두 번들 / 5 포트

| 스택 | 빌드 산출물 | 설치 | 기동 | 포트 |
|---|---|---|---|---|
| **AeroOne** | `offline_package.bat` → `dist\AeroOne-offline-*.zip` (vendor 트리 제외) | `setup_offline.bat` | `start_offline.bat` (또는 `scripts\run_all.bat`) | backend 18437 / frontend 29501 |
| **Open Notebook** | `airgap\1-online-package.bat` → `dist\AeroOne-bundle\` (+ `AeroOne-bundle.zip`) | `2-airgap-install.bat` | `3-run.bat` (또는 `scripts\run_all.bat` 가 위임) | SurrealDB 8000 / API 5055 / Worker(포트 없음) / Frontend 8502 |
| **공유** | — | Ollama 모델 사전 적재(§2) | Ollama 서버 `127.0.0.1:11434` | 11434 |

AeroOne ZIP 과 Open Notebook 번들은 **각자 빌드/반입**합니다(분리 번들, ralplan ADR-2/B2). 같은 폐쇄망 PC 에 나란히 풀고 `scripts\run_all.bat` 로 staggered 기동합니다(§3).

---

## 1. Vendoring 과 adapter 경로 동결 (core diff 0 기준)

Open Notebook 은 AeroOne 저장소에 **git submodule** (`vendor/open-notebook`) 로 vendoring 하며, 핀 대상은 pristine upstream tag 가 아니라 **AeroOne 유지 fork 브랜치 `aeroone/airgap`** 입니다. 이 브랜치 = 핀된 upstream tag 위에 airgap 도구 + thin adapter 만 rebase 한 형태입니다(ralplan ADR-1/A1).

### 1.1 adapter 경로 집합 (동결)

`vendor/open-notebook` 안에서 AeroOne 유지 fork 가 upstream 위에 **추가로 보유하는 경로(=adapter)** 는 다음으로 동결합니다. 이 목록 외의 애플리케이션 소스는 단 한 줄도 수정하지 않습니다(core 미수정).

| adapter 경로 | 역할 |
|---|---|
| `airgap/` | Docker-free 폐쇄망 번들 도구 일체 (`1-online-package.bat` / `2-airgap-install.bat` / `3-run.bat` / `stop.bat` / `release.bat` / `README.md`). 빌드·설치·기동 런처와 `.env` 시드가 모두 이 안에 있음. |

> 향후 adapter 파일이 늘면(예: 별도 런처/설정) **반드시 이 표에 행을 추가**하고 동시에 §4(동기화) 의 core-diff-0 exclude 인자에도 추가해야 합니다. 표와 exclude 인자가 어긋나면 core diff 0 게이트가 거짓 통과/거짓 차단합니다.

### 1.2 core diff 0 정의

> **core diff 0** = "vendored 애플리케이션 소스(위 adapter 경로 제외) 의 diff vs 핀된 upstream tag == 0". 즉 fork 가 upstream 코어를 단 한 줄도 바꾸지 않음.

검증 스크립트는 [`scripts/check_open_notebook_core_diff.cmd`](../../scripts/check_open_notebook_core_diff.cmd) (§4.2) — `git -C vendor/open-notebook diff --quiet <upstream-tag>..HEAD -- . ":(exclude)airgap"` 의 exit-code 로 판정합니다(비어있지 않으면 exit 1 = 핀 승격 차단).

---

## 2. 공유 Ollama 모델 provisioning (폐쇄망)

폐쇄망에서는 클라우드 AI 가 도달 불가하므로 **on-prem Ollama** 가 두 스택의 유일한 추론 엔드포인트입니다. AeroOne(AeroAI)·Open Notebook 모두 같은 Ollama 서버(`127.0.0.1:11434`)를 공유합니다.

| 소비자 | 모델 | 용도 | 출처(코드/문서) |
|---|---|---|---|
| AeroAI (AeroOne backend) | `gemma4:12b` | 폐쇄망 문서 근거 chat | `backend/app/core/config.py:35` (`ollama_default_model`), `:34` (`ollama_base_url=http://127.0.0.1:11434`) |
| Open Notebook chat | `gemma4:12b` (재사용) | 소스 정리/요약 | 번들 `provision_models.ps1` 자동 등록 |
| Open Notebook embedding | `nomic-embed-text` | 벡터 검색(필수) | 번들 `provision_models.ps1` 자동 등록 |

### 2.1 인터넷 PC — 모델 blob 사전 pull

```cmd
:: 인터넷 가능한 Windows PC 에서 (Ollama 설치 후)
ollama pull gemma4:12b
ollama pull nomic-embed-text
:: 적재된 blob 위치: %USERPROFILE%\.ollama\models  (manifests\ + blobs\)
```

### 2.2 단방향 반입 → 폐쇄망 적재

1. `%USERPROFILE%\.ollama\models` 전체(`manifests\`, `blobs\`)를 USB/사내 파일서버 등 **단방향 허용 경로**로 폐쇄망 PC 의 같은 경로(`%USERPROFILE%\.ollama\models`)에 복사.
2. 폐쇄망 PC 에서 Ollama 서버 기동 후 적재 확인:
   ```cmd
   ollama list
   :: gemma4:12b, nomic-embed-text 가 보이면 성공
   ```

### 2.3 Open Notebook 모델 자동 등록 (배치만으로 완료)

ON 번들의 adapter 스크립트가 **무인 자동 설정**합니다 — Models UI 수동 입력 불필요.

- **`2-airgap-install.bat`** → `write_env.ps1` 가 `app\.env` 를 자동 생성: 랜덤 암호화 키, `OLLAMA_BASE_URL=http://127.0.0.1:11434`(같은 PC 기준; 원격 Ollama 는 `2-airgap-install.bat --ollama-host <ip>` + 그 PC Ollama `0.0.0.0` 바인딩), `API_HOST=0.0.0.0`, `CORS_ORIGINS`(localhost/127.0.0.1/감지된 LAN IP 의 `:8502` — `credentials=True` 라 `*` 불가하므로 명시 오리진).
- **`3-run.bat`** → 기본은 LAN IPv4 자동 감지 후 API/Frontend 를 `0.0.0.0` 으로 띄우고, `--local` 은 loopback 전용, `--allow-host <ip>`/`--allow-host=<ip>` 는 호스트를 고정합니다. API health 200 과 Frontend `:8502` 도달을 확인한 뒤 READY 를 표시하고, `provision_models.ps1` 가 ON API 로 `gemma4:12b`(chat/transformation/tools/large-context) + `nomic-embed-text`(embedding) 를 등록하고 default 할당까지 자동 설정합니다(멱등 — 이미 있으면 보존).
- `3-run.bat` 는 상속된 `CORS_ORIGINS`/`OLLAMA_BASE_URL`/`API_URL` OS 환경변수를 비우고, child process 에 `API_HOST`·`CORS_ORIGINS`·`API_URL`·`INTERNAL_API_URL` 을 명시 전달합니다. 기존 `app\.env` 가 loopback-only 여도 실행 시 네트워크 키가 보정되며, encryption key 는 덮어쓰지 않습니다.

> **전제**: 위 §2.1~§2.2 로 `gemma4:12b` + `nomic-embed-text` 가 폐쇄망 Ollama 에 적재돼 있어야 자동 등록된 모델이 실제 추론·임베딩에 성공합니다(Ollama blob 반입은 두 모델 공통 절차).
> AeroAI 측은 별도 등록 불필요 — `backend/.env` 의 `OLLAMA_BASE_URL` / `OLLAMA_DEFAULT_MODEL` 가 곧장 사용됩니다.

---

## 3. 공유 Ollama 동시성 예산 (3 소비자, testable — ralplan ADR-5)

3 소비자(AeroAI chat + ON chat + ON embedding)가 한 Ollama 를 공유하므로 메모리·동시성을 규율화합니다.

### 3.1 리소스 예산

- **최소 RAM 24GB 권장.** `gemma4:12b`(q4 약 8GB 상주) + `nomic-embed-text`(약 0.3GB) 동거 + OS/두 스택 프로세스 헤드룸. **16GB 미만 = degraded(비권장).**
- GPU 부재(폐쇄망 CPU-only 가정) 시 12B 추론은 직렬화됨.

### 3.2 Ollama 환경변수 권장값

폐쇄망 PC 의 환경변수(또는 Ollama 서비스 설정)에 지정:

| 변수 | 값 | 이유 |
|---|---|---|
| `OLLAMA_MAX_LOADED_MODELS` | `2` | chat 1 + embedding 1 동거 |
| `OLLAMA_NUM_PARALLEL` | `1` | 12B CPU 직렬화 — 동시요청 큐잉으로 health 타임아웃 방지 |
| `OLLAMA_KEEP_ALIVE` | `30m` | 코부팅 직후 재적재 비용 회피 |

### 3.3 staggered boot + health 임계 (수용기준)

`scripts\run_all.bat` 가 순서를 강제합니다 — **AeroOne 먼저 → backend `:18437` health 200 확인 → 그 다음 Open Notebook → ON API `:5055/health` + Frontend `:8502` + runtime `/config` 확인 후 READY**. 동시 cold-load 로 12B 가 중복 적재/직렬화되는 사태와, Open Notebook launcher process 만 뜨고 API 가 아직 준비되지 않았는데 READY 로 오인하는 상황을 막습니다.

| 스택/프로세스 | health 도달 임계 |
|---|---|
| AeroOne backend `:18437/api/v1/health` | ≤ 30s |
| AeroOne frontend `:29501` | ≤ 30s |
| Open Notebook API `:5055/health` (+ "Migrations completed") | ≤ 90s (첫 12B 적재 포함) |
| Open Notebook Frontend `:8502` ("Ready") | ≤ 90s |
| Open Notebook runtime config `:8502/config` | ≤ 10s (Frontend ready 이후, browser API URL 진단) |

### 3.4 degraded mode

RAM < 24GB 또는 health 임계 초과 시 — ① ON chat 모델을 더 작은 모델로 교체하거나, ② AeroAI 와 ON chat 동시 사용을 운영 규율로 시간대 분리. **벡터 임베딩(`nomic-embed-text`)은 항상 상주**시킵니다.

---

## 4. upstream 동기화 절차 (rebase 보존, bare checkout 금지)

upstream open-notebook 새 버전을 따라갈 때, fork `aeroone/airgap` 브랜치의 airgap/adapter 를 보존하면서 핀을 한 단계 올리는 **반복 가능 절차**입니다. 핵심 불변식 — **bare checkout 금지**(airgap/adapter 가 떨어져 나가 fork 가 회귀함), **스모크 통과 전 핀 미승격**.

### 4.1 절차 (operator)

```cmd
:: 0) upstream 원격 등록 (1회; 이미 있으면 이 줄 생략 — git remote -v 로 확인)
git -C vendor\open-notebook remote add upstream https://github.com/lfnovo/open-notebook.git

:: 1) 새 upstream tag fetch
git -C vendor\open-notebook fetch --tags upstream

:: 2) adapter rebase — fork 브랜치를 새 tag 위로 (airgap/ + adapter 보존; bare checkout 금지)
git -C vendor\open-notebook checkout aeroone/airgap
git -C vendor\open-notebook rebase <new-tag>
::    충돌 시: thin adapter(airgap/) 만 수정해 해결하고 core 는 절대 건드리지 않는다.

:: 3) core diff 0 게이트 — 비어야(=exit 0) 핀 승격 가능
scripts\check_open_notebook_core_diff.cmd <new-tag>
::    exit 1 = core 오염 → 핀 승격 차단. exit 2 = submodule/tag 문제.

:: 4) 인터넷 PC airgap 번들 재빌드 (lockfile/uv-cache 재시드)
cd vendor\open-notebook\airgap && 1-online-package.bat

:: 5) 폐쇄망 e2e 스모크(OP-2) + AeroOne backend 175 / frontend 203 통과 전까지 핀 미승격 (게이트)

:: 6) 통과하면 submodule 핀을 새 fork 브랜치 커밋으로 승급 (한국어 커밋 + Lore trailer)
git add vendor\open-notebook && git commit
```

### 4.2 core diff 0 게이트 스크립트

[`scripts/check_open_notebook_core_diff.cmd`](../../scripts/check_open_notebook_core_diff.cmd) — `git -C vendor/open-notebook diff --quiet <upstream-tag>..HEAD -- . ":(exclude)airgap"` 의 exit-code 로 판정합니다(`--quiet` = `--exit-code`; `--stat` 은 변경 유무와 무관히 exit 0 이므로 기계 게이트엔 부적합).

| exit | 의미 |
|---|---|
| `0` | core diff 0 — vendored core 가 upstream tag 와 동일(adapter `airgap/` 제외). 핀 승격 가능 |
| `1` | core 오염 — adapter 밖 소스가 다름. 핀 승격 **차단** + 위반 파일 목록 출력 |
| `2` | submodule 부재 / tag 부재 / git 실패 (사용 오류) |

기본 baseline tag = `v1.9.0`. 다른 tag 는 인자로: `scripts\check_open_notebook_core_diff.cmd <upstream-tag>`. adapter 경로가 늘면 스크립트의 `EXCLUDES` 와 §1.1 동결 표를 **동시에** 갱신해야 게이트가 정확합니다.

### 4.3 동기화 체크리스트

- [ ] 새 upstream tag fetch 완료.
- [ ] `aeroone/airgap` rebase 후 `airgap/` + adapter 파일 보존(존재 + 기능 동작), bare checkout 미사용.
- [ ] `check_open_notebook_core_diff.cmd <new-tag>` == exit 0 (core diff 0).
- [ ] airgap 번들 재빌드 성공(lockfile/uv-cache 재시드, `uv sync --frozen --offline` 일치).
- [ ] 폐쇄망 e2e 스모크(OP-2) + AeroOne backend 175 / frontend 203 통과.
- [ ] 위 전부 통과 후에만 submodule 핀 승급(한국어 커밋 + Lore trailer).

---

## 5. 검증 체크리스트 (이 워크스테이션에서 가능한 범위)

- [x] adapter 경로 동결 표(§1.1) 작성 — `airgap/`.
- [x] core diff 0 정의(§1.2) 명문화.
- [x] 모델 provisioning 절차(§2) + 동시성 예산(§3) 문서화.
- [x] `gemma4:12b` / `http://127.0.0.1:11434` 가 `backend/app/core/config.py:34-35` 과 일치.
- [x] 포트 5종(18437/29501/8000/5055/8502) 비충돌 확인 — `scripts\run_all.bat` preflight.
- [x] broken-link 0 (본 문서 내부/상호 참조).
- [x] upstream 동기화 절차(§4.1) + core-diff-0 게이트 스크립트(§4.2) + 체크리스트(§4.3) 작성.
- [x] `check_open_notebook_core_diff.cmd` 게이트 의미 검증 — `--help` exit 0, submodule 부재 exit 2, diff 의미(airgap-only=exit 0 / core 변경=exit 1) 샌드박스 git 리포 실증.

---

## 6. 운영자 게이트 (물리 폐쇄망/외부 인프라 전제 — 이 워크스테이션 검증 불가)

아래 항목은 산출물(코드/스크립트/문서)은 준비됐으나 **라이브 검증은 운영자가 수행**합니다.

- **OP-1 — submodule 핀 + fork 브랜치 push.** open-notebook 에 `aeroone/airgap` fork 브랜치 생성(upstream tag + `airgap/` rebase) → GitHub push → AeroOne `.gitmodules` 에 `vendor/open-notebook` gitlink 연결. (사용자 GitHub 에 push 되는 외부 작업.)
- **OP-2 — 폐쇄망 4프로세스 e2e 스모크.** 인터넷 PC 에서 (a) AeroOne `offline_package.bat` ZIP(vendor 제외), (b) Open Notebook `airgap\1-online-package.bat` 번들 → 단방향 반입 → 폐쇄망 설치(`setup_offline.bat` / `2-airgap-install.bat`) → `scripts\run_all.bat` staggered 기동 → SurrealDB:8000 / API:5055 / Worker / Frontend:8502 4프로세스 health + Models Test + 대시보드 Notebook 카드 → `http://<host>:8502` 도달.
- **OP-3 — 24GB 폐쇄 PC 공유 Ollama 동시성 실측.** §3.3 health 임계 도달 시간 실측, `OLLAMA_*` 권장값 적용 확인, degraded mode 동작.

---

## 7. 관련 문서

- 폐쇄망 종합 가이드: [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) — Open Notebook co-deploy 섹션 + AeroAI vs Open Notebook 포지셔닝 SoT.
- AeroOne 폐쇄망 런북: [`docs/runbook/windows-offline.md`](windows-offline.md).
- 승인 계획: `.gjc/plans/ralplan/2026-06-13-0254-bd02/pending-approval.md`.
- 공동 기동 래퍼: [`scripts/run_all.bat`](../../scripts/run_all.bat) / [`scripts/stop_all.bat`](../../scripts/stop_all.bat).
