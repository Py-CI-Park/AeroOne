FROM node:22-alpine

WORKDIR /app

COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install

COPY frontend ./

CMD ["sh", "-c", "npm run dev -- --hostname 0.0.0.0 --port ${FRONTEND_PORT:-29501}"]
