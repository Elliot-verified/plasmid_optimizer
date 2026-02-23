"""CLI: plasmid-optimize with constraints and optional ML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .constraints import ConstraintConfig
from .core import optimize as run_optimize
from .io import normalize_sequence
from .uniprot import fetch_uniprot_fasta


def main():
    parser = argparse.ArgumentParser(
        description="Plasmid Optimizer: optimize DNA/AA sequences with constraints.",
    )
    parser.add_argument(
        "-s", "--sequence",
        type=str,
        help="Input sequence (amino acid or DNA).",
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        help="Read sequence from file (one sequence, whitespace stripped).",
    )
    parser.add_argument(
        "--uniprot-id",
        type=str,
        metavar="ID",
        help="Fetch sequence from UniProt by accession or FASTA URL (e.g. Q6JKW3). Uses amino acid type.",
    )
    parser.add_argument(
        "-t", "--type",
        choices=["aa", "dna"],
        default="aa",
        help="Sequence type: aa (amino acid) or dna.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Write optimized DNA to file (default: stdout).",
    )
    parser.add_argument(
        "--organism",
        type=str,
        default="e_coli",
        help="Species for codon optimization (e.g. e_coli, s_cerevisiae).",
    )
    parser.add_argument(
        "--gc-min",
        type=float,
        default=0.4,
        help="Minimum GC content (0-1).",
    )
    parser.add_argument(
        "--gc-max",
        type=float,
        default=0.6,
        help="Maximum GC content (0-1).",
    )
    parser.add_argument(
        "--gc-window",
        type=int,
        default=50,
        help="Sliding window size for GC constraint.",
    )
    parser.add_argument(
        "--avoid-enzymes",
        type=str,
        default="",
        help="Comma-separated restriction enzymes to avoid (e.g. EcoRI,BamHI,BsaI).",
    )
    parser.add_argument(
        "--no-secondary-structure",
        action="store_true",
        help="Disable avoid-secondary-structure constraint.",
    )
    parser.add_argument(
        "--no-repeats",
        action="store_true",
        help="Disable avoid-repeats constraint.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="JSON config file for constraints (overrides CLI flags).",
    )
    # Novel peptide generation (PepMLM)
    parser.add_argument(
        "--generate-binder-for-target",
        type=str,
        metavar="SEQUENCE_OR_FILE",
        help="Generate novel peptides for target protein (PepMLM); print sequences and exit.",
    )
    parser.add_argument(
        "--peptide-length",
        type=int,
        default=15,
        metavar="N",
        help="Length of generated peptide (default 15). Used with --generate-binder-for-target.",
    )
    parser.add_argument(
        "--num-binders",
        type=int,
        default=4,
        metavar="N",
        help="Number of novel sequences to generate (default 4).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        metavar="K",
        help="Top-k candidates per position; higher = more diversity (default 3).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        metavar="T",
        help="Sampling temperature; higher = more novel/random (default 1.0).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON (for optimize).",
    )

    args = parser.parse_args()

    # Novel peptide generation only
    if args.generate_binder_for_target is not None:
        seq = args.generate_binder_for_target.strip()
        if Path(seq).exists():
            seq = Path(seq).read_text()
        seq = normalize_sequence(seq)
        try:
            from .ml.pepmlm import generate_binders
            peptides = generate_binders(
                seq,
                peptide_length=args.peptide_length,
                num_binders=args.num_binders,
                top_k=args.top_k,
                temperature=args.temperature,
            )
            for i, p in enumerate(peptides, 1):
                print(f"Peptide {i}: {p}")
        except ImportError:
            print("PepMLM not available. Install with: pip install plasmid_optimizer[ml]", file=sys.stderr)
            sys.exit(1)
        return

    # Need sequence for optimize
    if args.uniprot_id:
        result = fetch_uniprot_fasta(args.uniprot_id)
        if result.get("error"):
            print(result["error"], file=sys.stderr)
            sys.exit(1)
        sequence = result["sequence"]
        args.type = "aa"
    elif args.sequence:
        sequence = args.sequence
    elif args.input:
        sequence = args.input.read_text()
    else:
        parser.error("Provide --sequence, --input, or --uniprot-id")
    sequence = normalize_sequence(sequence)
    if not sequence:
        print("Empty sequence.", file=sys.stderr)
        sys.exit(1)

    if args.config:
        cfg = ConstraintConfig.from_dict(json.loads(args.config.read_text()))
    else:
        enzymes = [e.strip() for e in args.avoid_enzymes.split(",") if e.strip()]
        cfg = ConstraintConfig(
            codon_organism=args.organism,
            gc_min=args.gc_min,
            gc_max=args.gc_max,
            gc_window=args.gc_window,
            avoid_restriction_enzymes=enzymes,
            avoid_secondary_structure=not args.no_secondary_structure,
            avoid_repeats=not args.no_repeats,
        )

    result = run_optimize(sequence=sequence, sequence_type=args.type, config=cfg)

    if result.get("report", {}).get("error") and not result.get("optimized_dna"):
        print(result["report"]["error"], file=sys.stderr)
        sys.exit(1)

    if args.json:
        out = json.dumps({
            "optimized_dna": result.get("optimized_dna", ""),
            "amino_acid": result.get("amino_acid", ""),
            "report": result.get("report", {}),
        }, indent=2)
        if args.output:
            args.output.write_text(out)
        else:
            print(out)
        return

    dna = result.get("optimized_dna", "")
    if args.output:
        args.output.write_text(dna)
        print(f"Wrote {len(dna)} bp to {args.output}", file=sys.stderr)
    else:
        print(dna)

    rep = result.get("report", {})
    if rep.get("gc_content") is not None:
        print(f"GC%: {rep['gc_content']*100:.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
