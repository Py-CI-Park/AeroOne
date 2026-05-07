# offline_installers/

이 폴더는 폐쇄망 PC 에 Python / Node 가 설치되어 있지 않을 때를 대비해
**인터넷이 가능한 본 PC 에서 미리 다운로드해 둘 인스톨러 보관소** 입니다.

`offline_package.bat` 실행 시 본 폴더 내용물이 ZIP 안 `offline_assets/installers/`
로 그대로 복사됩니다. 폐쇄망 PC 에서는 압축 해제 후 다음 두 파일을 차례로
실행하면 `setup_offline.bat` 사전 점검을 통과합니다.

```cmd
offline_assets\installers\python-3.12.x-amd64.exe
offline_assets\installers\node-v20.x.x-x64.msi
```

---

## 다운로드해야 할 두 개

| 파일 | 출처 | 비고 |
|---|---|---|
| `python-3.12.7-amd64.exe` | https://www.python.org/downloads/windows/ | "Windows installer (64-bit)". 설치 시 **"Add python.exe to PATH"** 반드시 체크 |
| `node-v20.18.0-x64.msi` | https://nodejs.org/en/download | LTS 버전 (Windows Installer .msi 64-bit). 설치 시 **"Add to PATH"** 반드시 체크 |

> 버전 숫자는 다운로드 시점의 최신 LTS / patch 버전으로 자유롭게 교체 가능합니다.
> 단, Python 은 **3.12.x** 계열 (FastAPI 의존성 호환), Node 는 **20.x LTS** 권장.

---

## 다운로드 후 절차

```cmd
:: 1. 본 폴더에 두 인스톨러를 배치
::    D:\Chanil_Park\Project\Programming\AeroOne\offline_installers\python-3.12.7-amd64.exe
::    D:\Chanil_Park\Project\Programming\AeroOne\offline_installers\node-v20.18.0-x64.msi

:: 2. 패키징
cd D:\Chanil_Park\Project\Programming\AeroOne
offline_package.bat

:: 3. 산출물 확인
dir dist\AeroOne-offline-*.zip
```

---

## 본 README 자체는 ZIP 에 포함되지 않습니다

`offline_package.bat` 의 robocopy 가 본 폴더의 모든 내용을 ZIP 안 `offline_assets/installers/`
로 복사하지만, README.md 는 운영자에게 같이 전달돼도 무해합니다 (참고용).
실제로 폐쇄망 PC 의 운영자가 보는 안내는 ZIP 안 `offline_assets/README-OFFLINE.txt`
가 자동 생성되어 들어 있으므로 별 고지 불필요.
