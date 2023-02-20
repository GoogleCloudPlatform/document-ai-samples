FROM python:3.11

ENV PYTHONUNBUFFERED True

# ./backend/render.py uses <DejaVuSansMono-Bold.ttf>
RUN apt-get update && apt-get install -y fonts-dejavu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
