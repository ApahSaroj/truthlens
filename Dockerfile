# Hosted web app (e.g. a free Hugging Face Space with the Docker SDK, Render, Railway, Fly.io). See HOSTING.md.
# One process on purpose: running checks and their results live in memory only (never on disk), so a second worker
# would not see the first one's jobs. Scale by running more containers behind a sticky load balancer.
FROM python:3.12-slim
RUN useradd -m -u 1000 app && mkdir -p /data && chown app /data
WORKDIR /app
COPY --chown=app . /app
RUN pip install --no-cache-dir -e ".[api]"
USER app
# Public mode: per-IP rate limits, Deep-check limits, a cap on checks running at once, corrections not stored.
# /data holds the shared official-data store (`truthlens sync`) and the shared live-answer cache; mount persistent
# storage there if the host offers it (Hugging Face Spaces: /data), otherwise it is rebuilt after each restart.
ENV PORT=7860 \
    TRUTHLENS_PUBLIC=1 \
    TRUTHLENS_TRUST_PROXY=1 \
    TRUTHLENS_SYNC_ON_START=1 \
    TRUTHLENS_DATA_DIR=/data \
    TRUTHLENS_CACHE=/data/cache \
    TRUTHLENS_RATE_CHECKS=20 \
    TRUTHLENS_RATE_DEEP=5 \
    TRUTHLENS_MAX_JOBS=4 \
    TRUTHLENS_JOB_TTL=1800 \
    TRUTHLENS_LIVE_CACHE_MB=300
# Optional: refresh the official data while building the image (needs internet at build time):
#   docker build --build-arg SYNC_AT_BUILD=1 .
ARG SYNC_AT_BUILD=0
RUN if [ "$SYNC_AT_BUILD" = "1" ]; then truthlens sync || echo "sync at build failed; it will run at startup"; fi
EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=4)" "http://127.0.0.1:${PORT}/health" || exit 1
CMD ["sh", "-c", "uvicorn truthlens.api:app --host 0.0.0.0 --port ${PORT} --workers 1 --no-access-log"]
