# Plasmid Optimizer API + optional PepMLM (load from GCS at runtime via PEPMLM_GCS_URI).
# Build: docker build -t plasmid-optimizer .
# Run:   docker run -p 8000:8000 -e PEPMLM_GCS_URI=gs://plasmidgo/pepmlm-650m plasmid-optimizer

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .
# Install torch first (largest dependency) to reduce peak memory during build
RUN pip install --no-cache-dir "torch>=2.0"
RUN pip install --no-cache-dir "transformers>=4.30" "accelerate>=0.20" google-cloud-storage \
    && pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["python", "scripts/entrypoint_gcs.py"]
