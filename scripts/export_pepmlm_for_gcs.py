#!/usr/bin/env python3
"""
Download PepMLM-650M from Hugging Face and save to a local directory.
Then upload that directory to GCS, e.g.:

  python scripts/export_pepmlm_for_gcs.py --output ./pepmlm-650m
  gsutil -m cp -r ./pepmlm-650m gs://YOUR_BUCKET/pepmlm-650m

Requires: pip install -e ".[ml]"
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Export PepMLM-650M for GCS upload")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pepmlm-650m"),
        help="Directory to save the model (default: ./pepmlm-650m)",
    )
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    from transformers import AutoModelForMaskedLM, AutoTokenizer

    model_id = "ChatterjeeLab/PepMLM-650M"
    print(f"Downloading {model_id} to {out} ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForMaskedLM.from_pretrained(model_id)
    tokenizer.save_pretrained(out)
    model.save_pretrained(out)
    print(f"Saved to {out}. Upload to GCS with:")
    print(f"  gsutil -m cp -r {out} gs://YOUR_BUCKET/pepmlm-650m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
