"""FastAPI app: POST /optimize, POST /generate-binder, POST /predict-metal-binding."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Import core (required)
from plasmid_optimizer.constraints import ConstraintConfig
from plasmid_optimizer.core import optimize as run_optimize
from plasmid_optimizer.species import SUPPORTED_SPECIES
from plasmid_optimizer.uniprot import fetch_uniprot_fasta


def _metal_binding_for_sequence(aa_sequence: str) -> Optional[dict]:
    """Run MetaLATTE if available; else return None."""
    try:
        from plasmid_optimizer.ml.metalatte import predict_metal_binding
        return predict_metal_binding(aa_sequence)
    except Exception:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Plasmid Optimizer API", version="0.1.0", lifespan=lifespan)

# Serve web UI from ../web if present
_web_dir = Path(__file__).resolve().parent.parent / "web"
if _web_dir.exists():
    @app.get("/")
    def index():
        return FileResponse(_web_dir / "index.html")
    app.mount("/web", StaticFiles(directory=_web_dir), name="web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---

class OptimizeConstraints(BaseModel):
    codon_organism: str = Field(default="e_coli", description="Species for codon usage")
    gc_min: float = Field(default=0.4, ge=0, le=1)
    gc_max: float = Field(default=0.6, ge=0, le=1)
    gc_window: int = Field(default=50, ge=10, le=500)
    avoid_restriction_enzymes: List[str] = Field(default_factory=list)
    avoid_secondary_structure: bool = True
    avoid_repeats: bool = True
    homopolymer_max_run: int = Field(default=5, ge=3, le=20)


class OptimizeRequest(BaseModel):
    sequence: str
    sequence_type: str = Field(..., pattern="^(aa|dna)$")
    constraints: Optional[OptimizeConstraints] = None
    include_metal_prediction: bool = Field(default=True)


class GenerateBinderRequest(BaseModel):
    target_protein_sequence: str
    peptide_length: int = Field(default=15, ge=5, le=50)
    num_binders: int = Field(default=4, ge=1, le=20)


class PredictMetalRequest(BaseModel):
    amino_acid_sequence: str


# --- Endpoints ---

@app.get("/species")
def list_species():
    """List supported organisms for codon optimization."""
    return {"species": SUPPORTED_SPECIES}


@app.get("/fetch-uniprot")
def fetch_uniprot(id: str):
    """
    Fetch protein sequence from UniProt by accession or FASTA URL.

    Query param: id — UniProt accession (e.g. Q6JKW3) or full URL (e.g. https://rest.uniprot.org/uniprotkb/Q6JKW3.fasta).
    Returns: { "sequence", "header", "error" } (error is null on success).
    """
    result = fetch_uniprot_fasta(id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/optimize")
def optimize(request: OptimizeRequest) -> dict:
    """Optimize a plasmid sequence (AA or DNA) under the given constraints."""
    cfg = ConstraintConfig.from_dict(
        (request.constraints or OptimizeConstraints()).model_dump()
    )
    result = run_optimize(
        sequence=request.sequence,
        sequence_type=request.sequence_type,
        config=cfg,
    )
    if result.get("report", {}).get("error") and not result.get("optimized_dna"):
        raise HTTPException(status_code=400, detail=result["report"]["error"])

    if request.include_metal_prediction and result.get("amino_acid"):
        mb = _metal_binding_for_sequence(result["amino_acid"])
        if mb is not None:
            result.setdefault("report", {})["metal_binding"] = mb

    return result


@app.post("/generate-binder")
def generate_binder(request: GenerateBinderRequest) -> dict:
    """Generate peptide binders for a target protein using PepMLM (requires [ml] extra)."""
    try:
        from plasmid_optimizer.ml.pepmlm import generate_binders
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PepMLM is not available. Install with: pip install plasmid_optimizer[ml]",
        )
    peptides = generate_binders(
        target_protein_sequence=request.target_protein_sequence,
        peptide_length=request.peptide_length,
        num_binders=request.num_binders,
    )
    return {"peptides": peptides}


@app.post("/predict-metal-binding")
def predict_metal_binding(request: PredictMetalRequest) -> dict:
    """Predict metal-binding for an amino acid sequence using MetaLATTE (requires [ml] extra)."""
    try:
        from plasmid_optimizer.ml.metalatte import predict_metal_binding as _pred
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="MetaLATTE is not available. Install plasmid_optimizer[ml] and set up MetaLATTE repo.",
        )
    return _pred(request.amino_acid_sequence)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
