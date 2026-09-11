"""
tests/test_api.py — Basic integration tests for Lawgic RAG API
Run with: pytest app/tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    """Create a test client with mocked startup events."""
    with (
        patch("app.main.initialise_engine"),
        patch("app.main.ingest_statutes_corpus"),
    ):
        from app.main import app
        with TestClient(app) as c:
            yield c


def test_health_check(client):
    """Health endpoint should return 200."""
    with patch("app.main.probe_ollama", new_callable=AsyncMock, return_value=True), \
         patch("app.main.statutes_chunk_count", return_value=100), \
         patch("app.main.uploads_chunk_count", return_value=5):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ollama_reachable"] is True


def test_chat_returns_answer(client):
    """Chat endpoint should return an answer and sources list."""
    mock_answer = "Under Section 73 of the Indian Contract Act, 1872, compensation is due. [Source: ICA.pdf, Page 42]"
    mock_sources = []

    with patch("app.main.query_rag", new_callable=AsyncMock, return_value=(mock_answer, mock_sources)):
        resp = client.post("/chat", json={"question": "What is compensation under ICA?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == mock_answer
    assert isinstance(data["sources"], list)
    assert "question" in data


def test_chat_empty_question_rejected(client):
    """Questions shorter than 3 characters should be rejected by Pydantic."""
    resp = client.post("/chat", json={"question": "hi"})
    assert resp.status_code == 422


def test_ingest_unsupported_format(client):
    """Uploading a .exe file should return 400."""
    resp = client.post(
        "/ingest",
        files={"file": ("malware.exe", b"fake-binary", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_ingest_pdf(client):
    """Valid PDF upload should return 200 with chunk count."""
    mock_result = {"filename": "test.pdf", "doc_id": "abc-123", "chunks_indexed": 10}
    with patch("app.main.ingest_uploaded_file", new_callable=AsyncMock, return_value=mock_result):
        resp = client.post(
            "/ingest",
            files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chunks_indexed"] == 10
    assert data["doc_id"] == "abc-123"


def test_list_documents_empty(client):
    """Documents list should return empty list when no uploads."""
    with patch("app.main.list_uploaded_documents", return_value=[]):
        resp = client.get("/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["documents"] == []


def test_delete_nonexistent_document(client):
    """Deleting a non-existent doc should return 404."""
    with patch("app.main.delete_uploaded_document", return_value=False):
        resp = client.delete("/documents/nonexistent-id")
    assert resp.status_code == 404
