# 폐쇄망 사용 안내 (AeroOne 1.18.0 — Aero Work 포함)

운영자가 폐쇄망 Windows PC 에서 AeroOne 본체를 반입·설치·실행하고 **Aero Work(로컬 AI 업무 워크스페이스)까지 정상 동작**시키는 **빠른 사용 가이드**입니다. 더 깊은 세부는 [`windows-offline.md`](windows-offline.md), 종합 가이드는 [`../CLOSED_NETWORK_GUIDE.md`](../CLOSED_NETWORK_GUIDE.md) 를 참고하세요.

> **1.18.0 변경 요점**
> - **Aero Work 정식 추가** — 대화 한 줄로 일정·문서(HWPX)·지식 검색을 잇는 폐쇄망 로컬 AI 업무 공간.
> - **Leantime 동거 기능 제외** — 이번 폐쇄망 릴리스에서 Leantime 카드·라우트·co-deploy 스크립트를 뺐습니다. Leantime 반입물이 필요 없습니다.

---

## 0. 준비물 (인터넷 되는 PC 에서 미리 확보)

### 0.1 AeroOne 본체 (필수)

[GitHub Release `1.18.0`](https://github.com/Py-CI-Park/AeroOne/releases/tag/1.18.0) 에서 받습니다.

| 파일 | 용도 | 필수 |
|---|---|---|
| `AeroOne-offline-1.18.0.zip` + `.sha256` | AeroOne 본체(백엔드·프런트·wheel·Node/Python 인스톨러) | ✅ |

무결성 확인: `certutil -hashfile AeroOne-offline-1.18.0.zip SHA256` → `.sha256` 파일 값과 일치.

### 0.2 로컬 AI (Aero Work·AeroAI 사용 시 필수) ⭐

**AeroOne ZIP 에는 AI 모델이 들어 있지 않습니다.** Aero Work 의 업무대화·문서 생성·지식 검색은 **로컬 Ollama + 모델 2개**가 있어야 동작합니다. 인터넷 되는 PC 에서 미리 받아 함께 반입하세요.

| 구성 | 값 | 용도 |
|---|---|---|
| Ollama 설치 파일 | `OllamaSetup.exe`([ollama.com](https://ollama.com/download) 또는 사내 미러) | 로컬 AI 실행기 |
| 대화·합성 모델 | **`gemma4:12b`** (약 7~8GB) | 업무대화·문서 생성·요약·분류 |
| 임베딩 모델 | **`nomic-embed-text`** (약 300MB) | 지식폴더 벡터 검색 |

폐쇄망 반입 방법(둘 중 하나):
- **A. 모델 캐시 통째 복사(권장)**: 인터넷 PC 에서 `ollama pull gemma4:12b` · `ollama pull nomic-embed-text` 후, `%USERPROFILE%\.ollama\models` 폴더 전체를 폐쇄망 PC 의 같은 경로로 복사.
- **B. 사내 Ollama 미러** 가 있으면 폐쇄망에서 `ollama pull` 로 받기.

> AI 없이도 AeroOne 열람 기능(뉴스레터·문서·Civil Aircraft)은 정상 동작합니다. **Aero Work 만 로컬 AI 를 요구**합니다.

→ 준비물을 USB 등 단방향 경로로 폐쇄망 PC 로 반입.

---

## 1. AeroOne 본체 설치·실행

```cmd
:: 1) 압축 해제 → D:\AeroOne\
:: 2) 최초 설치 (한 번만) — 오프라인 wheel/Node 설치 + DB 마이그레이션 + 시드
cd /d D:\AeroOne
setup_offline.bat

:: 3) 실행
start_offline.bat
```

- Python 3.12 / Node 가 없으면 ZIP 안 `offline_assets\installers\` 의 설치 파일을 먼저 실행.
- 기본 접속 = **LAN**(이 PC LAN IP 자동, `0.0.0.0`). 이 PC 전용은 `start_offline.bat --local`.
  - 프런트: `http://<이PC IP>:29501` (또는 `http://localhost:29501`)
  - 백엔드 API: `:18437`
- **관리자 로그인**: 아이디 `admin`, 비밀번호는 `D:\AeroOne\backend\.env` 의 `ADMIN_PASSWORD`(설치 시 랜덤 생성). **최초 로그인 시 비밀번호 변경**을 요구합니다.
- 외부 PC 접속 허용: `scripts\allow_lan_firewall.cmd` (18437/29501, LocalSubnet).
- 헤더/관리자 버전 = **1.18.0**.

---

## 2. 로컬 AI(Ollama) 설치·모델 등록 — Aero Work 필수 ⭐

```cmd
:: 1) Ollama 설치 (관리자 권한)
OllamaSetup.exe

:: 2) 모델 반입 확인 — 0.2-A 로 %USERPROFILE%\.ollama\models 를 복사했다면 아래로 목록 확인
ollama list
::  → gemma4:12b, nomic-embed-text 두 줄이 보이면 정상

:: 3) Ollama 서비스 기동 확인(설치 시 자동 기동). 수동 기동은:
ollama serve
```

- AeroOne 은 **`http://127.0.0.1:11434`** 의 로컬 Ollama 를 호출합니다(폐쇄망 순도 — 외부 SaaS 0).
- 기본 모델: 대화·합성 `gemma4:12b`, 임베딩 `nomic-embed-text`.
- 다른 모델/포트를 쓰려면 `D:\AeroOne\backend\.env` 에 지정:
  ```
  OLLAMA_BASE_URL=http://127.0.0.1:11434
  OLLAMA_DEFAULT_MODEL=gemma4:12b
  OLLAMA_EMBED_MODEL=nomic-embed-text
  ```
- **연결 확인**: AeroOne 로그인 → Aero Work 진입 → 우측 "업무 엔진" 배지가 **정상(gemma4:12b)** 이면 준비 완료. "환경설정" 탭에서도 로컬 AI 연결 상태를 확인합니다.

---

## 3. Aero Work 사용 시작

로그인(admin) 후 대시보드 Development 섹션 **Aero Work** 카드 → 또는 주소창 `/aero-work`.

좌측 7탭:

| 탭 | 하는 일 |
|---|---|
| 🏠 홈 | 오늘의 브리핑(일정·이어서 하기·지식 요약) |
| 💬 업무대화 | 대화 한 줄로 일정·문서·지식·도움말 라우팅(멀티인텐트) + 파일 첨부 |
| 📅 일정 | 월/주/일 캘린더, 사전 알림, 일정 CRUD |
| 📝 문서작성 | 시행문·1페이지·풀버전·이메일·임의형식 → 종이 미리보기 → HWPX 생성(승인형) |
| 📚 내 지식폴더 | 폴더 등록 → 색인 → 키워드/의미 검색, 지식위키(버전 가족), 분류체계 마법사 |
| 🧾 실행기록 | 실행한 작업 타임라인 |
| ⚙️ 환경설정 | 로컬 AI 연결 상태, LLM 프로필(default/local) |

**지식폴더 등록 주의**: "폴더 경로" 는 **AeroOne 백엔드가 접근 가능한 절대 경로**(예: `D:\업무\지식자료`)여야 합니다. 원본은 복사하지 않고 그 자리에서 색인합니다(HWPX·PDF·DOCX·txt/md/html/csv 지원, **구버전 `.hwp` 바이너리는 미지원** — hwpx 로 저장 후 색인).

> **지식폴더 등록 경로 제한(선택, 권장)**: 기본은 어떤 절대경로든 등록 가능합니다. 사용자가 서버의 임의 경로를 등록하지 못하게 하려면 `backend/.env` 에 허용 루트를 지정하세요 — `AERO_WORK_KNOWLEDGE_ROOTS=D:\업무\지식자료,E:\공용자료`. 설정 시 등록 폴더의 실경로(symlink/junction 해석 후)가 허용 루트 안이어야 하며, 밖의 경로는 거부됩니다.

---

## 4. 과거 실수 방지 체크리스트 ⭐ (게시·설치 전 필수 점검)

> 폐쇄망에서 "실수 없이 잘 실행"되도록, 과거에 실제로 겪은 함정을 순서대로 확인하세요.

| # | 과거 실수 | 방지 |
|---|---|---|
| 1 | **Aero Work AI 가 조용히 안 됨** — Ollama/모델 미설치인데 앱만 실행 | §2 순서대로 Ollama + `gemma4:12b` + `nomic-embed-text` 를 먼저 준비. "업무 엔진" 배지가 정상인지 확인 후 사용 |
| 2 | **지식폴더 색인이 비어 있음** — 임베딩 모델(`nomic-embed-text`) 누락 | `ollama list` 에 두 모델 모두 있는지 확인. 없으면 §0.2 로 반입 |
| 3 | `start_offline.bat` 을 `setup_offline.bat` 전에 실행 | 반드시 setup → start 순서. setup 은 최초 1회 |
| 4 | 관리자 비밀번호 모름 | `D:\AeroOne\backend\.env` 의 `ADMIN_PASSWORD`(설치 시 랜덤). 최초 로그인 시 변경 요구 |
| 5 | `APP_ENV` 가 development 로 회귀 | `setup_offline.bat` 는 `APP_ENV=closed_network` 로 고정(secret 강도 검증 ON, secure cookie OFF). `.env` 확인 |
| 6 | 포트 충돌 | AeroOne 18437(API)/29501(프런트), Ollama 11434 고정. 겹치면 `.env`/Ollama 설정으로 조정 |
| 7 | 다른 PC 에서 접속 안 됨 | `scripts\allow_lan_firewall.cmd` 실행(LocalSubnet). `start_offline.bat --allow-host` 와 짝 |
| 8 | 부분 검증 반입물 게시(1.16.3 회귀 재발) | 게시 전 backend 전량 pytest·frontend 전량 vitest 통과 확인(릴리스 게이트). 이 ZIP 은 통과본 |

---

## 5. 자주 겪는 점

| 증상 | 조치 |
|---|---|
| Aero Work "업무 엔진 확인 실패" | Ollama 미기동. `ollama serve` 또는 서비스 재시작. `.ollama\models` 에 두 모델 확인 |
| 업무대화 답변이 느림(첫 응답 수 초) | 로컬 gemma4:12b 최초 로딩 시간. 이후 빨라짐. RAM 16GB 권장 |
| 지식 검색 결과 비어 있음 | 폴더 등록 후 "재색인" 완료(ready) 확인. 임베딩 모델 필요 |
| HWPX 서식이 한컴에서 조금 다름 | 종이 미리보기는 근사치입니다. 파일 구조는 유효하나 한컴 서식 정밀 호환은 한컴 설치 PC 에서 확인 권장(실험적) |
| Office Studio 예제가 안 보임 | 로그인 + 최초 비밀번호 변경 완료 후 표시(예제는 인증 필요) |
| 관리자 비번 모름 | `D:\AeroOne\backend\.env` 의 `ADMIN_PASSWORD` |

---

## 6. 시스템 요구사항 (Aero Work 사용 시)

| 항목 | 사양 |
|---|---|
| OS | Windows 10 / 11 (64bit) |
| 메모리 | 8GB 동작, **로컬 gemma4:12b 구동 시 16GB 권장** |
| 디스크 | AeroOne ~1GB + Ollama·모델 ~10GB |
| 로컬 AI | Ollama + `gemma4:12b` + `nomic-embed-text` (Aero Work·AeroAI 전용) |
| 인터넷 | **불필요**(모델·의존성 전부 반입) |
