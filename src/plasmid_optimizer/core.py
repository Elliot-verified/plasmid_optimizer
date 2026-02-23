"""Build optimization problem from constraints and sequence; run resolve/optimize; return results."""

from __future__ import annotations

from typing import Any

from .constraints import ConstraintConfig
from .io import (
    back_translate_aa_to_dna,
    dna_to_aa,
    normalize_sequence,
    validate_aa,
    validate_dna,
)


def _build_specs(
    dna_sequence: str,
    translation: str,
    config: ConstraintConfig,
):
    """Build DnaChisel constraints and objectives from config and sequence."""
    from dnachisel import (
        AvoidHairpins,
        AvoidPattern,
        CodonOptimize,
        DnaOptimizationProblem,
        EnforceGCContent,
        EnforceTranslation,
        UniquifyAllKmers,
    )

    n = len(dna_sequence)
    location = (0, n, 1)

    constraints = [
        EnforceTranslation(
            location=location,
            translation=translation,
        ),
        EnforceGCContent(
            mini=config.gc_min,
            maxi=config.gc_max,
            window=config.gc_window,
            location=location,
        ),
    ]

    for enzyme in config.avoid_restriction_enzymes:
        pattern = f"{enzyme}_site" if "_site" not in enzyme else enzyme
        constraints.append(AvoidPattern(pattern, location=location, strand="both"))

    if config.avoid_secondary_structure:
        constraints.append(
            AvoidHairpins(stem_size=10, hairpin_window=80, location=location)
        )

    if config.avoid_repeats:
        constraints.append(UniquifyAllKmers(10, location=location, include_reverse_complement=True))

    # Avoid long homopolymers: add one AvoidPattern per base for run length > homopolymer_max_run
    for base in "ATGC":
        pattern = base * (config.homopolymer_max_run + 1)
        constraints.append(AvoidPattern(pattern, location=location))

    objectives = [
        CodonOptimize(species=config.codon_organism, location=location),
    ]

    return constraints, objectives


def optimize(
    sequence: str,
    sequence_type: str,
    config: ConstraintConfig,
) -> dict[str, Any]:
    """
    Run plasmid optimization.

    sequence: raw AA or DNA string
    sequence_type: "aa" or "dna"
    config: constraint options

    Returns dict with optimized_dna, amino_acid, report (gc_content, constraints_summary, errors).
    """
    from dnachisel import DnaOptimizationProblem

    seq = normalize_sequence(sequence)
    if not seq:
        return {
            "optimized_dna": "",
            "amino_acid": "",
            "report": {"error": "Empty sequence"},
        }

    if sequence_type == "aa":
        ok, err = validate_aa(seq)
        if not ok:
            return {"optimized_dna": "", "amino_acid": "", "report": {"error": err}}
        translation = seq
        initial_dna = back_translate_aa_to_dna(seq)
    else:
        ok, err = validate_dna(seq)
        if not ok:
            return {"optimized_dna": "", "amino_acid": "", "report": {"error": err}}
        initial_dna = seq
        translation = dna_to_aa(seq)

    constraints, objectives = _build_specs(initial_dna, translation, config)

    problem = DnaOptimizationProblem(
        sequence=initial_dna,
        constraints=constraints,
        objectives=objectives,
    )

    try:
        problem.resolve_constraints()
        problem.optimize()
    except Exception as e:
        return {
            "optimized_dna": initial_dna,
            "amino_acid": translation,
            "report": {
                "error": str(e),
                "constraints_resolved": False,
            },
        }

    final_dna = problem.sequence
    final_aa = dna_to_aa(final_dna)

    # GC content
    gc_count = sum(1 for c in final_dna if c in "GC")
    gc_content = gc_count / len(final_dna) if final_dna else 0.0

    report = {
        "gc_content": round(gc_content, 4),
        "length_dna": len(final_dna),
        "length_aa": len(final_aa),
        "constraints_summary": problem.constraints_text_summary(),
        "objectives_summary": problem.objectives_text_summary(),
        "error": None,
    }

    return {
        "optimized_dna": final_dna,
        "amino_acid": final_aa,
        "report": report,
    }
