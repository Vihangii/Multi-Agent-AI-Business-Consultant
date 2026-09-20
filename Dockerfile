# Single image serving either the FastAPI backend or the Streamlit frontend,
# selected by the command in docker-compose.yml.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-streamlit.txt ./
COPY vendor ./vendor
RUN pip install --upgrade pip && pip install -r requirements-streamlit.txt

COPY backend ./backend
COPY frontend ./frontend

# Non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501

# Default: backend. Overridden for the frontend service in docker-compose.yml.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
