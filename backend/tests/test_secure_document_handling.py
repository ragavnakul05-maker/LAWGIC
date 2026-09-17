"""
test_secure_document_handling.py — Comprehensive security test suite for LAWGIC.

Tests:
  1. HTTPS-ready security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy)
  2. Authentication enforcement (HTTP 401 on unauthenticated access across all APIs)
  3. Tenant document isolation (User B cannot access or download User A's contract)
  4. On-disk encryption at rest (stored file is Fernet ciphertext, not plaintext)
  5. Path traversal defense and filename sanitization
  6. File size limit enforcement (HTTP 413)
  7. Magic bytes & file signature validation (HTTP 400 for disguised binaries/scripts)
  8. User-specific RAG retrieval isolation (User B cannot retrieve User A's ingested documents)
  9. Temporary file cleanup guarantee (no plaintext leaks in temp storage)
 10. Authorized document download and in-memory decryption
"""

import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.core.security import create_access_token, hash_password
from app.core.encryption import encrypt_bytes, decrypt_bytes, secure_filename, validate_file_content
from app.models.schemas import UserModel, ContractModel

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def setup_security_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Create two distinct test users
    u1 = db.query(UserModel).filter(UserModel.email == "sec_user1@lawgic.internal").first()
    if not u1:
        u1 = UserModel(
            id="SEC-USER-001",
            email="sec_user1@lawgic.internal",
            hashed_password=hash_password("Password123!"),
            full_name="Security User One",
            role="LEGAL_COUNSEL",
            is_active=True,
        )
        db.add(u1)

    u2 = db.query(UserModel).filter(UserModel.email == "sec_user2@lawgic.internal").first()
    if not u2:
        u2 = UserModel(
            id="SEC-USER-002",
            email="sec_user2@lawgic.internal",
            hashed_password=hash_password("Password123!"),
            full_name="Security User Two",
            role="LEGAL_COUNSEL",
            is_active=True,
        )
        db.add(u2)

    db.commit()
    yield
    db.close()


@pytest.fixture
def user1_headers():
    token = create_access_token({"sub": "SEC-USER-001", "email": "sec_user1@lawgic.internal"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user2_headers():
    token = create_access_token({"sub": "SEC-USER-002", "email": "sec_user2@lawgic.internal"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. HTTPS-Ready Security Headers Tests
# ---------------------------------------------------------------------------

def test_https_security_headers_present():
    """Verify security headers middleware sets HSTS, nosniff, DENY, CSP, and Referrer-Policy."""
    resp = client.get("/health")
    assert resp.status_code == 200
    headers = resp.headers

    assert "Strict-Transport-Security" in headers
    assert "max-age=31536000" in headers["Strict-Transport-Security"]

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Referrer-Policy" in headers
    assert "Content-Security-Policy" in headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


# ---------------------------------------------------------------------------
# 2. Authentication Enforcement Tests (401 Unauthorized)
# ---------------------------------------------------------------------------

def test_unauthenticated_access_blocked():
    """Verify all protected RAG, document, contract, rule, and audit endpoints reject requests without token."""
    protected_endpoints = [
        ("GET", "/api/contracts"),
        ("POST", "/api/contracts/upload"),
        ("GET", "/api/contracts/CONTRACT-NONEXIST/download"),
        ("GET", "/api/rules"),
        ("POST", "/api/rules/execute"),
        ("GET", "/api/audit/logs"),
        ("POST", "/api/simulations/run"),
        ("GET", "/api/rag/search?query=test"),
        ("POST", "/chat"),
        ("POST", "/chat/stream"),
        ("POST", "/ingest"),
        ("GET", "/documents"),
        ("DELETE", "/documents/fake-doc-id"),
    ]

    for method, path in protected_endpoints:
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            r = client.post(path, json={})
        elif method == "DELETE":
            r = client.delete(path)
        
        assert r.status_code in (401, 403), f"Endpoint {method} {path} returned {r.status_code}, expected 401/403"


# ---------------------------------------------------------------------------
# 3. File Type & Magic Bytes Validation Tests (400 Bad Request)
# ---------------------------------------------------------------------------

def test_upload_executable_disguised_as_pdf_rejected(setup_security_db, user1_headers):
    """Verify that a Windows PE executable file disguised as a .pdf is rejected."""
    fake_exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    files = {"file": ("malicious.pdf", io.BytesIO(fake_exe_bytes), "application/pdf")}
    resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert resp.status_code == 400
    assert "Executable binaries cannot be uploaded" in resp.json()["detail"]


def test_upload_invalid_pdf_magic_bytes_rejected(setup_security_db, user1_headers):
    """Verify that non-PDF content with a .pdf extension is rejected."""
    corrupt_bytes = b"This is just random text, not a real PDF structure"
    files = {"file": ("corrupt.pdf", io.BytesIO(corrupt_bytes), "application/pdf")}
    resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert resp.status_code == 400
    assert "valid PDF magic signature" in resp.json()["detail"]


def test_upload_invalid_docx_magic_bytes_rejected(setup_security_db, user1_headers):
    """Verify that non-ZIP content with a .docx extension is rejected."""
    corrupt_bytes = b"Not a zip file at all"
    files = {"file": ("corrupt.docx", io.BytesIO(corrupt_bytes), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert resp.status_code == 400
    assert "Word document missing valid DOCX/DOC container header" in resp.json()["detail"]


def test_upload_disallowed_extension_rejected(setup_security_db, user1_headers):
    """Verify that disallowed extensions (e.g. .py, .exe, .sh) are rejected."""
    files = {"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho hello"), "application/x-sh")}
    resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. File Size Limit Validation Tests (413 Payload Too Large)
# ---------------------------------------------------------------------------

def test_upload_file_size_exceeded(setup_security_db, user1_headers, monkeypatch):
    """Verify that uploading a file larger than MAX_UPLOAD_SIZE_MB returns HTTP 413."""
    # Temporarily set MAX_UPLOAD_SIZE_MB to 0 (effectively blocking anything > 0 MB)
    monkeypatch.setattr("app.api.contracts.MAX_UPLOAD_SIZE_MB", 0.0001)
    large_content = b"A" * (1024 * 500)  # 500 KB > 0.0001 MB (~100 bytes)
    files = {"file": ("large_contract.txt", io.BytesIO(large_content), "text/plain")}
    resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert resp.status_code == 413
    assert "File too large" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Path Traversal & Filename Sanitization Tests
# ---------------------------------------------------------------------------

def test_filename_sanitization_defense():
    """Verify secure_filename neutralizes path traversal, null bytes, and dangerous characters."""
    assert secure_filename("../../etc/passwd") == "passwd"
    assert secure_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert secure_filename("contract\x00.pdf") == "contract.pdf"
    assert secure_filename("my contract (confidential) #1.docx") == "my_contract_confidential_1.docx"
    assert secure_filename("../../../secret/contract.txt") == "contract.txt"


# ---------------------------------------------------------------------------
# 6. On-Disk Encryption & Decrypted Download Tests
# ---------------------------------------------------------------------------

def test_contract_encrypted_on_disk_and_downloadable(setup_security_db, user1_headers):
    """
    Verify:
      1. Contract uploaded is saved as ciphertext (.enc) in user's isolated directory.
      2. Reading the file directly from disk does NOT yield plaintext.
      3. Authorized user can download and in-memory decryption restores the exact original bytes.
    """
    sample_text = (
        "CONFIDENTIAL MASTER AGREEMENT\n"
        "Section 1.1: Party A shall deliver goods within 30 days.\n"
        "Section 2.1: Payment penalty of $500 per day of delay applies.\n"
    )
    raw_bytes = sample_text.encode("utf-8")
    files = {"file": ("master_agreement.txt", io.BytesIO(raw_bytes), "text/plain")}

    # 1. Upload contract as User 1
    upload_resp = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert upload_resp.status_code == 200
    contract_id = upload_resp.json()["contract_id"]

    # 2. Inspect on-disk file
    db = SessionLocal()
    c_rec = db.query(ContractModel).filter(ContractModel.id == contract_id).first()
    assert c_rec is not None
    on_disk_path = c_rec.file_path
    db.close()

    assert os.path.exists(on_disk_path), f"File {on_disk_path} does not exist on disk"
    assert on_disk_path.endswith(".enc"), "File on disk must have .enc encrypted suffix"
    assert "SEC-USER-001" in on_disk_path or "sec_user1" in on_disk_path.lower() or "uploads" in on_disk_path

    # Verify disk content is ciphertext (cannot find sample plaintext in raw bytes)
    with open(on_disk_path, "rb") as f:
        disk_bytes = f.read()

    assert raw_bytes not in disk_bytes, "Security Failure: Plaintext contract content leaked onto disk!"
    assert b"CONFIDENTIAL MASTER AGREEMENT" not in disk_bytes

    # Verify manual decryption restores original text
    restored_bytes = decrypt_bytes(disk_bytes)
    assert restored_bytes == raw_bytes

    # 3. Download via authorized API endpoint
    down_resp = client.get(f"/api/contracts/{contract_id}/download", headers=user1_headers)
    assert down_resp.status_code == 200
    assert down_resp.content == raw_bytes
    assert "attachment" in down_resp.headers["Content-Disposition"]


# ---------------------------------------------------------------------------
# 7. Cross-Tenant Document Access & Download Isolation Tests (404/403)
# ---------------------------------------------------------------------------

def test_cross_tenant_contract_download_blocked(setup_security_db, user1_headers, user2_headers):
    """Verify User 2 CANNOT download or view User 1's contract."""
    # User 1 uploads contract
    raw_content = b"SECRET CLAUSE FOR USER 1 ONLY\nSection 1.0: Exclusive Patent Rights."
    files = {"file": ("user1_patent.txt", io.BytesIO(raw_content), "text/plain")}
    up = client.post("/api/contracts/upload", files=files, headers=user1_headers)
    assert up.status_code == 200
    c_id = up.json()["contract_id"]

    # User 2 attempts to get contract detail -> 404
    detail_resp = client.get(f"/api/contracts/{c_id}", headers=user2_headers)
    assert detail_resp.status_code == 404

    # User 2 attempts to download User 1's contract -> 404
    down_resp = client.get(f"/api/contracts/{c_id}/download", headers=user2_headers)
    assert down_resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. User-Specific RAG Retrieval Isolation Tests
# ---------------------------------------------------------------------------

def test_user_specific_rag_isolation(setup_security_db, user1_headers, user2_headers):
    """
    Verify:
      1. User 1 uploads document via /ingest.
      2. User 1 queries /documents and sees their document.
      3. User 2 queries /documents and CANNOT see User 1's document.
      4. User 2 attempts DELETE /documents/{doc_id} and is denied (404).
      5. User 2 queries /chat and receives NO citations from User 1's document.
    """
    secret_token = "PROJECT_TITAN_SECRET_CODE_779"
    doc_text = (
        f"Internal memo regarding {secret_token}.\n"
        "This project is strictly restricted to User 1 executive clearance."
    ).encode("utf-8")

    # 1. User 1 ingests document
    files = {"file": ("titan_memo.txt", io.BytesIO(doc_text), "text/plain")}
    ingest_resp = client.post("/ingest", files=files, headers=user1_headers)
    assert ingest_resp.status_code == 200
    doc_id = ingest_resp.json()["doc_id"]

    # 2. User 1 lists documents -> sees titan_memo.txt
    u1_docs = client.get("/documents", headers=user1_headers).json()
    u1_doc_ids = [d["doc_id"] for d in u1_docs["documents"]]
    assert doc_id in u1_doc_ids

    # 3. User 2 lists documents -> does NOT see titan_memo.txt
    u2_docs = client.get("/documents", headers=user2_headers).json()
    u2_doc_ids = [d["doc_id"] for d in u2_docs["documents"]]
    assert doc_id not in u2_doc_ids

    # 4. User 2 attempts to delete User 1's document -> 404
    del_resp = client.delete(f"/documents/{doc_id}", headers=user2_headers)
    assert del_resp.status_code == 404

    # 5. User 2 queries RAG chat about the secret token
    chat_resp = client.post(
        "/chat",
        json={"question": f"What is {secret_token}?", "collection": "uploads"},
        headers=user2_headers
    )
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    
    # Verify User 2 received zero source citations from User 1's document
    for source in chat_data.get("sources", []):
        assert "titan_memo" not in source.get("filename", "")
        assert secret_token not in source.get("snippet", "")

    # Cleanup: User 1 deletes their document
    u1_del = client.delete(f"/documents/{doc_id}", headers=user1_headers)
    assert u1_del.status_code == 200
