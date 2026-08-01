# Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY kb-web/frontend/package.json kb-web/frontend/package-lock.json* ./
RUN npm install
COPY kb-web/frontend/ ./
RUN npm run build

# Python backend
FROM python:3.11-slim
WORKDIR /app

COPY kb-web/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY kb-web/backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./backend/frontend_dist

ENV PYTHONPATH=/app/backend
ENV PORT=8080
EXPOSE 8080

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
