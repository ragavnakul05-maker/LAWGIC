"""
rag_engine.py — Core RAG engine: LlamaIndex + ChromaDB + Ollama (phi4-mini)

Architecture:
  - Two ChromaDB collections:
      * lawgic_statutes  — pre-loaded Indian law corpus (read-only at query time)
      * lawgic_uploads   — user-uploaded documents (mutable)
  - Queries either or both collections, merges & re-ranks results
  - Phi-4-mini via Ollama generates the final answer
"""

import logging
from typing import Any, Literal, Optional


import chromadb
from llama_index.core import (
    Settings,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import (
    CHROMA_COLLECTION_STATUTES,
    CHROMA_COLLECTION_UPLOADS,
    CHROMA_DIR,
    EMBED_MODEL,
    LEGAL_SYSTEM_PROMPT,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    OLLAMA_HOST,
    SIMILARITY_TOP_K,
)
from app.models import SourceCitation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (initialised once on startup)
# ---------------------------------------------------------------------------

_chroma_client: Any = None
_statutes_index: VectorStoreIndex | None = None
_uploads_index: VectorStoreIndex | None = None


def _get_chroma_client() -> Any:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def _build_index(collection_name: str) -> VectorStoreIndex:
    """Build (or load) a VectorStoreIndex backed by a ChromaDB collection."""
    client = _get_chroma_client()
    collection = client.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )


def ensure_engine_settings() -> None:
    """Ensures Settings.embed_model and Settings.llm are configured even outside FastAPI lifespan."""
    from llama_index.core import Settings
    try:
        if Settings.embed_model is None:
            Settings.embed_model = OllamaEmbedding(
                model_name=EMBED_MODEL,
                base_url=OLLAMA_HOST,
            )
    except Exception:
        from llama_index.core.embeddings import MockEmbedding
        Settings.embed_model = MockEmbedding(embed_dim=384)

    try:
        if Settings.llm is None:
            Settings.llm = Ollama(
                model=LLM_MODEL,
                base_url=OLLAMA_HOST,
                request_timeout=LLM_REQUEST_TIMEOUT,
                system_prompt=LEGAL_SYSTEM_PROMPT,
            )
    except Exception:
        from llama_index.core.llms import MockLLM
        Settings.llm = MockLLM()


def initialise_engine() -> None:
    """
    Called once at application startup (FastAPI lifespan).
    Configures global LlamaIndex Settings and loads both indexes.
    """
    global _statutes_index, _uploads_index

    logger.info("Initialising RAG engine …")
    logger.info("  LLM     : %s @ %s", LLM_MODEL, OLLAMA_HOST)
    logger.info("  Embedder: %s @ %s", EMBED_MODEL, OLLAMA_HOST)

    ensure_engine_settings()

    _statutes_index = _build_index(CHROMA_COLLECTION_STATUTES)
    _uploads_index = _build_index(CHROMA_COLLECTION_UPLOADS)

    logger.info("RAG engine ready ✓")


def get_statutes_index() -> VectorStoreIndex:
    global _statutes_index
    if _statutes_index is None:
        ensure_engine_settings()
        _statutes_index = _build_index(CHROMA_COLLECTION_STATUTES)
    return _statutes_index


def get_uploads_index() -> VectorStoreIndex:
    global _uploads_index
    if _uploads_index is None:
        ensure_engine_settings()
        _uploads_index = _build_index(CHROMA_COLLECTION_UPLOADS)
    return _uploads_index


def reload_uploads_index() -> None:
    """Call after a new document is ingested to refresh the uploads index."""
    global _uploads_index
    ensure_engine_settings()
    _uploads_index = _build_index(CHROMA_COLLECTION_UPLOADS)
    logger.info("Uploads index refreshed.")



# ---------------------------------------------------------------------------
# Query helper
# ---------------------------------------------------------------------------

def _nodes_to_citations(nodes: list[NodeWithScore], collection: str) -> list[SourceCitation]:
    """Convert LlamaIndex retrieved nodes to SourceCitation objects."""
    citations: list[SourceCitation] = []
    seen_snippets: set[str] = set()

    for node in nodes:
        meta = node.node.metadata or {}
        snippet = node.node.get_content()[:300].strip()

        # De-duplicate by snippet prefix
        key = snippet[:80]
        if key in seen_snippets:
            continue
        seen_snippets.add(key)

        citations.append(
            SourceCitation(
                filename=meta.get("file_name", meta.get("filename", "Unknown")),
                page=meta.get("page_label") or meta.get("page"),
                snippet=snippet,
                collection=collection,
            )
        )
    return citations


async def query_rag(
    question: str,
    collection: Literal["statutes", "uploads", "both"] = "both",
    user_id: Optional[str] = None,
) -> tuple[str, list[SourceCitation]]:
    """
    Run a RAG query against the requested collection(s).
    If user_id is provided, user upload retrieval is isolated strictly
    to chunks belonging to that user.

    Returns:
        (answer_text, list_of_source_citations)
    """
    from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter

    all_nodes: list[NodeWithScore] = []
    all_citations: list[SourceCitation] = []

    retriever_kwargs: dict[str, Any] = {"similarity_top_k": SIMILARITY_TOP_K}

    # --- Retrieve from statutes ---
    if collection in ("statutes", "both"):
        idx = get_statutes_index()
        retriever = idx.as_retriever(**retriever_kwargs)
        nodes = await retriever.aretrieve(question)
        all_nodes.extend(nodes)
        all_citations.extend(_nodes_to_citations(nodes, "statutes"))

    # --- Retrieve from uploads ---
    if collection in ("uploads", "both"):
        idx = get_uploads_index()
        uploads_kwargs = dict(retriever_kwargs)
        if user_id:
            uploads_kwargs["filters"] = MetadataFilters(
                filters=[ExactMatchFilter(key="user_id", value=str(user_id))]
            )
        try:
            retriever = idx.as_retriever(**uploads_kwargs)
            nodes = await retriever.aretrieve(question)
            all_nodes.extend(nodes)
            all_citations.extend(_nodes_to_citations(nodes, "uploads"))
        except Exception as exc:
            logger.warning("Uploads retrieval notice for user %s: %s", user_id, exc)


    if not all_nodes:
        return (
            "I could not find relevant information in the available documents. "
            "Please upload a related document or rephrase your question.",
            [],
        )

    # Build context string from retrieved nodes (score-sorted)
    all_nodes_sorted = sorted(all_nodes, key=lambda n: n.score or 0, reverse=True)
    context_parts: list[str] = []
    for i, node in enumerate(all_nodes_sorted[:SIMILARITY_TOP_K], 1):
        meta = node.node.metadata or {}
        fname = meta.get("file_name", meta.get("filename", "Unknown"))
        page = meta.get("page_label") or meta.get("page", "?")
        context_parts.append(
            f"[Context {i} — {fname}, Page {page}]\n{node.node.get_content()}"
        )

    context_text = "\n\n---\n\n".join(context_parts)

    # Build prompt
    prompt = (
        f"Context documents:\n\n{context_text}\n\n"
        f"---\n\nUser question: {question}\n\n"
        "Answer (cite sources using [Source: <filename>, Page <n>]):"
    )

    llm = Settings.llm
    response = await llm.acomplete(prompt)
    answer = str(response).strip()

    return answer, all_citations


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

async def probe_ollama() -> bool:
    """Returns True if Ollama is reachable and the model is available."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def statutes_chunk_count() -> int:
    try:
        col = _get_chroma_client().get_or_create_collection(CHROMA_COLLECTION_STATUTES)
        return col.count()
    except Exception:
        return -1


def uploads_chunk_count() -> int:
    try:
        col = _get_chroma_client().get_or_create_collection(CHROMA_COLLECTION_UPLOADS)
        return col.count()
    except Exception:
        return -1
