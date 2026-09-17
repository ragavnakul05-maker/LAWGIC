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
from app.rag_engine import get_uploads_index, reload_uploads_index, ensure_engine_settings

logger = logging.getLogger(__name__)



from typing import Any
def _get_chroma_client() -> Any:
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


import os
import tempfile
from app.core.encryption import (
    encrypt_bytes,
    decrypt_bytes,
    secure_filename,
    validate_file_content,
    get_user_storage_path,
)

async def ingest_uploaded_file(file_bytes: bytes, original_filename: str, user_id: str = "default_user") -> dict:
    """
    Ingest a single user-uploaded file into the uploads collection with:
      - Magic-byte & file-extension validation
      - Safe filename sanitization
      - AES-128 Fernet encryption at rest in dedicated user folder
      - Automatic temporary-file cleanup after embedding
      - Per-user metadata isolation
    """
    safe_filename = secure_filename(original_filename)
    validate_file_content(file_bytes, safe_filename)

    doc_id = str(uuid.uuid4())
    
    # Encrypt and save to user's private storage directory
    user_dir = get_user_storage_path(user_id, str(UPLOADS_DIR))
    save_name = f"{doc_id}_{safe_filename}.enc"
    save_path = user_dir / save_name
    save_path.write_bytes(encrypt_bytes(file_bytes))
    logger.info("Saved encrypted upload for user %s: %s", user_id, save_path)

    # Ingest document into vector store using secure temporary file with guaranteed cleanup
    suffix = Path(safe_filename).suffix.lower()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        temp_file.write(file_bytes)
        temp_file.flush()
        temp_file.close()

        logger.info("Parsing uploaded file for user %s: %s", user_id, safe_filename)
        documents = SimpleDirectoryReader(
            input_files=[temp_file.name],
            filename_as_id=True,
        ).load_data()
    finally:
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass

    # Attach tenant-isolated metadata for citation display and user-scoped retrieval
    for doc in documents:
        doc.id_ = doc_id
        doc.metadata["file_name"] = safe_filename
        doc.metadata["doc_id"] = doc_id
        doc.metadata["user_id"] = str(user_id)

    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)
    for node in nodes:
        node.metadata["doc_id"] = doc_id
        node.metadata["file_name"] = safe_filename
        node.metadata["user_id"] = str(user_id)

    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)
    ensure_engine_settings()
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes, storage_context=storage_context)

    # Refresh the in-memory uploads index
    reload_uploads_index()


    logger.info("✓ Ingested %d encrypted chunks for '%s' (doc_id=%s, user_id=%s)", len(nodes), safe_filename, doc_id, user_id)
    return {
        "filename": safe_filename,
        "doc_id": doc_id,
        "chunks_indexed": len(nodes),
    }


def list_uploaded_documents(user_id: str = "default_user") -> list[dict]:
    """Return metadata about uploaded documents belonging strictly to user_id."""
    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)

    results = collection.get(where={"user_id": str(user_id)}, include=["metadatas"])
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


def delete_uploaded_document(doc_id: str, user_id: str = "default_user") -> bool:
    """
    Delete all chunks belonging to `doc_id` owned by `user_id` from the uploads collection.
    Also securely removes the encrypted file from user's storage.
    Returns True if any chunks were deleted.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(CHROMA_COLLECTION_UPLOADS)

    # Find IDs of chunks belonging to this doc AND owned by user_id
    results = collection.get(
        where={"$and": [{"doc_id": doc_id}, {"user_id": str(user_id)}]},
        include=["metadatas"]
    )
    ids_to_delete = results.get("ids") or []

    if not ids_to_delete:
        logger.warning("No chunks found for doc_id=%s belonging to user_id=%s", doc_id, user_id)
        return False

    collection.delete(ids=ids_to_delete)
    logger.info("Deleted %d chunks for doc_id=%s (user_id=%s)", len(ids_to_delete), doc_id, user_id)

    # Remove encrypted file from user's private storage
    user_dir = get_user_storage_path(user_id, str(UPLOADS_DIR))
    for f in user_dir.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)
        logger.info("Removed encrypted file: %s", f)

    # Clean legacy unencrypted location if present
    for f in UPLOADS_DIR.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)

    reload_uploads_index()
    return True

