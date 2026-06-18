# 폐쇄망 상세 설치·사용 매뉴얼 — AeroOne + Open Notebook

이 문서는 **폐쇄망 PC 운영자가 처음부터 끝까지 그대로 따라 하는** 단일 설치·사용 매뉴얼입니다. AeroOne(뉴스레터·문서·AeroAI)과 Open Notebook(NotebookLM 대안)을 **코드 병합 없이 나란히(co-deploy)** 띄워 모든 기능을 폐쇄망에서 사용하는 절차를 다룹니다. 이 문서는 AeroOne 오프라인 ZIP(`docs/`)에 함께 포함되어 반입됩니다.

- 빠른 요약은 [`README.md`](../../README.md), 종합 가이드는 [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) §18, Open Notebook 내부 세부는 [`docs/runbook/open-notebook-airgap.md`](open-notebook-airgap.md).
- 새 오픈소스를 같은 방식으로 도입하는 절차는 [`docs/closed-network-oss-adoption-process.md`](../closed-network-oss-adoption-process.md).

---

## 0. 한눈에 — 두 앱 / 두 ZIP / 공유 Ollama

| 스택 | 접속 | 포트 | 인증 |
|---|---|---|---|
| AeroOne Web | `http://<host>:29501/` | 29501 (frontend) / 18437 (backend) | 공개 열람 무인증, `/admin/*` 는 `admin_session` 쿠키 |
| Open Notebook | `http://<host>:8502/` | 8502 (frontend) / 5055 (API) / 8000 (SurrealDB) | 자체 무인증 (§5 보안 주의) |
| 공유 Ollama | (백엔드 전용) | 11434 | — |

대시보드(AeroOne) AeroAI 섹션의 **Notebook 카드**가 `http://<host>:8502` 로 연결됩니다. 두 스택은 DB·세션·포트를 공유하지 않고, 결합점은 **대시보드 링크 + 공유 Ollama** 둘뿐입니다.

---

## 1. 인터넷 PC에서 반입물 모으기 (4가지)

USB 등 **단방향 허용 매체**로 폐쇄망 PC에 복사할 4가지:

1. **AeroOne 오프라인 ZIP** — 인터넷 PC 저장소 루트에서 `offline_package.bat` 실행 → `dist\AeroOne-offline-<버전>-<스탬프>.zip`
   - 소스·wheelhouse·`node_modules`·prebuilt `.next`·옵션 인스톨러 포함. (vendored open-notebook 트리는 의도적으로 제외)
2. **Open Notebook 번들 ZIP** — open-notebook 저장소에서 `airgap\1-online-package.bat` 실행 → `dist\AeroOne-bundle.zip`
   - 자체 Python/uv/Node/SurrealDB/ffmpeg + prebuilt frontend + 자동 프로비저닝 스크립트 포함(자기완결).
3. **Ollama 설치파일** — 폐쇄망 PC에 Ollama가 없으면 `OllamaSetup.exe` (https://ollama.com/download). 있으면 생략.
4. **Ollama 모델 blob** — 인터넷 PC에서 미리 받은 모델 파일:
   ```cmd
   ollama pull gemma4:12b
   ollama pull nomic-embed-text
   :: 위치: %USERPROFILE%\.ollama\models  (manifests\ + blobs\ 폴더 전체)
   ```

> **AeroOne 런타임 전제**: 폐쇄망 PC에 Python 3.12 / Node 20 이 필요합니다(없으면 인스톨러를 인터넷 PC 저장소 루트 `offline_installers\` 에 넣고 `offline_package.bat` 실행 → ZIP 안 `offline_assets\installers\` 로 동봉). Open Notebook 은 자체 런타임을 동봉하므로 별도 불필요.

---

## 2. 폐쇄망 PC — 공유 Ollama 준비 (가장 먼저)

```cmd
:: 1) Ollama 설치 (OllamaSetup.exe 실행) — 설치 후 자동으로 127.0.0.1:11434 에서 구동
:: 2) 반입한 models 폴더를 그대로 복사:
::    <USB>\models\*  ->  %USERPROFILE%\.ollama\models\
:: 3) 적재 확인:
ollama list
::    gemma4:12b, nomic-embed-text 둘 다 보이면 성공
```

> **중요**: 모델은 반드시 여기서 먼저 적재합니다. 뒤의 Open Notebook 자동 모델 등록은 "ON이 이 모델을 쓰도록 설정"하는 것이라, Ollama에 모델이 없으면 등록은 돼도 실제 추론·임베딩이 실패합니다.

---

## 3. 폐쇄망 PC — AeroOne 설치

```cmd
:: 공백·한글 없는 경로에 압축 해제. 예: D:\AeroOne\
cd D:\AeroOne
setup_offline.bat
```
- `setup_offline.bat` 은 Python venv 오프라인 복원, DB 마이그레이션/시드, frontend 의존성 확인을 수행합니다(`APP_ENV=closed_network`).
- 자세한 단계·종료 코드: [`docs/runbook/windows-offline.md`](windows-offline.md) §6.

---

## 4. 폐쇄망 PC — Open Notebook 설치 (AeroOne 옆에 나란히)

```cmd
:: AeroOne 의 형제 폴더로 압축 해제. 예: D:\AeroOne-bundle\
::   (권장 배치)  D:\AeroOne\   +   D:\AeroOne-bundle\
cd D:\AeroOne-bundle
2-airgap-install.bat
```
`2-airgap-install.bat` 이 자동으로:
- Python venv 를 번들 캐시에서 **오프라인 재구성**,
- `app\.env` 를 **자동 생성** — 랜덤 암호화 키, `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `API_HOST=0.0.0.0`, `CORS_ORIGINS`(localhost/127.0.0.1/감지된 LAN IP 의 `:8502`). 기존 `.env` 가 있으면 encryption key 보존을 위해 덮어쓰지 않으며, `3-run.bat` 가 실행 시 네트워크 키를 child process 환경변수로 보정합니다.

> **Ollama 가 다른 PC에 있을 때만**: `2-airgap-install.bat --ollama-host <그-PC-IP>` 로 설치하고, 그 PC의 Ollama 가 `0.0.0.0` 으로 바인딩돼 있어야 합니다(환경변수 `OLLAMA_HOST=0.0.0.0`). 같은 PC면 기본값(127.0.0.1)이 가장 안정적입니다.

---

## 5. 함께 기동

### 5.1 권장 — 통합 런처 (staggered)
```cmd
cd D:\AeroOne
scripts\run_all.bat
```
- 동작: AeroOne 먼저 기동 → backend `:18437` health 확인 → Open Notebook 기동(SurrealDB→API→Worker→Frontend) → ON API `:5055/health`, Frontend `:8502`, runtime `/config` 확인 → **모델 자동 등록**(`gemma4:12b` chat / `nomic-embed-text` embedding + default 할당).
- ON 번들이 `..\AeroOne-bundle` 가 아니면: `scripts\run_all.bat --on-bundle D:\경로\AeroOne-bundle`
- 단일 PC 전용으로 묶어 띄울 때: `scripts\run_all.bat --local` (AeroOne 과 Open Notebook 양쪽 모두 loopback 전용)
- 정지: `scripts\stop_all.bat`

### 5.2 개별 기동 (한쪽만 쓰거나 디버깅 시)
```cmd
:: AeroOne 만
cd D:\AeroOne && start_offline.bat
:: Open Notebook 만 (기본 LAN 자동 감지, API_URL/CORS 자동 보정)
cd D:\AeroOne-bundle && 3-run.bat
:: Open Notebook 을 이 PC에서만 열 때
cd D:\AeroOne-bundle && 3-run.bat --local
```

---

## 6. 확인 (정상 동작 체크리스트)

- [ ] `http://<host>:29501/` 대시보드 로드(단일 PC `--local` 은 `http://localhost:29501/`), AeroAI 섹션에 **Notebook 카드** 보임 (상단 요약 `8 active`).
- [ ] AeroAI: `/ai` 에서 사내 문서 근거 챗 응답(인용 표시).
- [ ] Viewer: 대시보드 Document 섹션 **Viewer 카드** → `/viewer` 에서 로컬 `.md`/`.html` 열기·편집·미리보기·다운로드 동작.
- [ ] Notebook 카드 클릭 → 같은 호스트의 `:8502` Open Notebook 로드(예: `http://<host>:8502/`, 연결 오류 없음).
- [ ] Open Notebook **Settings → Models**: Chat = `gemma4:12b`, Embedding = `nomic-embed-text` 자동 할당 확인.
- [ ] 노트북 생성 → 소스 추가 → Ask/벡터 검색 동작.
- [ ] (LAN 다중 PC) 관리자 권한으로 `scripts\allow_lan_firewall.cmd --with-notebook` 실행 후 다른 PC에서 `http://<this-PC-IP>:29501/` · `:8502` 접속.

---

## 7. 일상 운영

| 작업 | 방법 |
|---|---|
| 기동 / 정지 | `scripts\run_all.bat` / `scripts\stop_all.bat` |
| 뉴스레터·문서 추가 | `_database\*` 에 파일 복사 후 해당 페이지 새로고침 ([`windows-offline.md`](windows-offline.md) §7) |
| 관리자 비밀번호 교체 | `setup_offline.bat` 재실행 (`.env` 는 `.bak` 백업) |
| Open Notebook 데이터 | `D:\AeroOne-bundle\data\` (surrealdb / uploads / sqlite-db). 백업·업그레이드 시 보존 |
| AI 모델 추가/변경 | Ollama 에 모델 적재 후 ON `Models` 화면에서 등록·할당 |

---

## 8. 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| Notebook 카드 클릭 시 `:8502` 연결 안 됨 | Open Notebook 미기동 | `scripts\run_all.bat` 또는 `D:\AeroOne-bundle\3-run.bat` 실행 |
| ON 화면 "Unable to Connect to API Server" | API(:5055) 부팅 전 / API_URL·API_HOST·CORS 불일치 | `3-run.bat` 최신 adapter 로 재실행하고 출력의 `api bind`, `API_URL`, `CORS` 를 확인. `scripts\run_all.bat` 는 `/config` 까지 읽은 뒤 READY 를 표시합니다. 지속되면 `3-run.bat --local` 로 단일 PC 경로를 확인하거나 `--allow-host <IP>` 로 호스트를 고정하세요. |
| ON 챗/임베딩 실패 | Ollama 에 모델 미적재 | `ollama list` 로 `gemma4:12b`·`nomic-embed-text` 확인(§2) |
| AeroAI 연결 불가 | Ollama 미실행 | Ollama 서비스 확인(`:11434`). Document/문서 열람은 Ollama 없이도 동작 |
| 대시보드가 옛 화면(카드 없음) | 브라우저 캐시 | `Ctrl+Shift+R` 강제 새로고침 |
| LAN 다른 PC 접속 불가 | 방화벽 | 관리자 `scripts\allow_lan_firewall.cmd --with-notebook` (로컬 서브넷 한정) |

---

## 9. 보안 주의

- **Open Notebook 은 자체 인증이 없습니다.** `:8502/:5055/:8000` 에 도달하는 LAN 내 누구나 노트북·소스를 열람/조작할 수 있습니다. `scripts\allow_lan_firewall.cmd --with-notebook` 는 `remoteip=LocalSubnet` 로 외부망 도달만 차단합니다. 신뢰할 수 있는 폐쇄망 LAN 안에서만 사용하세요. 단일 PC 사용 시 방화벽 규칙은 불필요합니다.
- AeroOne `/admin/*` 은 `admin_session` 쿠키로 보호됩니다(공개 열람은 의도적 무인증).
- 신원 비대칭·포지셔닝 단일 출처: [`docs/CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) §18.5 / §18.6.
