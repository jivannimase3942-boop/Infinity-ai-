import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import pymupdf

try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None


def _clean_pdf_text(text: str) -> str:
    """
    Cleans extracted PDF text:
    - Removes non-printable / null control characters
    - Fixes broken hyphenations across line breaks (e.g., 'arti-\nficial' -> 'artificial')
    - Collapses excessive line breaks (3+ into 2)
    - Normalizes excessive whitespace while preserving paragraph structure
    """
    if not text:
        return ""
    # Strip nulls and control characters except newline and tab
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    # Fix hyphenated words across lines
    t = re.sub(r"(\b[a-zA-Z]{2,})-\n([a-zA-Z]{2,}\b)", r"\1\2", t)
    # Clean whitespace per line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in t.splitlines()]
    # Rejoin and collapse 3+ newlines
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _detect_heading(page_text: str) -> str:
    """Detect potential top heading or title on a page."""
    for line in page_text.splitlines()[:5]:
        line = line.strip()
        if not line:
            continue
        if len(line) < 80 and (
            re.match(r"^(chapter|section|part|unit|module)\s+\d+", line, re.IGNORECASE)
            or line.isupper()
            or line.endswith(":")
            or re.match(r"^\d+(\.\d+)*\s+[A-Z]", line)
        ):
            return line
    return ""


def _ocr_page(page, dpi=130) -> str:
    if pytesseract is None or Image is None:
        return ""
    try:
        from backend.ocr_vision import is_ocr_available
        if not is_ocr_available():
            return ""
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        raw_ocr = pytesseract.image_to_string(image)
        return _clean_pdf_text(raw_ocr)
    except Exception:
        return ""


def _tables_to_markdown(page) -> str:
    """Extract tables using PyMuPDF and format as clean Markdown tables."""
    try:
        finder = page.find_tables()
        tables = getattr(finder, "tables", []) or []
        if not tables:
            return ""
        table_parts = []
        for t_idx, table in enumerate(tables, start=1):
            rows = table.extract() or []
            if not rows:
                continue
            cleaned_rows = []
            for row in rows:
                cleaned_rows.append([re.sub(r"\s+", " ", str(cell or "").strip()) for cell in row])
            if not cleaned_rows:
                continue
            headers = cleaned_rows[0]
            header_line = "| " + " | ".join(headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            body_lines = ["| " + " | ".join(r) + " |" for r in cleaned_rows[1:]]
            table_md = "\n".join([header_line, sep_line] + body_lines)
            table_parts.append(f"\n[Table {t_idx}]\n{table_md}\n")
        return "\n".join(table_parts).strip()
    except Exception:
        return ""


def extract_text_from_pdf(
    pdf_path: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    use_ocr: bool = True
) -> List[Dict[str, Any]]:
    """
    Extracts text, tables, and page metadata from a PDF file.
    Handles:
    - Normal text PDFs
    - Multi-page PDFs
    - PDFs with tables
    - Scanned pages with OCR fallback
    - Empty or corrupted PDFs
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if path.stat().st_size == 0:
        return [{"page": 1, "text": "[Empty Document: File size is 0 bytes]", "ocr": False, "section": "Empty"}]

    pages = []
    try:
        with pymupdf.open(str(path)) as doc:
            total = len(doc)
            if total == 0:
                return [{"page": 1, "text": "[Empty PDF: Document contains 0 pages]", "ocr": False, "section": "Empty"}]

            for index, page in enumerate(doc):
                page_num = index + 1
                if progress_callback:
                    progress_callback(page_num, total, "Extracting text")

                raw_text = page.get_text("text", sort=True)
                text = _clean_pdf_text(raw_text)
                
                # Check for tables
                table_md = _tables_to_markdown(page)
                if table_md and table_md not in text:
                    text = f"{text}\n\n{table_md}".strip() if text else table_md

                # OCR fallback for scanned pages with minimal text
                ocr_used = False
                if use_ocr and len(text) < 40:
                    ocr_res = _ocr_page(page)
                    if len(ocr_res) > len(text):
                        text = ocr_res
                        ocr_used = True

                if not text:
                    text = f"[No extractable text on page {page_num}]"

                section = _detect_heading(text) or f"Page {page_num}"

                pages.append({
                    "page": page_num,
                    "text": text,
                    "ocr": ocr_used,
                    "section": section,
                })

    except pymupdf.FileDataError as exc:
        raise ValueError(f"Corrupted or invalid PDF file: {exc}")
    except Exception as exc:
        if pages:
            # Return whatever was successfully extracted
            return pages
        raise RuntimeError(f"Error processing PDF: {exc}")

    return pages


def extract_full_text(pages: Union[List[Dict[str, Any]], str]) -> str:
    """Assembles all pages into formatted text with page headers, or extracts from a PDF path."""
    if isinstance(pages, (str, Path)):
        if Path(pages).is_file():
            pages = extract_text_and_tables(str(pages))
        else:
            return str(pages)
    if not pages:
        return ""
    if isinstance(pages, list) and pages and isinstance(pages[0], str):
        return "\n\n".join(pages)
    return "\n\n".join(f"--- Page {p.get('page', 1)} ({p.get('section', 'General')}) ---\n{p.get('text', '')}" for p in pages if isinstance(p, dict))


def get_pdf_page_count(pdf_path: str) -> int:
    """Returns number of pages safely."""
    try:
        path = Path(pdf_path)
        if not path.exists() or path.stat().st_size == 0:
            return 0
        with pymupdf.open(str(path)) as doc:
            return len(doc)
    except Exception:
        return 0


def validate_document_file(file_path: str) -> tuple:
    """Validates if file exists, is non-empty, and readable."""
    try:
        p = Path(file_path)
        if not p.exists():
            return False, "File does not exist"
        if p.stat().st_size == 0:
            return False, "File is empty (0 bytes)"
        return True, "Valid"
    except Exception as exc:
        return False, str(exc)


# Aliases for compatibility
extract_text_and_tables = extract_text_from_pdf

