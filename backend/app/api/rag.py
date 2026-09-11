from fastapi import APIRouter, Query
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["RAG"])

@router.get("/search")
def search_statutory_laws(query: str = Query(..., description="Legal topic or statutory query")):
    """
    Retrieves external statutory laws and legal precedents.
    Separated from internal contract clauses.
    """
    results = RAGService.query_legal_references(query=query, top_k=3)
    return {
        "query": query,
        "results_count": len(results),
        "external_legal_references": results
    }
