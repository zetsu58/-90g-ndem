FROM python:3.12-slim
WORKDIR /app
COPY viral_futbol /app/viral_futbol
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app:app /app /data
USER app
CMD ["python", "-m", "viral_futbol.service"]
