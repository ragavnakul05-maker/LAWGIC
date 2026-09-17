"""
main.py — FastAPI application entry point for Lawgic RAG Backend

Endpoints:
  GET  /health                  — Readiness probe
  POST /chat                    — RAG query (returns answer + citations)
  POST /ingest                  — Upload & index a document
  GET  /documents               — List all uploaded documents
  DELETE /documents/{doc_id}    — Remove a document from the index

Streaming endpoint:
  POST /chat/stream             — SSE token stream
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.database import engine, Base, migrate_db
from app.sample_data.seed_db import seed_database
from app.api.dashboard import router as dashboard_router
from app.api.contracts import router as contracts_router
from app.api.rules import router as rules_router
from app.api.simulations import router as simulations_router
from app.api.audit import router as audit_router
from app.api.rag import router as rag_router
from app.api.auth import router as auth_router
from app.config import (
    CORS_ORIGINS,
    EMBED_MODEL,
    LLM_MODEL,
    MAX_UPLOAD_SIZE_MB,
)
from app.ingestion import (
    delete_uploaded_document,
    ingest_statutes_corpus,
    ingest_uploaded_file,
    list_uploaded_documents,
)
from app.models import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    HealthResponse,
    IngestResponse,
)
from app.rag_engine import (
    initialise_engine,
    probe_ollama,
    query_rag,
    statutes_chunk_count,
    uploads_chunk_count,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — runs once on startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Lawgic RAG backend starting up …")
    Base.metadata.create_all(bind=engine)
    try:
        migrate_db(bind_engine=engine)
    except Exception as e:
        logger.warning(f"Database migration note: {e}")
    try:
        seed_database()
    except Exception as e:
        logger.warning(f"Database seeding note: {e}")
    try:
        initialise_engine()         # Configure LlamaIndex global settings + load indexes
        ingest_statutes_corpus()    # Idempotent: skips if already indexed
    except Exception as e:
        logger.warning(f"RAG engine note (Ollama offline or loading): {e}")
    logger.info("✅ Ready to serve requests.")
    yield
    logger.info("🛑 Shutting down.")


from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response, Depends
from app.core.security import get_current_user
from app.models.schemas import UserModel

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Lawgic RAG API",
    description=(
        "Retrieval-Augmented Generation backend for Lawgic — "
        "Indian law contracts & statutes assistant powered by Phi-4-mini."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Security Headers Middleware (HTTPS-ready configuration)
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' http://localhost:* https://* ws://localhost:*; "
            "frame-ancestors 'none';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount /api routes
# ---------------------------------------------------------------------------
api_router = APIRouter(prefix="/api")
api_router.include_router(dashboard_router)
api_router.include_router(contracts_router)
api_router.include_router(rules_router)
api_router.include_router(simulations_router)
api_router.include_router(audit_router)
api_router.include_router(rag_router)
api_router.include_router(auth_router)

app.include_router(api_router)



# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check if the backend and Ollama are operational."""
    ollama_ok = await probe_ollama()
    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        llm_model=LLM_MODEL,
        embed_model=EMBED_MODEL,
        ollama_reachable=ollama_ok,
        statutes_chunks=statutes_chunk_count(),
        uploads_chunks=uploads_chunk_count(),
    )


@app.post("/chat", response_model=ChatResponse, tags=["RAG"])
async def chat(req: ChatRequest, current_user: UserModel = Depends(get_current_user)):
    """
    Ask a legal question. The model retrieves relevant context from indexed
    documents (scoped strictly to statutes and the authenticated user's documents)
    and returns an answer with source citations.
    """
    logger.info("Chat request: '%s' | collection=%s | user_id=%s", req.question[:80], req.collection, current_user.id)
    try:
        answer, sources = await query_rag(req.question, req.collection, user_id=current_user.id)  # type: ignore[arg-type]
    except Exception as exc:
        logger.exception("Error during RAG query: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(
        answer=answer,
        sources=sources,
        model=LLM_MODEL,
        question=req.question,
    )


@app.post("/chat/stream", tags=["RAG"])
async def chat_stream(req: ChatRequest, current_user: UserModel = Depends(get_current_user)):
    """
    Stream the RAG answer token-by-token via Server-Sent Events (SSE).
    Retrieves context strictly from statutes and the authenticated user's uploaded documents.
    """
    from llama_index.core import Settings
    from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter

    logger.info("Stream chat request: '%s' | user_id=%s", req.question[:80], current_user.id)

    # Run retrieval synchronously first (embedding is fast)
    from app.rag_engine import (
        get_statutes_index,
        get_uploads_index,
        _nodes_to_citations,
        SIMILARITY_TOP_K,
    )

    all_nodes = []
    if req.collection in ("statutes", "both"):
        nodes = get_statutes_index().as_retriever(
            similarity_top_k=SIMILARITY_TOP_K
        ).retrieve(req.question)
        all_nodes.extend(nodes)

    if req.collection in ("uploads", "both"):
        user_filters = MetadataFilters(
            filters=[ExactMatchFilter(key="user_id", value=str(current_user.id))]
        )
        try:
            nodes = get_uploads_index().as_retriever(
                similarity_top_k=SIMILARITY_TOP_K,
                filters=user_filters
            ).retrieve(req.question)
            all_nodes.extend(nodes)
        except Exception as exc:
            logger.warning("Uploads retrieval notice for user %s: %s", current_user.id, exc)

    if not all_nodes:
        async def no_context():
            yield "data: I could not find relevant information in the available documents.\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")

    all_nodes_sorted = sorted(all_nodes, key=lambda n: n.score or 0, reverse=True)
    context_parts = []
    for i, node in enumerate(all_nodes_sorted[:SIMILARITY_TOP_K], 1):
        meta = node.node.metadata or {}
        fname = meta.get("file_name", meta.get("filename", "Unknown"))
        page = meta.get("page_label") or meta.get("page", "?")
        context_parts.append(
            f"[Context {i} — {fname}, Page {page}]\n{node.node.get_content()}"
        )

    context_text = "\n\n---\n\n".join(context_parts)
    prompt = (
        f"Context documents:\n\n{context_text}\n\n"
        f"---\n\nUser question: {req.question}\n\n"
        "Answer (cite sources using [Source: <filename>, Page <n>]):"
    )

    async def token_stream():
        try:
            async for token in await Settings.llm.astream_complete(prompt):
                text = token.delta or ""
                if text:
                    # SSE format
                    yield f"data: {text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("Stream error: %s", exc)
            yield f"data: [ERROR] {exc}\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


@app.post("/ingest", response_model=IngestResponse, tags=["Documents"])
async def ingest_document(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Upload a PDF or DOCX file. It will be chunked, embedded, and stored
    in the vector database isolated to the authenticated user.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = file.filename.rsplit(".", 1)[-1].lower()
    if suffix not in {"pdf", "docx", "txt", "md"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{suffix}'. Allowed: pdf, docx, txt, md",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {MAX_UPLOAD_SIZE_MB} MB",
        )

    try:
        result = await ingest_uploaded_file(content, file.filename, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Ingestion error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return IngestResponse(
        message=f"'{file.filename}' indexed successfully.",
        filename=result["filename"],
        chunks_indexed=result["chunks_indexed"],
        doc_id=result["doc_id"],
    )


@app.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents(current_user: UserModel = Depends(get_current_user)):
    """List all user-uploaded documents currently in the index for the authenticated user."""
    docs_raw = list_uploaded_documents(user_id=current_user.id)
    docs = [DocumentInfo(**d) for d in docs_raw]
    return DocumentListResponse(documents=docs, total=len(docs))


@app.delete("/documents/{doc_id}", response_model=DeleteResponse, tags=["Documents"])
async def delete_document(doc_id: str, current_user: UserModel = Depends(get_current_user)):
    """Remove an authenticated user's document and all its chunks from the index."""
    deleted = delete_uploaded_document(doc_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No document found with doc_id='{doc_id}' or permission denied",
        )
    return DeleteResponse(message="Document deleted successfully.", doc_id=doc_id)

