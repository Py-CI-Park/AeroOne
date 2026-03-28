FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1             PYTHONUNBUFFERED=1

COPY backend/requirements.txt backend/requirements-dev.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY storage ./storage
COPY Newsletter ./Newsletter
COPY .env.example ./.env.example

WORKDIR /app/backend

CMD ["sh", "-c", "alembic upgrade head && PYTHONPATH=. python scripts/seed.py && uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-18437}"]
