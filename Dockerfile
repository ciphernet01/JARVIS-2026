FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_PORT=8000 \
    JARVIS_DEBUG=0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["waitress-serve", "--listen=0.0.0.0:8000", "wsgi:application"]