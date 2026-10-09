"""
Infinity AI - Data Analysis & Academic Study Mode Engine
Provides:
1. Deterministic Tabular Data Analysis (CSV, XLSX, JSON):
   - Schema detection, data types, missing value detection
   - Numerical statistics (min, max, mean, count)
   - Category frequency distributions
   - Tabular markdown summaries & charts
2. Academic Study Assistant:
   - Topic simplification & first-principles explanation
   - Multiple Choice Questions (MCQs) generator with explanations
   - Flashcards generator for active recall
   - Engineering exam questions & SPPU viva preparation
   - Structured study schedules
"""

import csv
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def analyze_tabular_file(file_path: str) -> Dict[str, Any]:
    """Analyzes a CSV, TSV, or JSON dataset locally and computes summary statistics."""
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    ext = p.suffix.lower()
    rows = []
    headers = []

    try:
        if ext in [".csv", ".tsv"]:
            delim = "\t" if ext == ".tsv" else ","
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=delim)
                for r in reader:
                    if r and any(cell.strip() for cell in r):
                        rows.append([c.strip() for c in r])
            if not rows:
                return {"status": "error", "message": "Dataset is empty."}
            headers = rows[0]
            data_rows = rows[1:]

        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                data_rows = [[str(item.get(k, "")) for k in headers] for item in data]
            elif isinstance(data, dict):
                return {
                    "status": "success",
                    "format": "JSON Object",
                    "keys": list(data.keys()),
                    "key_count": len(data),
                    "summary_markdown": f"### JSON Object Summary\n- Total Top-Level Keys: {len(data)}\n- Keys: `{', '.join(data.keys())}`"
                }
            else:
                return {"status": "error", "message": "Unsupported JSON structure."}
        else:
            return {"status": "error", "message": f"Unsupported tabular format: {ext}"}

        total_rows = len(data_rows)
        num_cols = len(headers)

        # Compute column statistics
        col_stats = []
        for col_idx, col_name in enumerate(headers):
            values = [row[col_idx] for row in data_rows if col_idx < len(row)]
            non_empty = [v for v in values if v != ""]
            missing_count = len(values) - len(non_empty)

            # Try parsing as numbers
            num_vals = []
            for v in non_empty:
                try:
                    num_vals.append(float(v))
                except ValueError:
                    pass

            is_numeric = len(num_vals) > (len(non_empty) * 0.7) and len(num_vals) > 0

            stat = {
                "name": col_name,
                "missing": missing_count,
                "type": "Numeric" if is_numeric else "Categorical",
            }

            if is_numeric and num_vals:
                stat["min"] = round(min(num_vals), 2)
                stat["max"] = round(max(num_vals), 2)
                stat["mean"] = round(sum(num_vals) / len(num_vals), 2)
            else:
                # Top frequent items
                freq = {}
                for v in non_empty:
                    freq[v] = freq.get(v, 0) + 1
                top_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
                stat["top_values"] = top_items

            col_stats.append(stat)

        # Build clean markdown summary
        md_lines = [
            f"### 📊 Dataset Analysis: `{p.name}`",
            f"- **Total Rows:** {total_rows:,}",
            f"- **Total Columns:** {num_cols}",
            f"- **Missing Value Summary:** {sum(s['missing'] for s in col_stats):,} total missing cells",
            "",
            "| Column | Type | Missing | Details / Range |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for s in col_stats:
            if s["type"] == "Numeric":
                det = f"Min: {s.get('min')}, Mean: {s.get('mean')}, Max: {s.get('max')}"
            else:
                top_str = ", ".join(f"'{k}' ({c})" for k, c in s.get("top_values", []))
                det = f"Top: {top_str}" if top_str else "N/A"
            md_lines.append(f"| `{s['name']}` | {s['type']} | {s['missing']} | {det} |")

        # Preview table (first 5 rows)
        md_lines.append("\n#### Sample Data Preview (First 5 Rows):")
        md_lines.append("| " + " | ".join(headers[:8]) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(headers[:8])) + " |")
        for r in data_rows[:5]:
            md_lines.append("| " + " | ".join(r[:8]) + " |")

        return {
            "status": "success",
            "file_name": p.name,
            "total_rows": total_rows,
            "num_cols": num_cols,
            "column_stats": col_stats,
            "summary_markdown": "\n".join(md_lines),
        }

    except Exception as exc:
        return {"status": "error", "message": f"Analysis failed: {exc}"}


# ============================================================
# STUDY MODE HELPERS & PROMPT BUILDERS (Section 13)
# ============================================================

def build_study_prompt(topic: str, mode: str = "explain", doc_context: str = "") -> Tuple[str, str]:
    """Generates structured pedagogical prompts for the Study Agent."""
    system = (
        "You are Infinity AI's Distinguished Academic Professor and Engineering Tutor.\n"
        "Your pedagogical approach is grounded in first principles, active recall, and rigorous academic excellence.\n"
        "Maintain clean Markdown formatting, intuitive analogies, and complete solutions."
    )

    context_block = f"\nREFERENCE CURRICULUM / DOCUMENT CONTEXT:\n{doc_context}\n" if doc_context else ""

    if mode == "explain":
        user = (
            f"Explain the following engineering concept from first principles:\n"
            f"TOPIC: {topic}\n{context_block}\n"
            f"Provide:\n"
            f"1. Core Intuition & Real-World Analogy\n"
            f"2. Formal Mathematical / Architectural Definition\n"
            f"3. Step-by-Step Working Mechanism\n"
            f"4. Concrete Example / Problem Walkthrough\n"
            f"5. Common Pitfalls & Exam Traps"
        )
    elif mode == "quiz":
        user = (
            f"Generate an academic examination quiz on:\n"
            f"TOPIC: {topic}\n{context_block}\n"
            f"Provide:\n"
            f"- 5 Rigorous Multiple Choice Questions (MCQs) with options A, B, C, D\n"
            f"- For each question, explain WHY the correct option is right and WHY the distractors are wrong\n"
            f"- 2 Descriptive University-level questions with model high-scoring answers"
        )
    elif mode == "flashcards":
        user = (
            f"Create a high-yield flashcard deck for active recall on:\n"
            f"TOPIC: {topic}\n{context_block}\n"
            f"Format each card exactly as:\n"
            f"**Card [N]: [Concept Name]**\n"
            f"- **Q:** [Precise Question]\n"
            f"- **A:** [Concise, high-impact answer]\n"
            f"- **Key Takeaway:** [One-sentence memory anchor]\n\n"
            f"Generate 8-10 cards."
        )
    elif mode == "viva":
        user = (
            f"Prepare a University / SPPU Viva Voce preparation guide for:\n"
            f"TOPIC: {topic}\n{context_block}\n"
            f"Provide:\n"
            f"1. 5 Most Likely Questions External Examiners will ask\n"
            f"2. High-scoring, confident verbal responses\n"
            f"3. Counter-questions examiners ask when probing deeper"
        )
    else:
        user = f"Provide a comprehensive academic breakdown for:\nTOPIC: {topic}\n{context_block}"

    return system, user
