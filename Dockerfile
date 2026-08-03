FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY xvector /app/xvector
COPY pyxvector /app/pyxvector
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

ENV PYTHONUNBUFFERED=1 \
    XVECTOR_DATA_DIR=/data \
    XVECTOR_LOG_LEVEL=INFO

EXPOSE 19530 18081 18082

CMD ["python", "-m", "xvector"]
