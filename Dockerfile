FROM python:3.11-slim

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
