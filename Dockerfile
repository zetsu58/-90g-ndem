FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY viral_futbol /app/viral_futbol
COPY scripts /app/scripts
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app
ENV PORT=8080 NEWS_AUTOSTART_WORKER=true
EXPOSE 8080
CMD ["python", "-m", "viral_futbol.web"]
