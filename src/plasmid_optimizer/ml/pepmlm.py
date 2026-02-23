"""PepMLM: generate peptide binders for a target protein sequence (Hugging Face ChatterjeeLab/PepMLM-650M)."""

from __future__ import annotations

import re
from typing import List

_pepmlm_model = None
_pepmlm_tokenizer = None


def _get_model_and_tokenizer():
    global _pepmlm_model, _pepmlm_tokenizer
    if _pepmlm_model is None:
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _pepmlm_tokenizer = AutoTokenizer.from_pretrained("ChatterjeeLab/PepMLM-650M")
        _pepmlm_model = AutoModelForMaskedLM.from_pretrained("ChatterjeeLab/PepMLM-650M").to(device)
        _pepmlm_model.eval()
    return _pepmlm_model, _pepmlm_tokenizer


def _normalize_sequence(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def generate_binders(
    target_protein_sequence: str,
    peptide_length: int = 15,
    num_binders: int = 4,
    top_k: int = 3,
) -> List[str]:
    """
    Generate peptide binder sequences for the given target protein using PepMLM.

    Returns a list of peptide strings (one-letter amino acid).
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

    binders = []
    for _ in range(num_binders):
        inputs = tokenizer(input_sequence, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits

        mask_token_id = tokenizer.mask_token_id
        mask_positions = (inputs["input_ids"] == mask_token_id).nonzero(as_tuple=True)[1]
        logits_at_masks = logits[0, mask_positions]

        top_k_logits, top_k_indices = logits_at_masks.topk(min(top_k, logits_at_masks.size(-1)), dim=-1)
        probs = torch.nn.functional.softmax(top_k_logits, dim=-1)
        sampled = Categorical(probs).sample()
        predicted_ids = top_k_indices.gather(-1, sampled.unsqueeze(-1)).squeeze(-1)

        peptide = tokenizer.decode(predicted_ids, skip_special_tokens=True)
        peptide = re.sub(r"\s+", "", peptide).upper()
        if peptide and all(c in "ACDEFGHIKLMNPQRSTVWY" for c in peptide):
            binders.append(peptide)
    return binders if binders else [""] * num_binders
