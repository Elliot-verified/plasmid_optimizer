"""PepMLM: generate peptide binders for a target protein sequence (Hugging Face ChatterjeeLab/PepMLM-650M)."""

from __future__ import annotations

import os
import re
from typing import List

HF_MODEL_ID = "ChatterjeeLab/PepMLM-650M"
_pepmlm_model = None
_pepmlm_tokenizer = None


def _get_model_path() -> str | None:
    """Local path if set via PEPMLM_MODEL_PATH (e.g. after syncing from GCS)."""
    path = os.environ.get("PEPMLM_MODEL_PATH", "").strip()
    if path and os.path.isdir(path):
        return path
    return None


def _get_model_and_tokenizer():
    global _pepmlm_model, _pepmlm_tokenizer
    if _pepmlm_model is None:
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model_path = _get_model_path()
        pretrained = model_path if model_path else HF_MODEL_ID
        _pepmlm_tokenizer = AutoTokenizer.from_pretrained(pretrained)
        _pepmlm_model = AutoModelForMaskedLM.from_pretrained(pretrained).to(device)
        _pepmlm_model.eval()
    return _pepmlm_model, _pepmlm_tokenizer


def _normalize_sequence(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def generate_binders(
    target_protein_sequence: str,
    peptide_length: int = 15,
    num_binders: int = 4,
    top_k: int = 3,
    temperature: float = 1.0,
) -> List[str]:
    """
    Generate novel peptide binder sequences for the given target protein using PepMLM.

    Novelty/diversity is controlled by top_k (candidate pool per position) and temperature
    (higher = more random sampling). Returns a list of peptide strings (one-letter amino acid).
    """
    import torch
    from torch.distributions.categorical import Categorical

    target = _normalize_sequence(target_protein_sequence)
    if not target:
        return []

    model, tokenizer = _get_model_and_tokenizer()
    device = next(model.parameters()).device
    mask_token = tokenizer.mask_token
    masked_peptide = mask_token * peptide_length
    input_sequence = target + masked_peptide

    # Clamp temperature to avoid division issues
    temp = max(1e-6, float(temperature))

    binders = []
    for _ in range(num_binders):
        inputs = tokenizer(input_sequence, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits

        mask_token_id = tokenizer.mask_token_id
        mask_positions = (inputs["input_ids"] == mask_token_id).nonzero(as_tuple=True)[1]
        logits_at_masks = logits[0, mask_positions]

        k = min(max(1, top_k), logits_at_masks.size(-1))
        top_k_logits, top_k_indices = logits_at_masks.topk(k, dim=-1)
        # Temperature scaling: higher temp = flatter probs = more novelty
        probs = torch.nn.functional.softmax(top_k_logits / temp, dim=-1)
        sampled = Categorical(probs).sample()
        predicted_ids = top_k_indices.gather(-1, sampled.unsqueeze(-1)).squeeze(-1)

        peptide = tokenizer.decode(predicted_ids, skip_special_tokens=True)
        peptide = re.sub(r"\s+", "", peptide).upper()
        if peptide and all(c in "ACDEFGHIKLMNPQRSTVWY" for c in peptide):
            binders.append(peptide)
    return binders if binders else [""] * num_binders
