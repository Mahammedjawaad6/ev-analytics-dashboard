FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EV_DATA_FILE=/data/ev-data.csv \
    EV_OUTPUT_DIR=/output

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-spark.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-spark.txt

COPY src/ ./src/
COPY dashboard.py ./
COPY tests/ ./tests/

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /output \
    && chown -R appuser:appuser /app /output

USER appuser

ENTRYPOINT ["spark-submit", "--master", "local[*]", "/app/src/ev_analytics.py"]
