import re
from typing import Dict, Any, List, Optional, Tuple

CONTRACT_TYPES = [
    "Service Agreement",
    "Employment Agreement",
    "Vendor/Supplier Agreement",
    "Lease Agreement",
    "Purchase Agreement",
]

# Classification rule profiles
PROFILES: Dict[str, Dict[str, Any]] = {
    "Service Agreement": {
        "title_patterns": [
            r"\b(?:master\s+)?services?\s+agreement\b",
            r"\bmsa\b",
            r"\bstatement\s+of\s+work\b",
            r"\bsow\b",
            r"\bservice\s+level\s+agreement\b",
            r"\bsla\b",
            r"\bconsulting\s+(?:services\s+)?agreement\b",
            r"\bprofessional\s+services\b",
            r"\bsoftware\s+as\s+a\s+service\b",
            r"\bsaas\s+agreement\b",
            r"\bcloud\s+services?\b",
        ],
        "party_terms": ["client", "customer", "service provider", "consultant", "contractor"],
        "content_keywords": [
            "services", "deliverables", "service levels", "sla", "uptime",
            "service credits", "work orders", "scope of work", "performance standards",
            "specifications", "maintenance services", "telemetry"
        ],
        "priority_clause_types": [
            "sla_penalty", "uptime", "service level", "deliverables",
            "scope of services", "late_payment_interest"
        ]
    },
    "Employment Agreement": {
        "title_patterns": [
            r"\bemployment\s+agreement\b",
            r"\bexecutive\s+employment\b",
            r"\boffer\s+letter\b",
            r"\bemployment\s+contract\b",
            r"\bappointment\s+letter\b",
            r"\bemployee\s+agreement\b",
            r"\bseverance\s+agreement\b",
            r"\bnon-?compete\s+agreement\b",
        ],
        "party_terms": ["employer", "company", "employee", "executive", "worker"],
        "content_keywords": [
            "salary", "base salary", "compensation", "benefits", "duties",
            "job title", "probation", "probationary", "non-compete", "non-solicitation",
            "confidentiality", "termination of employment", "severance", "leave entitlement"
        ],
        "priority_clause_types": [
            "compensation", "salary", "duties", "confidentiality",
            "non-compete", "termination", "probation"
        ]
    },
    "Vendor/Supplier Agreement": {
        "title_patterns": [
            r"\b(?:master\s+)?supplier\s+agreement\b",
            r"\b(?:master\s+)?supply\s+agreement\b",
            r"\bvendor\s+agreement\b",
            r"\bprocurement\s+contract\b",
            r"\bmanufacturing\s+agreement\b",
            r"\bdistributor\s+agreement\b",
            r"\bdistribution\s+agreement\b",
            r"\brate\s+contract\b",
        ],
        "party_terms": ["buyer", "supplier", "vendor", "manufacturer", "distributor"],
        "content_keywords": [
            "purchase order", "delivery deadline", "delivery schedule", "liquidated damages",
            "delivery delay", "volume discount", "order quantities", "bulk discount",
            "lead time", "inspection", "units", "goods", "shipment"
        ],
        "priority_clause_types": [
            "delivery_delay_penalty", "volume_discount", "liquidated damages",
            "order quantities", "late_payment_interest", "delivery timeline"
        ]
    },
    "Lease Agreement": {
        "title_patterns": [
            r"\blease\s+agreement\b",
            r"\bcommercial\s+lease\b",
            r"\bresidential\s+lease\b",
            r"\brental\s+agreement\b",
            r"\btenancy\s+agreement\b",
            r"\bsublease\s+agreement\b",
            r"\bequipment\s+lease\b",
        ],
        "party_terms": ["landlord", "lessor", "tenant", "lessee"],
        "content_keywords": [
            "premises", "demised premises", "rent", "monthly rent", "security deposit",
            "maintenance", "lease term", "utilities", "occupancy", "quiet enjoyment",
            "subletting", "alterations", "eviction", "landlord"
        ],
        "priority_clause_types": [
            "rent", "security deposit", "premises", "lease term",
            "maintenance", "late_payment_interest", "termination"
        ]
    },
    "Purchase Agreement": {
        "title_patterns": [
            r"\bpurchase\s+agreement\b",
            r"\basset\s+purchase\s+agreement\b",
            r"\bstock\s+purchase\s+agreement\b",
            r"\bsale\s+and\s+purchase\b",
            r"\bbill\s+of\s+sale\b",
            r"\bpurchase\s+and\s+sale\b",
            r"\bgoods\s+purchase\b",
        ],
        "party_terms": ["buyer", "purchaser", "seller"],
        "content_keywords": [
            "purchase price", "purchased assets", "closing date", "title and risk",
            "transfer of title", "warranties", "representations and warranties",
            "as-is", "bill of sale", "conveyance", "earnest money"
        ],
        "priority_clause_types": [
            "purchase price", "closing", "warranties", "title and risk",
            "representations", "indemnification", "payment"
        ]
    },
}

class ContractClassifier:
    @classmethod
    def classify(
        cls,
        title: str,
        full_text: str = "",
        headings: Optional[List[str]] = None,
        clauses: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Hybrid classifier:
        1. Title & Heading Pattern Extraction (High Confidence Weight)
        2. Party Relationship Signals (Medium Confidence Weight)
        3. Domain Term & Clause Distribution (Base Confidence Weight)
        """
        headings = headings or []
        clauses = clauses or []

        # Preamble text (first ~2500 chars where titles, recitals, and parties reside)
        preamble = full_text[:2500].lower() if full_text else ""
        title_lower = (title or "").lower()
        heading_text = " ".join(headings).lower()
        full_text_lower = full_text.lower() if full_text else ""

        scores: Dict[str, float] = {k: 0.0 for k in PROFILES.keys()}
        matched_signals: Dict[str, List[str]] = {k: [] for k in PROFILES.keys()}

        # 1. Title matching (strongest signal: 50 points)
        for ctype, profile in PROFILES.items():
            for pat in profile["title_patterns"]:
                if re.search(pat, title_lower):
                    scores[ctype] += 50.0
                    matched_signals[ctype].append(f"Title regex match '{pat}' in '{title}'")
                    break
                elif re.search(pat, preamble[:800]):
                    scores[ctype] += 40.0
                    matched_signals[ctype].append(f"Header regex match in preamble")
                    break

        # 2. Heading inspection (15 points per match)
        for ctype, profile in PROFILES.items():
            for pat in profile["title_patterns"]:
                if heading_text and re.search(pat, heading_text):
                    scores[ctype] += 15.0
                    matched_signals[ctype].append(f"Heading match")
                    break

        # 3. Party role analysis (15 points)
        for ctype, profile in PROFILES.items():
            party_matches = [pt for pt in profile["party_terms"] if re.search(rf"\b{re.escape(pt)}\b", preamble)]
            if len(party_matches) >= 2:
                scores[ctype] += 20.0
                matched_signals[ctype].append(f"Defined parties: {', '.join(party_matches[:3])}")
            elif len(party_matches) == 1:
                scores[ctype] += 10.0
                matched_signals[ctype].append(f"Defined party: {party_matches[0]}")

        # 4. Content keyword density (2 points each, capped at 25 points)
        for ctype, profile in PROFILES.items():
            kw_hits = [kw for kw in profile["content_keywords"] if kw in full_text_lower]
            kw_points = min(25.0, len(kw_hits) * 2.5)
            scores[ctype] += kw_points
            if kw_hits:
                matched_signals[ctype].append(f"Keywords: {', '.join(kw_hits[:4])}")

        # 5. Clause types presence
        for ctype, profile in PROFILES.items():
            for cl in clauses:
                cl_type = (cl.get("clause_type") or "").lower()
                cl_title = (cl.get("title") or "").lower()
                for target_t in profile["priority_clause_types"]:
                    if target_t in cl_type or target_t in cl_title:
                        scores[ctype] += 4.0

        # Determine winner
        best_type, best_score = max(scores.items(), key=lambda x: x[1])

        # Confidence calculation
        total_score = sum(scores.values()) or 1.0
        confidence = round(min(0.99, max(0.40, best_score / (best_score + 30.0))), 2)

        # Fallback if no strong signals detected
        if best_score < 15.0:
            predicted_type = "Vendor/Supplier Agreement" if "supplier" in title_lower or "vendor" in title_lower else "Service Agreement"
            confidence = 0.50
        else:
            predicted_type = best_type

        return {
            "predicted_type": predicted_type,
            "confidence": confidence,
            "score": round(best_score, 1),
            "signals": matched_signals.get(predicted_type, []),
            "all_scores": {k: round(v, 1) for k, v in scores.items()}
        }

    @classmethod
    def prioritize_clauses(
        cls,
        clauses: List[Dict[str, Any]],
        contract_type: str,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Prioritizes clauses and document sections based on confirmed contract type,
        with general keyword search as fallback. Zero hardcoded page numbers.
        """
        if not clauses:
            return []

        profile = PROFILES.get(contract_type, {})
        priority_topics = profile.get("priority_clause_types", [])
        q_lower = (query or "").strip().lower()

        def score_clause(c: Dict[str, Any]) -> Tuple[float, int]:
            title = (c.get("title") or "").lower()
            ctype = (c.get("clause_type") or "").lower()
            text = (c.get("clause_text") or c.get("original_text") or "").lower()
            page = c.get("page_number", 999)

            score = 0.0

            # 1. Query match (highest priority if user explicitly searched)
            if q_lower:
                if q_lower in title:
                    score += 50.0
                if q_lower in text:
                    score += 30.0

            # 2. Priority topic match based on confirmed contract type
            for topic in priority_topics:
                if topic in ctype or topic in title:
                    score += 20.0
                elif topic in text:
                    score += 10.0

            # 3. Operational clauses generally score higher than boilerplate
            if ctype not in ("general_clause", "boilerplate"):
                score += 5.0

            # Return negative page to preserve natural document ordering for ties
            return (score, -page)

        # Sort descending by priority score, then by document order
        sorted_clauses = sorted(clauses, key=score_clause, reverse=True)
        return sorted_clauses
