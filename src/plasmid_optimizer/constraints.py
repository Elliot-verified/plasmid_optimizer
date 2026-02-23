"""Constraint config types and optional custom DnaChisel specs (e.g. RNA folding)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Homopolymer pattern: 5+ of same base (avoid long runs)
HOMOPOLYMER_PATTERN = "A{5,}|T{5,}|G{5,}|C{5,}"


@dataclass
class ConstraintConfig:
    """Scientist-selected constraints for plasmid optimization."""

    codon_organism: str = "e_coli"
    gc_min: float = 0.4
    gc_max: float = 0.6
    gc_window: int = 50
    avoid_restriction_enzymes: list[str] = field(default_factory=lambda: [])
    avoid_secondary_structure: bool = True
    avoid_repeats: bool = True
    homopolymer_max_run: int = 5  # avoid runs longer than this

    def to_dict(self) -> dict[str, Any]:
        return {
            "codon_organism": self.codon_organism,
            "gc_min": self.gc_min,
            "gc_max": self.gc_max,
            "gc_window": self.gc_window,
            "avoid_restriction_enzymes": self.avoid_restriction_enzymes,
            "avoid_secondary_structure": self.avoid_secondary_structure,
            "avoid_repeats": self.avoid_repeats,
            "homopolymer_max_run": self.homopolymer_max_run,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ConstraintConfig:
        return cls(
            codon_organism=d.get("codon_organism", "e_coli"),
            gc_min=float(d.get("gc_min", 0.4)),
            gc_max=float(d.get("gc_max", 0.6)),
            gc_window=int(d.get("gc_window", 50)),
            avoid_restriction_enzymes=list(d.get("avoid_restriction_enzymes", [])),
            avoid_secondary_structure=bool(d.get("avoid_secondary_structure", True)),
            avoid_repeats=bool(d.get("avoid_repeats", True)),
            homopolymer_max_run=int(d.get("homopolymer_max_run", 5)),
        )
