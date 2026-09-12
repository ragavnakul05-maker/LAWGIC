"""
config.py — Lawgic RAG Backend Configuration
All settings are read from environment variables (with sane defaults).
Copy .env.example → .env and override as needed.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATUTES_DIR = DATA_DIR / "statutes"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Ensure runtime directories exist
STATUTES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Base LLM — Phi-4-mini (~3.8 GB, fits under 5 GB requirement)
LLM_MODEL: str = os.getenv("LLM_MODEL", "phi4-mini")

# Embedding model — small, fast, high-quality
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")

# ---------------------------------------------------------------------------
# LlamaIndex / RAG tunables
# ---------------------------------------------------------------------------
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))
SIMILARITY_TOP_K: int = int(os.getenv("SIMILARITY_TOP_K", "5"))

# Ollama request timeout (seconds) — large enough for first cold-start
LLM_REQUEST_TIMEOUT: float = float(os.getenv("LLM_REQUEST_TIMEOUT", "300.0"))

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------
CHROMA_COLLECTION_STATUTES: str = "lawgic_statutes"
CHROMA_COLLECTION_UPLOADS: str = "lawgic_uploads"

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,https://lawgic-phi.vercel.app",
).split(",")

MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

# ---------------------------------------------------------------------------
# System prompt for legal domain
# ---------------------------------------------------------------------------
LEGAL_SYSTEM_PROMPT = """You are Lawgic, an expert AI legal assistant specialising in \
Indian law and contract analysis. You answer questions STRICTLY based on the \
document context provided to you. Follow these rules:

1. ALWAYS cite your sources using the format [Source: <filename>, Page <n>].
2. If the answer is not found in the provided context, say: \
   "I could not find this information in the uploaded documents."
3. Do NOT fabricate statutes, case laws, section numbers, or clauses.
4. Keep answers precise, professional, and easy to understand.
5. When analysing contracts, highlight risks, obligations, and key dates.
"""
