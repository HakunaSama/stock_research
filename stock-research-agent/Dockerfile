# Backend image — FastAPI webapp wrapping the ODR research engine.
# The engine is stdlib-only; we add just the web/serving deps (requirements.txt).
FROM python:3.11-slim

# tini for clean signal handling of the uvicorn + worker threads.
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code (engine + vendored stocksdk + webapp + serve.py helpers + seed script).
COPY . .

# Data dir holds the SQLite DB and run artifacts; mounted as a volume in compose.
ENV STOCK_DATA_DIR=/data \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/docker-entrypoint.sh"]
