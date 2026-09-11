# Lawgic RAG Backend

A **FastAPI** + **LlamaIndex** + **ChromaDB** + **Ollama (Phi-4-mini)** backend that powers the RAG (Retrieval-Augmented Generation) feature of [Lawgic](https://lawgic-phi.vercel.app/).

---

## ✨ Features

| Feature | Details |
|---|---|
| **LLM** | Phi-4-mini via Ollama — ~3.8 GB, well under 5 GB limit |
| **Embedder** | nomic-embed-text via Ollama |
| **Vector DB** | ChromaDB (persistent) |
| **Corpus** | Pre-loaded Indian law statutes (ICA, IPC, CPC, Arbitration Act…) |
| **Uploads** | Runtime PDF/DOCX upload & indexing |
| **API** | FastAPI with Swagger UI at `/docs` |
| **Streaming** | SSE token streaming at `POST /chat/stream` |

---

## 🚀 Quick Start (Docker — Recommended)

### Prerequisites
- Docker Desktop installed and running
- 8 GB+ RAM available

```bash
# 1. Clone / navigate to this directory
cd lawgic-backend

# 2. Copy env template (edit if needed)
cp .env.example .env

# 3. Start everything
docker compose up --build
```

> ⚠️ First boot downloads Phi-4-mini (~3.8 GB) and nomic-embed-text. This may take 5–15 minutes depending on your internet speed. Subsequent starts are instant.

Once running:
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 🖥️ Local Development (without Docker)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) installed and running

```bash
# 1. Pull the required models
ollama pull phi4-mini
ollama pull nomic-embed-text

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit environment
cp .env.example .env

# 5. (Optional) Add statute PDFs
# Place PDF files in data/statutes/ — they'll be indexed on first startup

# 6. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 Adding Statute Documents

Place PDF/DOCX/TXT files in the `data/statutes/` folder **before first boot**. They will be automatically indexed into ChromaDB. On subsequent boots, if the statutes collection already has data, indexing is skipped.

**Recommended sources (all public domain):**
- [Indian Contract Act, 1872 (PDF)](https://legislative.gov.in/sites/default/files/A1872-09.pdf)
- [Indian Penal Code, 1860 (PDF)](https://legislative.gov.in/sites/default/files/A1860-45.pdf)
- [Arbitration and Conciliation Act, 1996 (PDF)](https://legislative.gov.in/sites/default/files/A1996-26.pdf)

---

## 🌐 API Reference

### `GET /health`
Returns server and model status.

### `POST /chat`
```json
// Request
{ "question": "What are the termination clauses?", "collection": "both" }

// Response
{
  "answer": "Under Section 73 … [Source: ICA.pdf, Page 42]",
  "sources": [{ "filename": "ICA.pdf", "page": 42, "snippet": "…", "collection": "statutes" }],
  "model": "phi4-mini",
  "question": "…"
}
```

### `POST /chat/stream`
Same request body as `/chat`. Returns `text/event-stream` (SSE) — each `data:` event is a token chunk. Ends with `data: [DONE]`.

### `POST /ingest`
`multipart/form-data` with field `file`. Accepts `.pdf`, `.docx`, `.txt`, `.md`.

### `GET /documents`
Lists all user-uploaded documents.

### `DELETE /documents/{doc_id}`
Removes a document and all its chunks.

---

## ☁️ Cloud Deployment (Railway / Render)

1. Push this repo to GitHub
2. Create a new Railway / Render service from the repo
3. Set **Start Command**: `docker compose up --build` (or use their native Docker support)
4. Set environment variables (see `.env.example`)
5. Update `CORS_ORIGINS` to include your Vercel URL
6. Copy the deployed URL → set as `VITE_RAG_API_URL` in your Vercel project env

---

## 🧪 Running Tests

```bash
pytest app/tests/ -v
```

---

## 📁 Project Structure

```
lawgic-backend/
├── app/
│   ├── main.py          # FastAPI app + all routes
│   ├── rag_engine.py    # LlamaIndex + ChromaDB + Ollama
│   ├── ingestion.py     # Document parsing & indexing
│   ├── models.py        # Pydantic schemas
│   ├── config.py        # Settings
│   └── tests/
│       └── test_api.py
├── data/
│   ├── statutes/        # Pre-loaded law corpus (add PDFs here)
│   └── uploads/         # Runtime user uploads (auto-created)
├── chroma_db/           # Vector store (auto-created)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
