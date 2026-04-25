"""Modal deployment for PepMLM-650M peptide binder generation.

Hosts a single POST endpoint that wraps PepMLM. Weights are cached in a Modal
Volume so cold starts after the first download skip the ~1.3 GB model fetch.

Deploy:
    pip install modal
    modal token new                # one-time auth (opens a browser)
    modal deploy app.py

Modal will print the public endpoint URL on success — copy it into vercel.json
as the destination of the /generate-binder rewrite. See HOSTING.md.

Cost (free Modal credits cover this for "handful of users at a time"):
- Cold start, first ever call: ~60s (image pull + model download)
- Cold start, after volume populated: ~10-15s (load weights from volume)
- Warm call (CPU): ~20-30s for 4 peptides of length 15
- Idle: $0 (scale-to-zero after `scaledown_window`)
"""

from __future__ import annotations

import re
from typing import List

import modal
from pydantic import BaseModel, Field

MODEL_ID = "ChatterjeeLab/PepMLM-650M"
CACHE_DIR = "/root/.cache/huggingface"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.0",
        "transformers==4.44.2",
        "accelerate==0.33.0",
        "fastapi[standard]==0.115.0",
    )
)

volume = modal.Volume.from_name("pepmlm-weights", create_if_missing=True)
app = modal.App("plasmid-optimizer-pepmlm")


class GenerateBinderBody(BaseModel):
    target_protein_sequence: str
    peptide_length: int = Field(default=15, ge=5, le=50)
    num_binders: int = Field(default=4, ge=1, le=20)
    top_k: int = Field(default=3, ge=1, le=20)
    temperature: float = Field(default=1.0, ge=0.01, le=10.0)


@app.cls(
    image=image,
    volumes={CACHE_DIR: volume},
    timeout=600,
    scaledown_window=300,
    max_containers=2,
)
class PepMLM:
    @modal.enter()
    def load(self):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=CACHE_DIR)
        self.model = (
            AutoModelForMaskedLM.from_pretrained(MODEL_ID, cache_dir=CACHE_DIR)
            .to(self.device)
            .eval()
        )
        try:
            volume.commit()
        except Exception:
            pass

    @modal.fastapi_endpoint(method="POST", docs=False)
    def generate(self, body: GenerateBinderBody) -> dict:
        target = re.sub(r"\s+", "", body.target_protein_sequence).upper()
        if not target:
            return {"peptides": []}
        peptides = self._generate(
            target=target,
            peptide_length=body.peptide_length,
            num_binders=body.num_binders,
            top_k=body.top_k,
            temperature=max(1e-6, body.temperature),
        )
        return {"peptides": peptides}

    def _generate(self, target, peptide_length, num_binders, top_k, temperature) -> List[str]:
        import torch
        from torch.distributions.categorical import Categorical

        mask_token = self.tokenizer.mask_token
        input_sequence = target + (mask_token * peptide_length)

        binders: List[str] = []
        for _ in range(num_binders):
            inputs = self.tokenizer(input_sequence, return_tensors="pt").to(self.device)
            with torch.no_grad():
                logits = self.model(**inputs).logits
            mask_positions = (inputs["input_ids"] == self.tokenizer.mask_token_id).nonzero(as_tuple=True)[1]
            logits_at_masks = logits[0, mask_positions]
            k = min(max(1, top_k), logits_at_masks.size(-1))
            top_k_logits, top_k_indices = logits_at_masks.topk(k, dim=-1)
            probs = torch.nn.functional.softmax(top_k_logits / temperature, dim=-1)
            sampled = Categorical(probs).sample()
            predicted_ids = top_k_indices.gather(-1, sampled.unsqueeze(-1)).squeeze(-1)
            peptide = self.tokenizer.decode(predicted_ids, skip_special_tokens=True)
            peptide = re.sub(r"\s+", "", peptide).upper()
            if peptide and all(c in "ACDEFGHIKLMNPQRSTVWY" for c in peptide):
                binders.append(peptide)
        return binders if binders else [""] * num_binders
