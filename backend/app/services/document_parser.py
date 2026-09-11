import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader
import docx

class DocumentService:
    @staticmethod
    def parse_document(file_path: str) -> Dict[str, Any]:
        """
        Parses PDF, DOCX, or TXT document preserving page numbers and section headers.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return DocumentService._parse_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return DocumentService._parse_docx(file_path)
        else:
            return DocumentService._parse_txt(file_path)

    @staticmethod
    def _parse_pdf(file_path: str) -> Dict[str, Any]:
        reader = PdfReader(file_path)
        pages_content = []
        full_text = ""
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_content.append({
                "page_number": i + 1,
                "text": text.strip()
            })
            full_text += f"\n--- PAGE {i + 1} ---\n" + text

        clauses = DocumentService.segment_clauses(pages_content)
        return {
            "page_count": len(reader.pages),
            "pages": pages_content,
            "clauses": clauses,
            "full_text": full_text
        }

    @staticmethod
    def _parse_docx(file_path: str) -> Dict[str, Any]:
        doc = docx.Document(file_path)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        
        # Word documents don't have hard page boundaries without rendering, so estimate/chunk paragraphs
        pages_content = []
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        chunk_size = 8
        
        for page_idx in range(0, max(1, len(paragraphs)), chunk_size):
            chunk = paragraphs[page_idx:page_idx + chunk_size]
            page_text = "\n".join(chunk)
            pages_content.append({
                "page_number": (page_idx // chunk_size) + 1,
                "text": page_text
            })

        clauses = DocumentService.segment_clauses(pages_content)
        return {
            "page_count": len(pages_content),
            "pages": pages_content,
            "clauses": clauses,
            "full_text": full_text
        }

    @staticmethod
    def _parse_txt(file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        pages_content = []
        # split by page markers or paragraph blocks
        raw_pages = content.split("--- PAGE ")
        if len(raw_pages) > 1:
            for idx, raw in enumerate(raw_pages[1:], start=1):
                lines = raw.split("\n", 1)
                p_num = idx
                text = lines[1] if len(lines) > 1 else raw
                pages_content.append({"page_number": p_num, "text": text.strip()})
        else:
            pages_content.append({"page_number": 1, "text": content.strip()})

        clauses = DocumentService.segment_clauses(pages_content)
        return {
            "page_count": len(pages_content),
            "pages": pages_content,
            "clauses": clauses,
            "full_text": content
        }

    @staticmethod
    def segment_clauses(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Regex-based section and clause detector to identify clause blocks with source metadata.
        """
        clause_list = []
        # Pattern matching section numbers like "Section 7.2", "7.2", "Clause 4.1", "4.1 Payment Terms", etc.
        section_pattern = re.compile(
            r'(?:SECTION|CLAUSE|ARTICLE)?\s*(\d+\.\d+|\d+)\s*[:\.\-]?\s*([^\n]+)', 
            re.IGNORECASE
        )

        for page in pages:
            page_num = page["page_number"]
            text = page["text"]
            lines = text.split("\n")
            
            current_section = None
            current_title = None
            current_clause_buf = []

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                match = section_pattern.match(line_str)
                if match:
                    # Save previous clause if present
                    if current_clause_buf and (current_section or current_title):
                        clause_text = " ".join(current_clause_buf)
                        clause_list.append({
                            "page_number": page_num,
                            "section_number": current_section or "1.0",
                            "title": current_title or "Clause",
                            "clause_text": clause_text,
                            "clause_type": DocumentService._infer_type(clause_text)
                        })
                        current_clause_buf = []

                    current_section = match.group(1)
                    current_title = match.group(2).strip()
                    current_clause_buf.append(line_str)
                else:
                    current_clause_buf.append(line_str)

            # Flush remaining buffer for page
            if current_clause_buf:
                clause_text = " ".join(current_clause_buf)
                clause_list.append({
                    "page_number": page_num,
                    "section_number": current_section or "1.0",
                    "title": current_title or "General Clause",
                    "clause_text": clause_text,
                    "clause_type": DocumentService._infer_type(clause_text)
                })

        return clause_list

    @staticmethod
    def _infer_type(text: str) -> str:
        text_lower = text.lower()
        if "interest" in text_lower or "late payment" in text_lower or "overdue" in text_lower:
            return "late_payment_interest"
        elif "delay" in text_lower or "penalty" in text_lower or "liquidated damages" in text_lower:
            return "delivery_delay_penalty"
        elif "discount" in text_lower or "volume" in text_lower or "rebate" in text_lower:
            return "volume_discount"
        elif "sla" in text_lower or "uptime" in text_lower or "service level" in text_lower:
            return "sla_penalty"
        elif "escalation" in text_lower or "price increase" in text_lower or "inflation" in text_lower:
            return "price_escalation"
        elif "renew" in text_lower or "extension" in text_lower:
            return "renewal_condition"
        elif "terminate" in text_lower or "cancel" in text_lower:
            return "termination_condition"
        return "general_clause"
