"""Fetch protein sequence from UniProt REST API (FASTA)."""

from __future__ import annotations

import re
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UNIPROT_FASTA_URL = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"


def _extract_accession_from_url(url: str) -> str | None:
    """Extract UniProt accession from a URL like https://rest.uniprot.org/uniprotkb/Q6JKW3.fasta."""
    url = url.strip()
    # Match .../uniprotkb/<accession>.fasta or .../uniprotkb/<accession>
    m = re.search(r"uniprotkb/([A-Z0-9][A-Z0-9_]+)(?:\.fasta)?", url, re.I)
    return m.group(1) if m else None


def _parse_fasta(fasta_text: str) -> tuple[str, str]:
    """Parse FASTA text; return (header_line, sequence). Uses first record only."""
    lines = fasta_text.strip().splitlines()
    header = ""
    seq_parts = []
    for line in lines:
        if line.startswith(">"):
            if header and seq_parts:
                break
            header = line[1:].strip()
            seq_parts = []
        else:
            seq_parts.append(line.strip())
    sequence = re.sub(r"\s+", "", "".join(seq_parts)).upper()
    return header, sequence


def fetch_uniprot_fasta(uniprot_id_or_url: str) -> dict[str, Any]:
    """
    Fetch FASTA from UniProt by accession ID or full FASTA URL.

    Args:
        uniprot_id_or_url: UniProt accession (e.g. Q6JKW3) or URL like
            https://rest.uniprot.org/uniprotkb/Q6JKW3.fasta

    Returns:
        {"sequence": str, "header": str, "error": None} on success,
        {"sequence": "", "header": "", "error": str} on failure.
    """
    raw = uniprot_id_or_url.strip()
    if not raw:
        return {"sequence": "", "header": "", "error": "Empty UniProt ID or URL."}

    url = raw if raw.startswith("http://") or raw.startswith("https://") else None
    if url is None:
        # Treat as accession (allow alphanumeric and underscore)
        accession = re.sub(r"\s+", "", raw)
        if not accession:
            return {"sequence": "", "header": "", "error": "Invalid UniProt accession."}
        url = UNIPROT_FASTA_URL.format(accession=accession)

    try:
        req = Request(url, headers={"User-Agent": "PlasmidOptimizer/1.0"})
        with urlopen(req, timeout=15) as resp:
            fasta_text = resp.read().decode("utf-8")
    except HTTPError as e:
        return {"sequence": "", "header": "", "error": f"UniProt returned {e.code}: {e.reason}"}
    except URLError as e:
        return {"sequence": "", "header": "", "error": f"Request failed: {e.reason}"}
    except Exception as e:
        return {"sequence": "", "header": "", "error": str(e)}

    header, sequence = _parse_fasta(fasta_text)
    if not sequence:
        return {"sequence": "", "header": header, "error": "No sequence in FASTA."}
    return {"sequence": sequence, "header": header, "error": None}
