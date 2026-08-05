FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY . .
RUN SECRET_KEY=build-only-secret-key-with-more-than-fifty-random-characters-12345 \
    python manage.py collectstatic --noinput --settings=config.settings.production && \
    addgroup --system --gid 10001 app && adduser --system --uid 10001 --ingroup app app && \
    mkdir -p /app/media && chown -R 10001:10001 /app/media

USER app

EXPOSE 8000
