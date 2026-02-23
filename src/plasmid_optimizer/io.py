"""Parse and validate AA/DNA input; back-translate AA to DNA; output formatting."""

from __future__ import annotations

import re
from typing import Literal

from Bio.Seq import Seq

# Valid 1-letter amino acid codes (standard + stop)
AA_LETTERS = set("ACDEFGHIKLMNPQRSTVWY*")
# IUPAC DNA
DNA_LETTERS = set("ACGTURYSWKMBDHVN.- ")


def normalize_sequence(raw: str) -> str:
    """Strip whitespace and newlines; uppercase."""
    return re.sub(r"\s+", "", raw).upper()


def guess_sequence_type(sequence: str) -> Literal["aa", "dna"]:
    """Heuristic: if mostly valid DNA letters and length % 3 == 0, prefer DNA; else AA."""
    s = normalize_sequence(sequence)
    if not s:
        return "aa"
    dna_count = sum(1 for c in s if c in DNA_LETTERS)
    aa_count = sum(1 for c in s if c in AA_LETTERS)
    if aa_count >= len(s) * 0.9 and dna_count < len(s) * 0.9:
        return "aa"
    if dna_count >= len(s) * 0.9:
        return "dna"
    return "aa"


def validate_aa(sequence: str) -> tuple[bool, str]:
    """Validate amino acid sequence (1-letter). Returns (ok, error_message)."""
    s = normalize_sequence(sequence)
    if not s:
        return False, "Empty sequence"
    invalid = [c for c in s if c not in AA_LETTERS]
    if invalid:
        return False, f"Invalid amino acid character(s): {set(invalid)}"
    return True, ""


def validate_dna(sequence: str) -> tuple[bool, str]:
    """Validate DNA sequence (IUPAC). Returns (ok, error_message)."""
    s = normalize_sequence(sequence)
    if not s:
        return False, "Empty sequence"
    invalid = [c for c in s if c not in DNA_LETTERS]
    if invalid:
        return False, f"Invalid DNA character(s): {set(invalid)}"
    if len(s) % 3 != 0:
        return False, "DNA length must be a multiple of 3 for translation"
    return True, ""


def back_translate_aa_to_dna(
    aa_sequence: str,
    table_id: int = 1,
    codon_choice: Literal["first", "random"] = "first",
) -> str:
    """Convert amino acid sequence to DNA using Biopython. Uses first codon per AA by default."""
    s = normalize_sequence(aa_sequence)
    if not s:
        return ""
    from Bio.Data.CodonTable import ambiguous_dna_by_id
    import random

    std = ambiguous_dna_by_id[table_id]
    # Build aa -> list of DNA codons (forward_table is codon -> aa)
    bases = "ACGT"
    triplets = [a + b + c for a in bases for b in bases for c in bases]
    rev = {}
    for c in triplets:
        try:
            aa = std.forward_table[c]
            rev.setdefault(aa, []).append(c)
        except (KeyError, TypeError):
            pass
    stops = [c for c in (getattr(std, "stop_codons", []) or []) if "U" not in c] or ["TAA"]
    codons = []
    for aa in s:
        if aa == "*":
            codons.append(stops[0])
        else:
            choices = rev.get(aa, ["NNN"])
            codons.append(choices[0] if codon_choice == "first" else random.choice(choices))
    return "".join(codons)


def dna_to_aa(dna_sequence: str, table_id: int = 1) -> str:
    """Translate DNA to amino acid (1-letter)."""
    s = normalize_sequence(dna_sequence)
    if not s:
        return ""
    seq = Seq(s)
    return str(seq.translate(to_stop=False, table=table_id))


def format_fasta(header: str, sequence: str, line_length: int = 80) -> str:
    """Format sequence as FASTA."""
    lines = [f">{header}"]
    for i in range(0, len(sequence), line_length):
        lines.append(sequence[i : i + line_length])
    return "\n".join(lines)
