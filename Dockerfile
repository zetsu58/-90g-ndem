FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY viral_futbol /app/viral_futbol
COPY bamloop /app/bamloop
COPY production /app/production
COPY scripts /app/scripts
COPY assets /app/assets
COPY remotion /app/remotion
RUN cd /app/remotion && npm install --omit=dev
RUN python -m compileall -q /app/viral_futbol /app/bamloop /app/production /app/scripts \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core espeak-ng chromium \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app
ENV PORT=8080 NEWS_AUTOSTART_WORKER=true PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "viral_futbol.web"]

