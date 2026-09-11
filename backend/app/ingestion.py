"""
ingestion.py — Document ingestion pipeline for Lawgic RAG

Handles:
  - PDF and DOCX parsing
  - Chunking with overlap
  - Embedding via nomic-embed-text (Ollama)
  - Storage into ChromaDB (statutes or uploads collection)
  - Bulk ingestion of the pre-loaded statutes corpus on first boot
"""

import logging
import shutil
import uuid
from pathlib import Path

import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import (
    CHROMA_COLLECTION_STATUTES,
    CHROMA_COLLECTION_UPLOADS,
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    STATUTES_DIR,
    UPLOADS_DIR,
)
from app.rag_engine import get_uploads_index, reload_uploads_index

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _ingest_directory(
    directory: Path,
    collection_name: str,
    *,
    recursive: bool = True,
) -> int:
    """
    Ingest all supported files from `directory` into `collection_name`.
    Returns the number of chunks indexed.
    """
    if not directory.exists() or not any(directory.iterdir()):
        logger.warning("Directory %s is empty or missing — skipping ingestion.", directory)
        return 0

    logger.info("Loading documents from %s …", directory)
    documents = SimpleDirectoryReader(
        str(directory),
        recursive=recursive,
        # Supported formats out of the box: PDF, DOCX, TXT, MD, CSV
        required_exts=[".pdf", ".docx", ".txt", ".md"],
        filename_as_id=True,
    ).load_data()

    if not documents:
        logger.warning("No documents found in %s.", directory)
        return 0

    logger.info("  Loaded %d document(s). Chunking …", len(documents))

    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)
    logger.info("  Created %d chunks. Embedding & storing …", len(nodes))

    client = _get_chroma_client()
    collection = client.get_or_create_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    VectorStoreIndex(nodes, storage_context=storage_context)
    logger.info("  ✓ %d chunks stored in collection '%s'.", len(nodes), collection_name)
    return len(nodes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_statutes_corpus() -> int:
    """
    Bulk-ingest the pre-loaded Indian law corpus from data/statutes/.
    Only runs if the statutes collection is empty (idempotent).
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_STATUTES)

    if collection.count() > 0:
        logger.info(
            "Statutes collection already has %d chunks — skipping re-ingestion.",
            collection.count(),
        )
        return collection.count()

    logger.info("=== Ingesting statutes corpus (first-time setup) ===")
    count = _ingest_directory(STATUTES_DIR, CHROMA_COLLECTION_STATUTES)
    logger.info("=== Statutes corpus ready: %d chunks ===", count)
    return count


async def ingest_uploaded_file(file_bytes: bytes, original_filename: str) -> dict:
    """
    Ingest a single user-uploaded file into the uploads collection.

    Returns a dict with: filename, doc_id, chunks_indexed
    """
    suffix = Path(original_filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md"}:
        raise ValueError(f"Unsupported file type: {suffix}")

    doc_id = str(uuid.uuid4())
    # Save with doc_id prefix to avoid collisions
    save_name = f"{doc_id}_{original_filename}"
    save_path = UPLOADS_DIR / save_name

    save_path.write_bytes(file_bytes)
    logger.info("Saved upload: %s", save_path)

    # Ingest just this file
    logger.info("Ingesting uploaded file: %s", original_filename)
    documents = SimpleDirectoryReader(
        input_files=[str(save_path)],
        filename_as_id=True,
    ).load_data()

    # Attach extra metadata for citation display
    for doc in documents:
        doc.metadata["file_name"] = original_filename
        doc.metadata["doc_id"] = doc_id

    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)

    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes, storage_context=storage_context)

    # Refresh the in-memory uploads index
    reload_uploads_index()

    logger.info("✓ Ingested %d chunks for '%s' (doc_id=%s)", len(nodes), original_filename, doc_id)
    return {
        "filename": original_filename,
        "doc_id": doc_id,
        "chunks_indexed": len(nodes),
    }


def list_uploaded_documents() -> list[dict]:
    """Return metadata about all uploaded documents."""
    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)

    results = collection.get(include=["metadatas"])
    metadatas = results.get("metadatas") or []

    # Aggregate by doc_id
    seen: dict[str, dict] = {}
    for meta in metadatas:
        if not meta:
            continue
        did = meta.get("doc_id", "unknown")
        if did not in seen:
            seen[did] = {
                "doc_id": did,
                "filename": meta.get("file_name", "Unknown"),
                "collection": "uploads",
                "chunks": 0,
            }
        seen[did]["chunks"] += 1

    return list(seen.values())


def delete_uploaded_document(doc_id: str) -> bool:
    """
    Delete all chunks belonging to `doc_id` from the uploads collection.
    Also removes the saved file from disk.
    Returns True if any chunks were deleted.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)

    # Find IDs of chunks belonging to this doc
    results = collection.get(where={"doc_id": doc_id}, include=["metadatas"])
    ids_to_delete = results.get("ids") or []

    if not ids_to_delete:
        logger.warning("No chunks found for doc_id=%s", doc_id)
        return False

    collection.delete(ids=ids_to_delete)
    logger.info("Deleted %d chunks for doc_id=%s", len(ids_to_delete), doc_id)

    # Remove file from disk
    for f in UPLOADS_DIR.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)
        logger.info("Removed file: %s", f)

    reload_uploads_index()
    return True
