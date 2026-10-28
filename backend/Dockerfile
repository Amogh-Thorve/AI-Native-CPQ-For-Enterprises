# Backend API. Build context is the repository root (the code imports `backend.app.*`).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY scripts scripts

EXPOSE 8000

# Migrate, then serve. Runs from the repo root so `static/` and `storage/` resolve as in local dev.
CMD ["sh", "-c", "cd backend && python -m alembic upgrade head && cd /app && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
