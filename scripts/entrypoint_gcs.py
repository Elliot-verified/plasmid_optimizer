#!/usr/bin/env python3
"""
Copy PepMLM from GCS to a local dir, set PEPMLM_MODEL_PATH, then start the API.
Set PEPMLM_GCS_URI (e.g. gs://bucket/pepmlm-650m) in the environment.
"""
import os
import re
import sys

MODEL_DIR = os.environ.get("PEPMLM_MODEL_PATH", "/tmp/pepmlm")
GCS_URI = os.environ.get("PEPMLM_GCS_URI", "").strip()
PORT = os.environ.get("PORT", "8000")


def main():
    if GCS_URI:
        m = re.match(r"^gs://([^/]+)/(.*)$", GCS_URI)
        if not m:
            print("Invalid PEPMLM_GCS_URI (expected gs://bucket/path)", file=sys.stderr)
            sys.exit(1)
        bucket_name, prefix = m.group(1), m.group(2).rstrip("/")
        if prefix:
            prefix = prefix + "/"
        else:
            prefix = ""

        print(f"Copying model from {GCS_URI} to {MODEL_DIR} ...")
        try:
            from google.cloud import storage
        except ImportError:
            print("Install google-cloud-storage: pip install google-cloud-storage", file=sys.stderr)
            sys.exit(1)

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        if not blobs:
            print(f"No objects found under gs://{bucket_name}/{prefix}", file=sys.stderr)
        else:
            os.makedirs(MODEL_DIR, exist_ok=True)
            for blob in blobs:
                rel = os.path.relpath(blob.name, prefix) if prefix else blob.name
                local_path = os.path.join(MODEL_DIR, rel)
                if blob.name.endswith("/"):
                    continue
                os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
                blob.download_to_filename(local_path)
                print(f"  {blob.name} -> {local_path}")

        os.environ["PEPMLM_MODEL_PATH"] = MODEL_DIR

    # Replace current process with uvicorn
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "api.main:app",
            "--host", "0.0.0.0",
            "--port", PORT,
        ],
    )


if __name__ == "__main__":
    main()
