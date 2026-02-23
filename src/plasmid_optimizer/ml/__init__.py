"""Optional ML: PepMLM for novel peptide (binder) generation."""

def generate_binders(
    target_protein_sequence: str,
    peptide_length: int = 15,
    num_binders: int = 4,
    top_k: int = 3,
    temperature: float = 1.0,
):
    """Generate novel peptide binders for target protein using PepMLM. Requires [ml] extra."""
    from .pepmlm import generate_binders as _gen
    return _gen(
        target_protein_sequence,
        peptide_length=peptide_length,
        num_binders=num_binders,
        top_k=top_k,
        temperature=temperature,
    )
