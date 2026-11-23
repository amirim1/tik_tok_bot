# Базовый образ по digest: сборка воспроизводима, digest = tag python:3.12-slim на 2026-11-23.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin botuser \
    && mkdir -p /app/temp_videos \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"]
