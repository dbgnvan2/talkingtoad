# v2.3 M0.7 — Container image for the TalkingToad backend.
#
# Target host: Railway. Anywhere that runs container images will work
# (Render, Fly.io, Docker on a VM). Vercel is NOT a target — the backend
# uses asyncio.BackgroundTasks which doesn't survive serverless function
# freezes; long-lived container is required.

# Python 3.11+ matches our local dev environment and is the lowest version
# that supports the modern typing annotations we use (X | Y, Self, etc.).
FROM python:3.11-slim AS base

# Bake in some sensible defaults — no .pyc files, unbuffered stdout for
# real-time logs in Railway's log stream.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages needed for the Python deps that compile native bits:
# - lxml needs libxml2 / libxslt headers
# - Pillow needs jpeg/zlib for JPEG/PNG decoding
# - piexif is pure-python but Pillow's image manipulation needs them
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer caches across code changes.
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# R7: Playwright + Chromium enable the JS-render / cloaking / UA-differ GEO
# checks (api/services/js_renderer.py). Adds ~400MB (chromium + OS deps). The
# renderer degrades gracefully when absent, so this layer is only required to
# ENABLE those three checks in production; comment it out to keep the image
# small if you don't need them.
RUN pip install "playwright>=1.40,<2" \
    && playwright install --with-deps chromium

# Copy the application code. Keeping this last keeps the dep-install layer
# cached between most builds.
COPY api /app/api

# Run as non-root for safety. Railway runs the entrypoint as whatever user
# the image specifies; uid 10001 avoids colliding with system uids.
RUN groupadd --system --gid 10001 toad \
    && useradd  --system --uid 10001 --gid toad toad \
    && chown -R toad:toad /app
USER toad

# Container exposes whatever port Railway assigns at runtime via $PORT.
# Default to 8000 for local docker-run testing.
ENV PORT=8000
EXPOSE 8000

# Health probe matches the existing /api/health endpoint (which is on the
# public_router and intentionally requires no auth).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/api/health').read()" || exit 1

# Use uvicorn directly. Railway expects the container to bind to 0.0.0.0:$PORT.
# --proxy-headers because Railway terminates TLS at its edge and forwards
# X-Forwarded-* — required so request.url.scheme reports https correctly.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
