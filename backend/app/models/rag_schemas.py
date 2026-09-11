"""
rag_schemas.py — Pydantic request/response schemas for Lawgic RAG API
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class SourceCitation(BaseModel):
    """A single source chunk returned alongside an AI answer."""
    filename: str = Field(..., description="Name of the source document")
    page: Optional[int] = Field(None, description="Page number (if available)")
    snippet: str = Field(..., description="Relevant text excerpt from the chunk")
    collection: str = Field(..., description="'statutes' or 'uploads'")


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000,
                          description="The legal question to ask")
    collection: str = Field(
        default="both",
        description="Which corpus to search: 'statutes', 'uploads', or 'both'",
    )
    session_id: Optional[str] = Field(
        None, description="Optional session ID for conversation history"
    )


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    model: str
    question: str


# ---------------------------------------------------------------------------
# /ingest
# ---------------------------------------------------------------------------

class IngestResponse(BaseModel):
    message: str
    filename: str
    chunks_indexed: int
    doc_id: str


# ---------------------------------------------------------------------------
# /documents
# ---------------------------------------------------------------------------

class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    collection: str
    chunks: int


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int


class DeleteResponse(BaseModel):
    message: str
    doc_id: str


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    llm_model: str
    embed_model: str
    ollama_reachable: bool
    statutes_chunks: int
    uploads_chunks: int
