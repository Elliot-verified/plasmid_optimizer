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
    # ML
    parser.add_argument(
        "--generate-binder-for-target",
        type=str,
        metavar="SEQUENCE_OR_FILE",
        help="Generate peptide binders for target protein (PepMLM); print peptides and exit.",
    )
    parser.add_argument(
        "--predict-metal-binding",
        action="store_true",
        help="Run MetaLATTE on optimized AA (or with --input) and print predicted metals.",
    )
    parser.add_argument(
        "--no-metal-prediction",
        action="store_true",
        help="Do not include metal-binding prediction in optimize step.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON (for optimize).",
    )

    args = parser.parse_args()

    # Generate binder only
    if args.generate_binder_for_target is not None:
        seq = args.generate_binder_for_target.strip()
        if Path(seq).exists():
            seq = Path(seq).read_text()
        seq = normalize_sequence(seq)
        try:
            from .ml.pepmlm import generate_binders
            peptides = generate_binders(seq, peptide_length=15, num_binders=4)
            for i, p in enumerate(peptides, 1):
                print(f"Binder {i}: {p}")
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

    # Optional metal prediction
    if args.predict_metal_binding and not args.no_metal_prediction:
        aa = result.get("amino_acid") or sequence if args.type == "aa" else result.get("amino_acid")
        if aa:
            try:
                from .ml.metalatte import predict_metal_binding
                mb = predict_metal_binding(aa)
                result.setdefault("report", {})["metal_binding"] = mb
                if mb.get("predicted_metals"):
                    print("Predicted metals:", ", ".join(mb["predicted_metals"]), file=sys.stderr)
            except ImportError:
                pass

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
