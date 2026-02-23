"""Optional ML: PepMLM (peptide binder generation), MetaLATTE (metal-binding prediction)."""

def generate_binders(target_protein_sequence: str, peptide_length: int = 15, num_binders: int = 4, top_k: int = 3):
    """Generate peptide binders for target protein using PepMLM. Requires [ml] extra."""
    from .pepmlm import generate_binders as _gen
    return _gen(target_protein_sequence, peptide_length=peptide_length, num_binders=num_binders, top_k=top_k)


def predict_metal_binding(amino_acid_sequence: str):
    """Predict metal-binding for AA sequence using MetaLATTE. Requires [ml] extra."""
    from .metalatte import predict_metal_binding as _pred
    return _pred(amino_acid_sequence)
