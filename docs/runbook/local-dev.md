# AeroOne 로컬 개발 실행 가이드

## 1. 환경 변수 준비

프로젝트 루트에서 `.env.example`을 복사해 `.env`를 만듭니다.

```bash
cp .env.example .env
```

## 2. 백엔드 로컬 실행

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
PYTHONPATH=. python scripts/seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 18437
```

## 3. 프런트엔드 로컬 실행

```bash
cd frontend
npm install
npm run dev
```

## 4. Docker Compose 실행

```bash
docker compose up --build
```

## 5. 기본 확인

- Public 목록: `http://localhost:29501/newsletters`
- Login: `http://localhost:29501/login`
- Backend health: `http://localhost:18437/api/v1/health`
- 기본 관리자 계정: `.env`의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`

## 6. Worktree에서 실행할 때 주의할 점

`git worktree`는 **추적되는 파일만** 새 작업 디렉터리로 가져옵니다.  
다음 항목들은 기본적으로 ignore 대상이라 worktree를 새로 만들면 자동으로 복제되지 않을 수 있습니다.

- `backend/.venv`
- `frontend/node_modules`
- `backend/data/aeroone.db`
- `Newsletter/output`

이 상태에서 worktree에서 바로 `start.bat` 또는 backend/frontend를 실행하면 다음과 같은 문제가 생길 수 있습니다.

- 백엔드 가상환경을 찾지 못해 backend startup 실패
- 프런트 의존성을 찾지 못해 frontend startup 실패
- `backend/data/aeroone.db`가 비어 새로 생성되어 `no such table: newsletters` 발생
- `Newsletter/output`가 비어 있어 `/api/v1/newsletters/{id}/content/html` 또는 PDF download가 `500` 발생

### 권장 방법

worktree에서 실제 런타임 검증을 할 때는 아래 네 자원을 **루트 저장소의 정상 상태와 연결**한 뒤 실행하는 것을 권장합니다.

- `backend/.venv`
- `frontend/node_modules`
- `backend/data`
- `Newsletter/output`

Windows에서는 junction(`mklink /J`)을 쓰는 방식이 가장 간단합니다.

예시:

```powershell
cmd /c mklink /J ".worktrees\\<worktree-name>\\backend\\.venv" "backend\\.venv"
cmd /c mklink /J ".worktrees\\<worktree-name>\\frontend\\node_modules" "frontend\\node_modules"
cmd /c mklink /J ".worktrees\\<worktree-name>\\backend\\data" "backend\\data"
cmd /c mklink /J ".worktrees\\<worktree-name>\\Newsletter\\output" "Newsletter\\output"
```

### 최소 확인 항목

worktree에서 런타임을 검증할 때는 아래를 먼저 확인합니다.

```powershell
Test-Path .\backend\.venv\Scripts\python.exe
Test-Path .\frontend\node_modules
Test-Path .\backend\data\aeroone.db
Test-Path .\Newsletter\output
```

모두 `True`여야 실제 실행 검증 결과를 앱 코드 문제로 해석할 수 있습니다.
