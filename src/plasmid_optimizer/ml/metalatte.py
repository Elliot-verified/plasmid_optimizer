"""MetaLATTE: metal-binding prediction for protein sequences (Hugging Face ChatterjeeLab/MetaLATTE)."""

from __future__ import annotations

import re
from typing import Any, Dict, List

_metalatte_model = None
_metalatte_tokenizer = None
_metalatte_config = None


def _normalize_sequence(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def _load_metalatte():
    global _metalatte_model, _metalatte_tokenizer, _metalatte_config
    if _metalatte_model is not None:
        return

    try:
        from transformers import AutoConfig, AutoModel, AutoTokenizer
    except ImportError:
        raise ImportError("MetaLATTE requires transformers. Install with: pip install plasmid_optimizer[ml]")

    # MetaLATTE uses custom config and model; try to load from repo
    try:
        import sys
        from pathlib import Path
        # Allow loading from cloned MetaLATTE repo if present
        repo_path = Path(__file__).resolve().parent.parent.parent.parent / "ChatterjeeLab" / "MetaLATTE"
        if repo_path.exists():
            sys.path.insert(0, str(repo_path))
        from metalatte import MetaLATTEConfig, MultitaskProteinModel
        AutoConfig.register("metalatte", MetaLATTEConfig)
        AutoModel.register(MetaLATTEConfig, MultitaskProteinModel)
    except ImportError:
        raise ImportError(
            "MetaLATTE requires the metalatte module from ChatterjeeLab/MetaLATTE. "
            "Clone the repo and add it to PYTHONPATH, or install from the repo."
        )

    _metalatte_tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
    _metalatte_config = AutoConfig.from_pretrained("ChatterjeeLab/MetaLATTE")
    _metalatte_model = AutoModel.from_pretrained("ChatterjeeLab/MetaLATTE", config=_metalatte_config)
    _metalatte_model.eval()


def predict_metal_binding(amino_acid_sequence: str) -> Dict[str, Any]:
    """
    Predict metal-binding for the given amino acid sequence using MetaLATTE.

    Returns dict with predicted_metals (list of metal labels, e.g. Cu, Zn) and optionally probabilities.
    """
    seq = _normalize_sequence(amino_acid_sequence)
    if not seq:
        return {"predicted_metals": [], "probabilities": {}, "available": False}

    try:
        _load_metalatte()
    except ImportError as e:
        return {"predicted_metals": [], "probabilities": {}, "available": False, "error": str(e)}

    import torch
    device = next(_metalatte_model.parameters()).device
    inputs = _metalatte_tokenizer(seq, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        raw_probs, predictions = _metalatte_model.predict(**inputs)

    id2label = getattr(_metalatte_config, "id2label", {})
    if not id2label and hasattr(_metalatte_config, "label2id"):
        id2label = {v: k for k, v in _metalatte_config.label2id.items()}
    predicted_labels = []
    for i, pred in enumerate(predictions[0]):
        if pred == 1 and i in id2label:
            predicted_labels.append(id2label[i])

    probs = {}
    if raw_probs is not None and hasattr(raw_probs, "tolist"):
        try:
            prob_list = raw_probs[0].tolist()
            for i, label in id2label.items():
                if i < len(prob_list):
                    probs[label] = round(float(prob_list[i]), 4)
        except Exception:
            pass

    return {
        "predicted_metals": predicted_labels,
        "probabilities": probs,
        "available": True,
    }
