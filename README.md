# Plasmid Optimizer

Optimize plasmid sequences (DNA or amino acid) for bacterial expression. Choose constraints (codon usage, GC content, restriction sites, secondary structure, repeats/homopolymers) and optionally use Hugging Face ML models: **PepMLM** (peptide binder generation) and **MetaLATTE** (metal-binding prediction). Delivered as a **web app** and **CLI**.

## Install

From the project root:

```bash
pip install -e .
```

For ML features (PepMLM, MetaLATTE):

```bash
pip install -e ".[ml]"
```

**Note:** MetaLATTE uses a custom model. To use it, clone [ChatterjeeLab/MetaLATTE](https://huggingface.co/ChatterjeeLab/MetaLATTE) and add the repo (or its `metalatte` module) to your `PYTHONPATH`, or place it as `ChatterjeeLab/MetaLATTE` next to the project. PepMLM works out of the box with `.[ml]`.

Optional: if you hit NumPy/pandas compatibility issues with DnaChisel, try `numpy<2` in your environment.

## Run the API and Web UI

From the project root (with the package installed):

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for the web UI. The same server serves the REST API.

## UniProt integration

You can load a protein sequence directly from [UniProt](https://www.uniprot.org/) by accession or FASTA URL.

- **Web UI:** In "Generate peptide binder" or "Sequence to optimize", enter a UniProt accession (e.g. `Q6JKW3`) or paste a FASTA URL (e.g. `https://rest.uniprot.org/uniprotkb/Q6JKW3.fasta`) and click **Fetch** to fill the sequence.
- **CLI:** Use `--uniprot-id Q6JKW3` (or a full FASTA URL) instead of `-s`/`-i`; the sequence is fetched and treated as amino acid.

## CLI

```bash
# Optimize an amino acid sequence (output to stdout)
plasmid-optimize -s "MKQL" -t aa

# Fetch from UniProt and optimize
plasmid-optimize --uniprot-id Q6JKW3 -o optimized_dna.txt

# Optimize from file, write DNA to file
plasmid-optimize -i sequence.txt -t aa -o optimized_dna.txt

# With constraints
plasmid-optimize -s "MKQL..." -t aa --organism e_coli --gc-min 0.4 --gc-max 0.6 --avoid-enzymes EcoRI,BamHI

# Generate peptide binders for a target protein (PepMLM)
plasmid-optimize --generate-binder-for-target "MKTIIALSYIFCL..."

# JSON output
plasmid-optimize -s "MKQL" -t aa --json -o result.json
```

## Constraints

| Constraint | Description |
|------------|-------------|
| **Codon usage** | Organism-specific (e.g. `e_coli`, `s_cerevisiae`). |
| **GC content** | Min/max and sliding window size. |
| **Restriction sites** | Avoid selected enzymes (e.g. EcoRI, BamHI, BsaI). |
| **Secondary structure** | Avoid hairpins (DnaChisel AvoidHairpins). |
| **Repeats / homopolymers** | Uniquify kmers; avoid long homopolymer runs. |

## API

- `POST /optimize` — Body: `{ "sequence", "sequence_type": "aa"|"dna", "constraints": {...}, "include_metal_prediction": true }`. Returns `optimized_dna`, `amino_acid`, `report` (with optional `metal_binding`).
- `POST /generate-binder` — Body: `{ "target_protein_sequence", "peptide_length", "num_binders" }`. Returns `peptides` (PepMLM). Requires `[ml]`.
- `POST /predict-metal-binding` — Body: `{ "amino_acid_sequence" }`. Returns predicted metals (MetaLATTE). Requires `[ml]` and MetaLATTE setup.
- `GET /species` — List supported organisms for codon optimization.
- `GET /fetch-uniprot?id=Q6JKW3` — Fetch protein sequence from UniProt by accession or FASTA URL. Returns `{ "sequence", "header" }`.

## References

- [DnaChisel](https://edinburgh-genome-foundry.github.io/DnaChisel/) — sequence optimization.
- [ViennaRNA](https://www.tbi.univie.ac.at/RNA/) — RNA structure (optional).
- [PepMLM (ChatterjeeLab/PepMLM-650M)](https://huggingface.co/ChatterjeeLab/PepMLM-650M) — peptide binder generation.
- [MetaLATTE (ChatterjeeLab/MetaLATTE)](https://huggingface.co/ChatterjeeLab/MetaLATTE) — metal-binding prediction.
