"""
Infinity AI - Universal File Attachments & Protected File Operations Layer
Provides:
1. Universal content extraction for 20+ file formats:
   PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, JSON, PY, JS, TS, HTML, CSS, JAVA, CPP, C, SQL, LOG, YAML, XML
2. Safe file operations with strict protection against accidental or silent deletions
3. Local export capabilities (TXT, Markdown, JSON, HTML)
100% Offline-First. Never uploads files to any cloud service.
"""

import csv
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from backend.security import is_write_authorized


SUPPORTED_EXTENSIONS = {
    ".pdf": "Portable Document Format",
    ".docx": "Microsoft Word Document",
    ".pptx": "Microsoft PowerPoint Presentation",
    ".xlsx": "Microsoft Excel Spreadsheet",
    ".csv": "Comma Separated Values",
    ".tsv": "Tab Separated Values",
    ".txt": "Plain Text Document",
    ".md": "Markdown Document",
    ".json": "JavaScript Object Notation",
    ".py": "Python Source Code",
    ".js": "JavaScript Source Code",
    ".ts": "TypeScript Source Code",
    ".html": "HyperText Markup Language",
    ".css": "Cascading Style Sheets",
    ".java": "Java Source Code",
    ".cpp": "C++ Source Code",
    ".c": "C Source Code",
    ".sql": "Structured Query Language",
    ".log": "Log File",
    ".yaml": "YAML Document",
    ".yml": "YAML Document",
    ".xml": "Extensible Markup Language",
    ".png": "Image (PNG)",
    ".jpg": "Image (JPEG)",
    ".jpeg": "Image (JPEG)",
    ".webp": "Image (WEBP)",
}


def detect_file_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(ext, f"Generic ({ext})")


def is_image_file(file_path: str) -> bool:
    ext = Path(file_path).suffix.lower()
    return ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]


def extract_file_content(file_path: str, max_chars: int = 35000) -> Dict[str, Any]:
    """
    Extracts text/tabular content from any supported file format.
    Never uploads to cloud. Returns structured dict with preview and metadata.
    """
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "error": f"File does not exist: {file_path}", "content": ""}

    ext = p.suffix.lower()
    fname = p.name
    size = p.stat().st_size
    file_type = detect_file_type(file_path)

    try:
        # 1. Images
        if is_image_file(file_path):
            from backend.ocr_vision import is_ocr_available, get_available_vision_model
            # Return image attachment metadata
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": True,
                "content": f"[Image Attachment: {fname} ({size / 1024:.1f} KB)]",
                "pages": 1,
            }

        # 2. PDF
        if ext == ".pdf":
            import pymupdf
            doc = pymupdf.open(file_path)
            pages_text = []
            for i, page in enumerate(doc):
                txt = page.get_text()
                if not txt.strip() and len(pages_text) < 5:
                    # OCR fallback for first few scanned pages
                    try:
                        import pytesseract
                        from PIL import Image
                        import io
                        pix = page.get_pixmap(dpi=130)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        txt = pytesseract.image_to_string(img)
                    except Exception:
                        pass
                pages_text.append(f"--- [Page {i + 1}] ---\n{txt.strip()}")
            doc.close()
            full = "\n\n".join(pages_text)
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": len(pages_text),
            }

        # 3. Word DOCX
        if ext == ".docx":
            paragraphs = []
            with zipfile.ZipFile(file_path) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for node in tree.iter(f"{{{ns['w']}}}p"):
                    texts = [t.text for t in node.iter(f"{{{ns['w']}}}t") if t.text]
                    if texts:
                        paragraphs.append("".join(texts))
            full = "\n\n".join(paragraphs) or "[Empty Document]"
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": max(1, len(paragraphs) // 10),
            }

        # 4. PowerPoint PPTX
        if ext == ".pptx":
            slides = []
            with zipfile.ZipFile(file_path) as z:
                slide_files = [f for f in z.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")]
                slide_files.sort(key=lambda s: int(re.search(r"slide(\d+)\.xml", s).group(1)) if re.search(r"slide(\d+)\.xml", s) else 0)
                for idx, s in enumerate(slide_files, 1):
                    tree = ET.fromstring(z.read(s))
                    texts = [n.text for n in tree.iter() if n.tag.endswith("}t") and n.text]
                    slides.append(f"--- [Slide {idx}] ---\n" + " ".join(texts).strip())
            full = "\n\n".join(slides) or "[Empty Presentation]"
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": len(slides),
            }

        # 5. Excel XLSX
        if ext == ".xlsx":
            sheet_rows = []
            with zipfile.ZipFile(file_path) as z:
                # Read shared strings if present
                shared = []
                if "xl/sharedStrings.xml" in z.namelist():
                    stree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in stree.iter():
                        if si.tag.endswith("}t") and si.text:
                            shared.append(si.text)

                sheet_files = [f for f in z.namelist() if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")]
                if sheet_files:
                    stree = ET.fromstring(z.read(sheet_files[0]))
                    for row in stree.iter():
                        if row.tag.endswith("}row"):
                            cells = []
                            for c in row.iter():
                                if c.tag.endswith("}c"):
                                    t = c.get("t")
                                    v = "".join([vn.text for vn in c.iter() if vn.tag.endswith("}v") and vn.text])
                                    if t == "s" and v.isdigit() and int(v) < len(shared):
                                        cells.append(shared[int(v)])
                                    else:
                                        cells.append(v)
                            if any(cells):
                                sheet_rows.append(" | ".join(cells))
            full = "\n".join(sheet_rows[:150]) or "[Empty Spreadsheet]"
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": max(1, len(sheet_rows) // 40),
            }

        # 6. CSV / TSV
        if ext in [".csv", ".tsv"]:
            delimiter = "\t" if ext == ".tsv" else ","
            rows = []
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for r in reader:
                    rows.append(" | ".join([cell.strip() for cell in r]))
            full = "\n".join(rows[:200]) or "[Empty Tabular Data]"
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": max(1, len(rows) // 40),
            }

        # 7. JSON
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            full = json.dumps(data, indent=2)
            return {
                "status": "success",
                "file_name": fname,
                "file_type": file_type,
                "size_bytes": size,
                "is_image": False,
                "content": full[:max_chars],
                "pages": max(1, len(full.splitlines()) // 50),
            }

        # 8. Text, Markdown, Source Code & Logs
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            full = f.read()

        return {
            "status": "success",
            "file_name": fname,
            "file_type": file_type,
            "size_bytes": size,
            "is_image": False,
            "content": full[:max_chars],
            "pages": max(1, len(full.splitlines()) // 50),
        }

    except Exception as exc:
        return {
            "status": "error",
            "file_name": fname,
            "file_type": file_type,
            "size_bytes": size,
            "error": str(exc),
            "content": f"[Error extracting {fname}: {exc}]",
        }


# ============================================================
# SAFE FILE OPERATIONS LAYER (Section 23)
# ============================================================

def safe_read_file(file_path: str, max_bytes: int = 500000) -> str:
    """Reads local file safely without memory explosion."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_bytes)


def safe_create_file(
    file_path: str,
    content: str,
    overwrite: bool = False,
    confirmation: bool = False
) -> Dict[str, Any]:
    """Creates a new file. If file exists, requires overwrite=True and confirmation=True."""
    p = Path(file_path)
    if p.exists() and not overwrite:
        return {"status": "error", "message": f"File already exists: {file_path}. Set overwrite=True with confirmation to proceed."}

    if p.exists() and overwrite:
        if not confirmation:
            return {"status": "blocked", "message": "Confirmation required: Overwriting an existing file requires explicit user approval."}
        if not is_write_authorized():
            return {"status": "denied", "message": "Write operation blocked: Overwriting protected files requires authorized Infinity AI USB key."}

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)

    return {"status": "success", "file_path": str(p), "size_bytes": len(content.encode("utf-8"))}


def safe_edit_file(
    file_path: str,
    search_target: str,
    replacement: str,
    confirmation: bool = False
) -> Dict[str, Any]:
    """Performs targeted in-place text replacement with verification."""
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    if not confirmation:
        return {"status": "blocked", "message": "Confirmation required: Modifying an existing file requires explicit user approval."}

    if not is_write_authorized():
        return {"status": "denied", "message": "Write operation blocked: Modifying protected files requires authorized Infinity AI USB key."}

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    if search_target not in text:
        return {"status": "error", "message": "Target search text not found in file."}

    new_text = text.replace(search_target, replacement, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(new_text)

    return {"status": "success", "message": "Replacement applied successfully."}


def safe_delete_file(file_path: str, confirmation: bool = False) -> Dict[str, Any]:
    """
    CRITICAL SAFETY: Absolute protection against silent or LLM-driven deletions.
    Strictly requires confirmation=True AND authorized USB key.
    """
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    if not confirmation:
        return {
            "status": "blocked",
            "message": f"CRITICAL: Deleting file '{p.name}' requires explicit user confirmation. Silent deletion is forbidden."
        }

    if not is_write_authorized():
        return {
            "status": "denied",
            "message": "CRITICAL: Deleting protected files requires authorized Infinity AI USB key."
        }

    try:
        p.unlink()
        return {"status": "success", "message": f"File '{p.name}' deleted with explicit authorization."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def safe_export_content(
    content: str,
    filename: str,
    export_dir: Optional[str] = None
) -> str:
    """Exports content to an exports directory without altering any source file."""
    base_dir = Path(export_dir) if export_dir else Path(__file__).resolve().parent.parent / "data" / "exports"
    base_dir.mkdir(parents=True, exist_ok=True)
    out_path = base_dir / filename
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(out_path)
