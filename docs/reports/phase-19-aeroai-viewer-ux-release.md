# 단계 19 — AeroAI/Viewer UX 강화 + Open Notebook 동거 릴리즈

- 버전: `1.7.0`
- 날짜: 2026-06-26
- 성격: minor — 기존 AeroAI/Viewer 사용자 표면의 기능 강화와 Open Notebook co-deploy 릴리즈 절차 정리
- 기준 계획: `.gjc/plans/ralplan/2026-06-18-aeroai-viewer-ux/pending-approval.md`

---

## 1. 배경

1.6.x 에서 AeroAI, Viewer, Open Notebook 동거 배포는 작동했지만 현장 확인 중 세 가지 사용성 요구가 남아 있었다.

- AeroAI 오른쪽 HTML 본문 검색 패널이 모니터 높이에 맞지 않거나 페이지 전체 스크롤을 유발할 수 있었다.
- AI 답변은 Markdown 구조를 가진 텍스트인데 화면에서는 충분히 읽기 좋게 렌더링되지 않았고, 원문 복사와 렌더링 표시의 경계가 명확해야 했다.
- Viewer 와 AeroAI 인용 미리보기는 더 큰 화면, 집중 보기, 전체화면 확인이 필요했다.
- Open Notebook 은 별도 번들이므로 AeroOne 릴리즈와 함께 어떤 파일을 받아 폐쇄망에 가져가야 하는지 운영자 안내가 한 자리에서 보여야 했다.

따라서 1.7.0 은 기능 추가와 운영 문서화를 함께 묶은 minor 릴리즈로 정리한다.

---

## 2. 구현 요약

### 2.1 AeroAI

- `/ai` 3분할 워크스페이스의 높이 계산을 모니터 기준으로 재조정했다.
  - 대화 목록, 중앙 답변 패널, 오른쪽 HTML 본문 검색 패널 모두 `calc(100dvh - 176px)` 기준으로 화면 안에 들어오도록 맞췄다.
  - 오른쪽 HTML 본문 검색 패널은 `overflow-y-auto` / `overscroll-contain` 으로 긴 검색 결과를 패널 내부에서 스크롤한다.
- AI 답변 Markdown 렌더러를 프론트엔드 내부 구현으로 추가했다.
  - heading, paragraph, blockquote, ordered/unordered/task list, fenced code, table, rule, inline code/link/bold/italic 을 지원한다.
  - HTML 태그와 위험 링크는 실행하지 않는다.
  - 허용 링크는 `http`, `https`, `mailto`, `/...`, `#...` 로 제한하고 `javascript:` 및 protocol-relative URL 은 링크로 만들지 않는다.
- 복사 버튼은 렌더링 결과가 아니라 `message.content` 원문을 클립보드에 쓴다.
- HTML 본문 검색 결과는 새 탭으로 연다.
  - `target="_blank"`, `rel="noopener noreferrer"` 를 사용한다.
  - API payload 의 `navigation_url` 은 `/documents`, `/reports/civil-aircraft`, `/nsa` 계열 same-origin viewer 경로만 허용한다.

### 2.2 AeroAI 인용 미리보기

- 인용 미리보기 iframe 을 크게 조정했다.
- `전체 보기` / `패널로 보기` 토글을 추가했다.
- 미리보기 iframe 은 계속 빈 `sandbox` 로 표시해 스크립트와 동일출처 권한을 차단한다.

### 2.3 Viewer

- Viewer 화면에 보기 모드를 추가했다.
  - `편집+미리보기`
  - `미리보기 집중`
  - `전체화면 미리보기`
- 전체화면 미리보기는 같은 렌더 결과를 별도 dialog 영역의 빈 `sandbox` iframe 으로 보여준다.
- 렌더 프록시가 비정상 payload 를 반환하면 사용자가 볼 수 있는 오류로 처리하고 오래된 preview 를 지운다.

### 2.4 도움말/릴리즈 문서

- 헤더 버전 팝업 changelog 에 1.7.0 항목을 추가했다.
- README, CLOSED_NETWORK_GUIDE, closed-network-install-manual, open-notebook-airgap, docs/INDEX, reports/INDEX 를 1.7.0 기준으로 갱신했다.
- 폐쇄망 반입물은 다음 4개로 명문화했다.
  1. `AeroOne-offline-1.7.0-YYYYMMDD-HHMMSS.zip`
  2. `AeroOne-bundle.zip`
  3. Ollama 모델 폴더 `%USERPROFILE%\.ollama\models\manifests`, `blobs`
  4. 필요 시 `OllamaSetup.exe`

---

## 3. 운영자 사용 절차

### 3.1 온라인 PC

```cmd
:: AeroOne ZIP
cd D:\AeroOne-source
offline_package.bat

:: Open Notebook ZIP
cd D:\open-notebook\airgap
1-online-package.bat

:: 모델 사전 적재
ollama pull gemma4:12b
ollama pull nomic-embed-text
```

### 3.2 폐쇄망 PC

```cmd
:: 권장 배치
D:\AeroOne\
D:\AeroOne-bundle\

:: Ollama 설치 후 모델 폴더 복사
%USERPROFILE%\.ollama\models\manifests
%USERPROFILE%\.ollama\models\blobs

:: AeroOne 설치
cd D:\AeroOne
setup_offline.bat

:: Open Notebook 설치
cd D:\AeroOne-bundle
2-airgap-install.bat

:: 함께 기동
cd D:\AeroOne
scripts\run_all.bat
```

단일 PC에서만 검증할 때는 `scripts\run_all.bat --local` 을 사용한다. LAN 운영은 기본 실행 또는 `--allow-host=<IP>` 를 사용하고, 다른 PC 접속이 필요하면 관리자 권한으로 `scripts\allow_lan_firewall.cmd --with-notebook` 를 실행한다.

---

## 4. 검증 결과

### 4.1 자동 검증

| 명령 | 결과 |
|---|---|
| `cd frontend && npm run typecheck` | 통과 |
| `cd frontend && npm test` | 47 files / 203 tests 통과 |
| `cd frontend && npm run build` | 통과 |
| `cd backend && .venv\Scripts\python.exe -m pytest tests -q` | 175 passed |
| `cmd /d /c "scripts\run_all.bat --dry-run --on-bundle ..\AeroOne-bundle --local"` | 통과 |

### 4.2 브라우저 스모크

| 표면 | 확인 |
|---|---|
| AeroAI `/ai` | 상태 `AeroAI 준비됨`, chat API 정상 응답, HTML 본문 검색 3건, 새 탭 링크 target/rel, console/page error 없음 |
| AeroAI layout | 1440x900 기준 페이지 scrollHeight 900, HTML 검색 패널 bottom 872, 긴 결과 stress 에서 페이지 전체가 아닌 패널 내부 스크롤 |
| Viewer `/viewer` | Markdown 파일 로드, 렌더 iframe `sandbox=""`, 미리보기 집중 에디터 숨김, 전체화면 dialog/iframe 표시, console/page error 없음 |
| Open Notebook `:8502` | Frontend `/notebooks`, API `:5055/health`, `/config`, 주요 메뉴 라우팅, Models 화면 `gemma4:12b` + `nomic-embed-text` 확인 |

---

## 5. 비범위와 주의

- Open Notebook 자체 인증은 여전히 없다. LAN 에 열면 `:8502/:5055/:8000` 에 도달 가능한 사용자가 노트북과 소스를 조작할 수 있다. 단일 PC 사용은 `--local`, LAN 사용은 신뢰된 폐쇄망과 `allow_lan_firewall.cmd --with-notebook` 전제가 필요하다.
- Podcast 페이지는 기본적으로 열리지만, TTS/STT 또는 podcast profile 모델 설정이 비어 있으면 `Setup required` 안내가 보인다. 이는 Open Notebook 설정 상태이며 AeroOne/Open Notebook 기본 co-deploy 장애는 아니다.
- AeroOne ZIP 은 Open Notebook 번들을 포함하지 않는다. 두 ZIP 은 분리 릴리즈 asset 으로 함께 반입해야 한다.

---

## 6. 후속 후보

- Open Notebook podcast 프로필 기본 모델까지 자동 할당할지 검토.
- AeroAI Markdown 렌더러가 필요한 추가 문법(각주, 정의 목록 등)이 생기면 제한적으로 확장.
- 운영자용 릴리즈 asset 체크섬 검증 스크립트 추가.
