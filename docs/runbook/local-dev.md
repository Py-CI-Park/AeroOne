# AeroOne 로컬 실행 가이드

## 1. 환경 변수 준비
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

## 3. 프론트엔드 로컬 실행
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
- 기본 관리자 계정: `.env` 의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`
