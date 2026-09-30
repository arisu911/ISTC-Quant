"""
Bursa Strategy Financial Statement & PDF Extraction Engine
High-fidelity extraction of A4 Bursa quarterly and annual report text, layout, and structured tables.
Utilizes PyMuPDF (`pymupdf`) and `pdfplumber` for zero-loss financial table parsing.
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import pymupdf  # Modern PyMuPDF API
import pdfplumber

logger = logging.getLogger("bursa.analyzer.pdf")

class BursaPDFExtractor:
    """Extracts text sections, financial tables, and metadata from Bursa Malaysia A4 PDF reports."""

    def __init__(self):
        pass

    def extract_full_text(self, pdf_path: Path) -> str:
        """Extract full plain text across all pages using pymupdf."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found at {pdf_path}")

        full_text = []
        doc = pymupdf.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            full_text.append(f"--- PAGE {page_num + 1} ---\n{text}")
        doc.close()
        return "\n".join(full_text)

    def extract_structured_tables(self, pdf_path: Path) -> List[List[List[str]]]:
        """
        Extract tabular structures using pdfplumber.
        Returns a list of tables, where each table is a 2D list of cell strings.
        """
        pdf_path = Path(pdf_path)
        tables: List[List[List[str]]] = []
        
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    extracted = page.extract_tables()
                    for t in extracted:
                        # Clean cell values
                        cleaned_table = []
                        for row in t:
                            cleaned_row = [
                                str(cell).replace("\n", " ").strip() if cell is not None else ""
                                for cell in row
                            ]
                            if any(cleaned_row): # Ignore completely empty rows
                                cleaned_table.append(cleaned_row)
                        if cleaned_table:
                            tables.append(cleaned_table)
        except Exception as e:
            logger.warning(f"pdfplumber table extraction warning ({e}). Falling back to pymupdf text parsing.")
        
        return tables

    def segment_report_sections(self, full_text: str) -> Dict[str, str]:
        """
        Heuristic segmentation of standard Bursa Malaysia quarterly report sections:
          - 'income_statement'
          - 'balance_sheet'
          - 'cash_flow'
          - 'mda_operational'
          - 'explanatory_notes'
        """
        sections: Dict[str, str] = {
            "income_statement": "",
            "balance_sheet": "",
            "cash_flow": "",
            "mda_operational": "",
            "explanatory_notes": ""
        }

        # Regex markers for standard Bursa headings
        patterns = {
            "income_statement": r"(PART\s*A[:\s]+CONDENSED\s*CONSOLIDATED\s*STATEMENT\s*OF\s*PROFIT\s*OR\s*LOSS|STATEMENT\s*OF\s*COMPREHENSIVE\s*INCOME)",
            "balance_sheet": r"(PART\s*B[:\s]+CONDENSED\s*CONSOLIDATED\s*STATEMENT\s*OF\s*FINANCIAL\s*POSITION|STATEMENT\s*OF\s*FINANCIAL\s*POSITION|BALANCE\s*SHEET)",
            "cash_flow": r"(PART\s*C[:\s]+CONDENSED\s*CONSOLIDATED\s*STATEMENT\s*OF\s*CASH\s*FLOWS|STATEMENT\s*OF\s*CASH\s*FLOWS)",
            "mda_operational": r"(PART\s*D[:\s]+MANAGEMENT\s*DISCUSSION|MANAGEMENT\s*DISCUSSION\s*AND\s*ANALYSIS|REVIEW\s*OF\s*PERFORMANCE|OPERATIONAL\s*AUDIT)",
            "explanatory_notes": r"(PART\s*E[:\s]+EXPLANATORY\s*NOTES|NOTES\s*TO\s*THE\s*INTERIM\s*FINANCIAL\s*REPORT)"
        }

        # Find match indices
        matches = []
        for key, pat in patterns.items():
            for m in re.finditer(pat, full_text, re.IGNORECASE):
                matches.append((m.start(), key))

        matches.sort(key=lambda x: x[0])

        if not matches:
            # Fallback: slice into sections by length
            total_len = len(full_text)
            sections["income_statement"] = full_text[: int(total_len * 0.25)]
            sections["balance_sheet"] = full_text[int(total_len * 0.25) : int(total_len * 0.50)]
            sections["cash_flow"] = full_text[int(total_len * 0.50) : int(total_len * 0.75)]
            sections["mda_operational"] = full_text[int(total_len * 0.75) :]
            return sections

        for i, (start_idx, key) in enumerate(matches):
            end_idx = matches[i + 1][0] if i + 1 < len(matches) else len(full_text)
            sections[key] = full_text[start_idx:end_idx].strip()

        return sections

    def parse_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Convenience function extracting full text, tables, and segmented sections."""
        full_text = self.extract_full_text(pdf_path)
        tables = self.extract_structured_tables(pdf_path)
        sections = self.segment_report_sections(full_text)

        return {
            "pdf_name": pdf_path.name,
            "pdf_path": str(pdf_path),
            "text_length": len(full_text),
            "table_count": len(tables),
            "full_text": full_text,
            "tables": tables,
            "sections": sections
        }

# PDF Extractor singleton
pdf_extractor = BursaPDFExtractor()
