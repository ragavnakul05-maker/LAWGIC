from typing import List, Dict, Any

STATUTORY_LEGAL_KNOWLEDGE_BASE = [
    {
        "id": "STAT-001",
        "jurisdiction": "Commercial Law General",
        "statute_code": "UCC § 2-718",
        "title": "Liquidation or Limitation of Damages; Deposits",
        "content": "Damages for breach by either party may be liquidated in the agreement but only at an amount which is reasonable in the light of the anticipated or actual harm caused by the breach, the difficulties of proof of loss, and the inconvenience or nonfeasibility of otherwise obtaining an adequate remedy. A term fixing unreasonably large liquidated damages is void as a penalty."
    },
    {
        "id": "STAT-002",
        "jurisdiction": "Federal / Prompt Payment",
        "statute_code": "31 U.S.C. § 3902",
        "title": "Interest Penalties on Late Payments",
        "content": "An agency that does not pay a business concern for each complete delivered item of property or service by the required payment date shall pay an interest penalty to the business concern on the amount due, calculated under published interest rate standards for the applicable period."
    },
    {
        "id": "STAT-003",
        "jurisdiction": "Contract Law",
        "statute_code": "Section 74 - Indian Contract Act 1872",
        "title": "Compensation for Breach of Contract where Penalty is Stipulated",
        "content": "When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of such breach, or if the contract contains any other stipulation by way of penalty, the party complaining of the breach is entitled to receive reasonable compensation not exceeding the amount so named or the penalty stipulated."
    },
    {
        "id": "STAT-004",
        "jurisdiction": "Service Level Agreements",
        "statute_code": "ISO/IEC 19086-2",
        "title": "Cloud Computing Service Level Agreement (SLA) Metric Validation",
        "content": "SLA performance metrics must specify measurement intervals, downtime calculation exclusions (such as scheduled maintenance), and deterministic credit/deduction formulas tied strictly to empirical telemetry."
    }
]

class RAGService:
    @staticmethod
    def query_legal_references(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves relevant external statutory laws and legal precedents.
        Distinctly marked as EXTERNAL LEGAL REFERENCE (separated from contract clauses).
        """
        query_words = set(query.lower().split())
        results = []

        for doc in STATUTORY_LEGAL_KNOWLEDGE_BASE:
            text = (doc["title"] + " " + doc["content"]).lower()
            doc_words = set(text.split())
            overlap = len(query_words.intersection(doc_words))
            
            results.append({
                "score": overlap,
                "document": doc
            })

        # Sort by relevance score
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = [r["document"] for r in results[:top_k]]
        return top_results
