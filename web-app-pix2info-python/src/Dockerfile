FROM python:3.11-slim

# Create a non-root user to run the application
RUN adduser --system --group --disabled-password appuser
USER appuser

ENV PYTHONUNBUFFERED True

# backend/render.py uses <DejaVuSansMono-Bold.ttf>
RUN apt-get update \
  && apt-get install --no-install-recommends -y fonts-dejavu=2.37-2 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD curl --fail http://localhost:$PORT/ || exit 1

# hadolint ignore=DL3025
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
