FROM python:3.11-slim

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

# hadolint ignore=DL3025
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
