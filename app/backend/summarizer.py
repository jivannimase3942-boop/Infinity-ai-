from typing import Optional, Callable, List
from backend.ai_engine import STOP_EVENT, NUM_PREDICT_SUMMARY, NUM_CONTEXT, generate_simple_response
from backend.diagnostics import log_ai_operation


def stop_summary():
    STOP_EVENT.set()


def reset_summary_stop():
    STOP_EVENT.clear()


def _split_text(text: str, size: int = 4000, overlap: int = 200) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind("\n\n", start, end)
            if boundary > start + int(size * 0.6):
                end = boundary
            else:
                boundary2 = text.rfind(". ", start, end)
                if boundary2 > start + int(size * 0.6):
                    end = boundary2 + 1
        sub = text[start:end].strip()
        if sub:
            chunks.append(sub)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [c for c in chunks if c]


def _format_summary_prompt(content: str, is_section: bool = False) -> str:
    if is_section:
        return (
            "Summarize this document section concisely. Focus on key ideas, facts, numbers, and headings. "
            "Do not invent facts.\n\n"
            f"SECTION CONTENT:\n{content}"
        )
    return (
        "Create a comprehensive, well-structured executive summary of the supplied document.\n"
        "You MUST include the following 6 sections formatted clearly in Markdown:\n\n"
        "# Executive Summary\n"
        "A clear, high-level overview of the document's main thesis, purpose, and content.\n\n"
        "## Key Points\n"
        "- Bullet points of the primary arguments, objectives, or takeaways\n\n"
        "## Important Concepts\n"
        "- Core definitions, principles, topics, or frameworks introduced\n\n"
        "## Important Facts\n"
        "- Notable facts, numbers, dates, findings, or questions covered\n\n"
        "## Document Structure\n"
        "- Breakdown of the document's progression and sections\n\n"
        "## Source References\n"
        "- Page or section citations where primary evidence was found\n\n"
        "Ground your answer strictly in the text below. Do not hallucinate.\n\n"
        f"DOCUMENT CONTENT:\n{content}"
    )


def summarize_document(
    full_text: str,
    chunk_callback: Optional[Callable[[str], None]] = None,
    model_name: Optional[str] = None
) -> str:
    """
    Summarizes document content using single-pass or hierarchical tree reduction.
    Never overfills the local model's context window.
    """
    if not (full_text or "").strip():
        msg = "I could not generate a summary because the document appears to have no extractable text."
        if chunk_callback:
            chunk_callback(msg)
        return msg

    reset_summary_stop()
    chunks = _split_text(full_text, size=4200, overlap=250)
    if not chunks:
        return "Document contains no readable text."

    # Single-pass for small / concise documents (1-2 chunks)
    if len(chunks) == 1:
        prompt = _format_summary_prompt(chunks[0], is_section=False)
        return generate_simple_response(
            prompt,
            num_ctx=NUM_CONTEXT,
            num_predict=NUM_PREDICT_SUMMARY,
            chunk_callback=chunk_callback,
            model_name=model_name
        )

    # Hierarchical summarization for multi-page documents
    # Step 1: Summarize each section
    section_summaries = []
    for idx, chunk in enumerate(chunks, 1):
        if STOP_EVENT.is_set():
            return "\n\n".join(section_summaries)
        sec_prompt = _format_summary_prompt(chunk, is_section=True)
        sec_out = generate_simple_response(
            sec_prompt,
            num_ctx=NUM_CONTEXT,
            num_predict=350,
            model_name=model_name
        )
        if sec_out and sec_out.strip():
            section_summaries.append(f"[Part {idx}]\n{sec_out.strip()}")

    if STOP_EVENT.is_set():
        return "\n\n".join(section_summaries)

    # Step 2: If combined section summaries exceed context length, hierarchically condense
    combined = "\n\n".join(section_summaries)
    if len(combined) > 6000:
        condensed = []
        # Group into batches of 3
        for i in range(0, len(section_summaries), 3):
            if STOP_EVENT.is_set():
                break
            batch_text = "\n\n".join(section_summaries[i:i + 3])
            c_prompt = _format_summary_prompt(batch_text, is_section=True)
            c_out = generate_simple_response(
                c_prompt,
                num_ctx=NUM_CONTEXT,
                num_predict=400,
                model_name=model_name
            )
            if c_out and c_out.strip():
                condensed.append(c_out.strip())
        combined = "\n\n".join(condensed) if condensed else combined

    if STOP_EVENT.is_set():
        return combined

    # Step 3: Produce final structured synthesis
    final_prompt = _format_summary_prompt(combined, is_section=False)
    final_summary = generate_simple_response(
        final_prompt,
        num_ctx=NUM_CONTEXT,
        num_predict=NUM_PREDICT_SUMMARY,
        chunk_callback=chunk_callback,
        model_name=model_name
    )

    log_ai_operation(
        operation="pdf_summary",
        model=model_name or "Auto",
        success=bool(final_summary),
        retrieval_count=len(chunks)
    )
    return final_summary


summarize_hierarchical = summarize_document

