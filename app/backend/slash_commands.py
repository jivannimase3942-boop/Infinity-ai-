"""
Infinity AI - Slash Commands & Modes Dispatcher
Supports:
/summarize, /explain, /analyze, /research, /code, /debug, /compare,
/extract, /translate, /quiz, /flashcards, /citations, /search, /remember, /forget
Seamlessly blends with natural language queries.
"""

import re
from typing import Dict, Any, Tuple, Optional
from backend.memory import memory_service
from backend.rag_engine import retrieve_context_with_citations


def process_slash_command(query: str, active_doc_id: Optional[str] = None) -> Tuple[bool, str, Optional[str], Optional[str]]:
    """
    Checks if query begins with a slash command.
    Returns: (is_slash_cmd, modified_prompt, target_agent, system_instruction_override)
    """
    q = query.strip()
    if not q.startswith("/"):
        return False, query, None, None

    parts = q.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/summarize":
        prompt = f"Provide a comprehensive, structured executive summary of the following:\n{arg}" if arg else "Provide a comprehensive summary of the currently loaded document."
        return True, prompt, "Document", None

    elif cmd == "/explain":
        prompt = f"Explain the following concept thoroughly from first principles with clear examples and intuitive analogies:\n{arg}"
        return True, prompt, "Study", None

    elif cmd == "/analyze":
        prompt = f"Perform an in-depth critical analysis of:\n{arg}"
        return True, prompt, "Data" if ("csv" in arg.lower() or "data" in arg.lower() or "number" in arg.lower()) else "General", None

    elif cmd == "/research":
        prompt = f"Conduct a rigorous research investigation into the following question and produce a structured findings report with evidence and confidence rating:\n{arg}"
        return True, prompt, "Research", None

    elif cmd == "/code":
        prompt = f"Write clean, robust, well-documented, production-grade code for the following task:\n{arg}"
        return True, prompt, "Coding", None

    elif cmd == "/debug":
        prompt = f"Analyze the following code, diagnose any bugs or performance bottlenecks, and provide a unified diff fix with verification steps:\n{arg}"
        return True, prompt, "Coding", None

    elif cmd == "/compare":
        prompt = f"Compare and contrast the key aspects, methodologies, and findings between the relevant topics or documents:\n{arg}"
        return True, prompt, "Document", None

    elif cmd == "/extract":
        prompt = f"Extract all critical data points, key entities, numbers, dates, and conclusions from:\n{arg}"
        return True, prompt, "Document", None

    elif cmd == "/quiz":
        prompt = f"Generate 5 challenging multiple-choice questions (MCQs) with 4 options each, followed by an answer key and in-depth explanations for:\n{arg}"
        return True, prompt, "Study", None

    elif cmd == "/flashcards":
        prompt = f"Create a set of high-yield study flashcards (Question / Answer pairs) for active recall on:\n{arg}"
        return True, prompt, "Study", None

    elif cmd == "/citations":
        ctx, cits = retrieve_context_with_citations(arg or "key findings", doc_id=active_doc_id, n_results=5)
        citation_summary = "\n".join([f"- Citation {c['citation_id']}: Document '{c['document']}', Page {c['page']}\n  Snippet: {c['snippet']}" for c in cits])
        prompt = f"Review the extracted document citations below and answer the query: '{arg}'\n\nCITATIONS:\n{citation_summary}"
        return True, prompt, "Document", None

    elif cmd == "/search":
        ctx, cits = retrieve_context_with_citations(arg, doc_id=active_doc_id, n_results=4)
        prompt = f"Search Query: {arg}\n\nDocument Context Found:\n{ctx}\n\nSynthesize the findings from the search results."
        return True, prompt, "Document", None

    elif cmd == "/remember":
        if ":" in arg:
            k, v = arg.split(":", 1)
        elif "=" in arg:
            k, v = arg.split("=", 1)
        else:
            k, v = "Note", arg
        memory_service.remember(k.strip(), v.strip())
        prompt = f"System Note: The following persistent memory was stored successfully:\nKey: '{k.strip()}', Value: '{v.strip()}'. Acknowledge this to the user."
        return True, prompt, "General", None

    elif cmd == "/forget":
        prompt = f"Please instruct the user that they can view and delete individual memories from the '🧠 Memory' panel in the sidebar, or confirm which key they would like forgotten."
        return True, prompt, "General", None

    # Unknown slash command, let it pass through with original query
    return False, query, None, None
