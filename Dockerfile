# FastAPI backend image. The Next.js frontend has its own Dockerfile in web/.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
COPY vendor ./vendor
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend ./backend
COPY api ./api

# Non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
