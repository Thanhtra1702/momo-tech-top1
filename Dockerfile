# Giai đoạn 1: build frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Giai đoạn 2: backend phục vụ cả frontend đã build
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /srv
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY backend/agents ./backend/agents
COPY --from=web /web/dist ./frontend_dist
RUN mkdir -p /srv/backend/data && chown -R app:app /srv/backend/data
ENV FRONTEND_DIR=/srv/frontend_dist DB_PATH=/srv/backend/data/app.db APP_ENV=production
USER app
WORKDIR /srv/backend
EXPOSE 8000
# Danh mục mô phỏng được sinh lại khi khởi động nếu DB trống hoặc sắp hết dữ liệu tương lai.
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
