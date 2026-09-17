from fastapi import APIRouter, Query, Depends
from app.services.rag_service import RAGService
from app.core.security import get_current_user
from app.models.schemas import UserModel

router = APIRouter(prefix="/rag", tags=["RAG"])

@router.get("/search")
def search_statutory_laws(
    query: str = Query(..., description="Legal topic or statutory query"),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Retrieves external statutory laws and legal precedents.
    Separated from internal contract clauses.
    Requires authenticated user session.
    """
    results = RAGService.query_legal_references(query=query, top_k=3)
    return {
        "query": query,
        "results_count": len(results),
        "external_legal_references": results
    }

