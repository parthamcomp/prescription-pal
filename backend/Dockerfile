FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Run migrations, then start the API.
# --proxy-headers + --forwarded-allow-ips='*' trust Render's edge proxy's
# X-Forwarded-Proto so HTTPSRedirectMiddleware sees the real scheme instead
# of always seeing plain HTTP and redirecting every request to itself.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
