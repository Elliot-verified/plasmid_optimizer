#!/bin/sh
# Copy PepMLM from GCS to local dir, then start the API.
# Set PEPMLM_GCS_URI (e.g. gs://bucket/pepmlm-650m) and optionally PEPMLM_MODEL_PATH (default /tmp/pepmlm).

set -e
MODEL_DIR="${PEPMLM_MODEL_PATH:-/tmp/pepmlm}"
if [ -n "$PEPMLM_GCS_URI" ]; then
  echo "Copying model from $PEPMLM_GCS_URI to $MODEL_DIR ..."
  mkdir -p "$MODEL_DIR"
  gsutil -m cp -r "$PEPMLM_GCS_URI"/* "$MODEL_DIR/" || true
  export PEPMLM_MODEL_PATH="$MODEL_DIR"
fi
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
