FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Nicht als root laufen lassen.
RUN useradd --create-home --uid 1000 botuser \
 && mkdir -p /app/logs && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-u", "main.py"]
