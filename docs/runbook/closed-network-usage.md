# 폐쇄망 사용 안내 (AeroOne 1.16.0 + Leantime)

운영자가 폐쇄망 Windows PC 에서 AeroOne 본체와(선택적으로) Leantime 을 반입·설치·실행·연동하는 **빠른 사용 가이드**입니다. 더 깊은 세부는 [`closed-network-install-manual.md`](closed-network-install-manual.md), [`windows-offline.md`](windows-offline.md), [`leantime-codeploy.md`](leantime-codeploy.md) 를 참고하세요.

---

## 0. 준비물 (인터넷 되는 PC)

[GitHub Release `1.16.0`](https://github.com/Py-CI-Park/AeroOne/releases/tag/1.16.0) 에서 받습니다.

| 파일 | 용도 | 필수 |
|---|---|---|
| `AeroOne-offline-1.16.0.zip` + `.sha256` | AeroOne 본체 | ✅ 필수 |
| `AeroOne-Leantime-Stack-v3.9.8-*.zip` + `.sha256` | Leantime 실기동 포터블 스택 | 선택 |

무결성 확인:

```cmd
certutil -hashfile AeroOne-offline-1.16.0.zip SHA256
:: → b44d11b02327663c7af787a45197a25908c91545f182d6d8a87ca7d16b5ccf7f 와 일치
certutil -hashfile AeroOne-Leantime-Stack-v3.9.8-*.zip SHA256
:: → f6a30394c53eee082088311f1253d6f87d9daa02bcd55411b78c440cf4bd9fab 와 일치
```

→ 두 ZIP 을 USB 등 단방향 경로로 폐쇄망 PC 로 반입.

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

---

## 2. Leantime 스택 설치·실행 (선택)

AeroOne 폴더의 **형제 폴더**로 풀면 AeroOne 이 자동 감지합니다.

```cmd
:: 1) 압축 해제 → D:\AeroOne-Leantime-Stack\   (AeroOne 과 같은 상위 폴더)
:: 2) 최초 설치 (한 번만) — 포터블 MariaDB init + 스키마 + 관리자 생성
cd /d D:\AeroOne-Leantime-Stack
setup-leantime-stack.bat

:: 3) 실행 / 중지
start-leantime-stack.bat
stop-leantime-stack.bat
```

- 구성: 포터블 **PHP 8.3.32 + MariaDB 11.4.8(127.0.0.1:3307) + Leantime v3.9.8** — 폐쇄망 무설치.
- Leantime 접속: `http://localhost:8081`
- **Leantime 관리자(기본)**: `admin@aeroone.local` / `AeroOneLean2026!`
  - 설치 전 변경: `set LEANTIME_ADMIN_EMAIL=...` / `set LEANTIME_ADMIN_PASSWORD=...` 후 `setup-leantime-stack.bat`
- 포트 변경(선택): `set LEANTIME_PORT=8081` / `set LEANTIME_DB_PORT=3307`
- 외부 접속 허용: `scripts\leantime\allow-leantime-firewall.cmd`
- 완전 초기화: 스택의 `data\` 폴더 삭제 후 `setup-leantime-stack.bat` 재실행.

---

## 3. AeroOne ↔ Leantime 연동

1. `start-leantime-stack.bat` 로 Leantime(8081)을 먼저 기동.
2. AeroOne 로그인 → **Development 섹션 Leantime 카드** → 상태 배지 **"준비됨"** + "열기" 활성.
3. AeroOne 은 `http://127.0.0.1:8081` 을 **HTTP 로만 감지**해 연동합니다 — **세션·쿠키·DB 미공유**(각각 독립 로그인). 감지 대상은 `AEROONE_LEANTIME_HEALTH_URL` 로 재정의.
4. AeroOne `scripts\leantime\start-leantime.bat` 은 형제 폴더 `..\AeroOne-Leantime-Stack` 을 자동 감지·위임합니다. 다른 위치면 `set AEROONE_LEANTIME_STACK=<경로>`.

---

## 4. 1.16.0 사용 시 참고

- **대시보드 섹션**: AeroAI·Notebook·Open WebUI = **AI**, Ladder 등 = **ETC**.
- **Civil Aircraft Spec Catalog**: v1.7 인터랙티브 대시보드(포털/백과/비교/출처)로 교체 — 카드에서 바로 탐색 + "새 창으로 열기".
- **관리자 → 시스템 탭**: OpenAI 호환 provider(URL·API 키, write-only) 설정.
- 헤더/관리자 버전 = **1.16.0**.

---

## 5. 자주 겪는 점

| 증상 | 조치 |
|---|---|
| Office Studio 예제가 안 보임 | **로그인 + 최초 비밀번호 변경 완료** 후 표시(예제는 인증 필요). |
| Leantime 카드 "확인 실패" | `start-leantime-stack.bat` 로 스택을 먼저 기동. |
| 관리자 비번 모름 | `D:\AeroOne\backend\.env` 의 `ADMIN_PASSWORD`. |
| 포트 충돌 | AeroOne 18437/29501, Leantime 8081/3307 고정 — 겹치면 위 env 로 조정. |

> Leantime 스택은 AGPL(Leantime)/GPL(MariaDB) 바이너리로, 본체 ZIP 과 **분리된 선택 반입물**입니다. 필요 없으면 AeroOne 본체만 반입해도 정상 동작합니다.
