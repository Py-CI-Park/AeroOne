# Windows / 폐쇄망 실행 가이드

## 배치 파일 구성
| 파일 | 용도 |
|---|---|
| `setup.bat` | 인터넷 가능한 Windows PC에서 개발/사전 설치 |
| `start.bat` | 인터넷 가능한 Windows PC에서 백엔드/프론트 동시 실행 |
| `offline_package.bat` | 현재 리포 + Python wheelhouse + frontend node_modules를 ZIP으로 패키징 |
| `setup_offline.bat` | 폐쇄망 Windows PC에서 오프라인 설치 |
| `start_offline.bat` | 폐쇄망 Windows PC에서 운영 실행 |

## 실행 시 동작
- `start.bat` 와 `start_offline.bat` 는 백엔드/프론트 CMD 창을 먼저 연 뒤, 두 포트(`18437`, `29501`)가 준비되었을 때만 브라우저를 엽니다.
- 두 포트 중 하나라도 이미 사용 중이면 브라우저를 열지 않고 즉시 오류를 출력한 뒤 멈춥니다.
- 브라우저가 열리지 않으면 먼저 launcher 창 메시지를 확인하고, 백엔드/프론트 CMD 창이 열린 경우에는 해당 로그도 함께 확인합니다.

## 권장 순서
1. 인터넷 가능한 Windows PC에서 `setup.bat`
2. 필요 시 `start.bat`로 온라인 환경 검증
3. `offline_package.bat`로 ZIP 생성
4. ZIP을 폐쇄망 PC로 복사 및 압축 해제
5. 폐쇄망 PC에서 `setup_offline.bat`
6. 폐쇄망 PC에서 `start_offline.bat`

## 주의사항
- `Newsletter/output` 폴더가 실제 HTML/PDF 원본입니다. 오프라인 패키지에 함께 포함됩니다.
- `offline_package.bat`는 `frontend/node_modules`와 Python wheelhouse를 함께 넣습니다.
- Python/Node 설치 파일까지 넣고 싶으면 루트의 `offline_installers` 폴더에 미리 넣어 두세요.
- Windows 절대경로를 직접 쓸 경우 `D:/...` 형태를 권장합니다.
