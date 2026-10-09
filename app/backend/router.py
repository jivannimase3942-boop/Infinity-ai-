"""
Infinity AI - Intelligent Model Router
Automatically routes requests based on task type, complexity, and modality.
Supports manual override (Auto, Fast, Balanced, Advanced, Vision, Coding, Custom)
and provides clear explanations and graceful fallbacks when a specialized model is missing.
"""

import re
from typing import Dict, Any, Tuple
from backend.model_manager import get_all_models
from backend.datetime_engine import is_datetime_query
from backend.capability_engine import check_unsupported_capability

CODE_PATTERNS = [
    r"\bdef\s+\w+\(", r"\bclass\s+\w+", r"\bfunction\b", r"\bconst\b", r"\blet\b",
    r"\bimport\s+\w+", r"\bfrom\s+\w+\s+import", r"```(python|javascript|typescript|c|cpp|rust|go|html|css|bash|powershell|sql)",
    r"\bwrite a (script|program|function|class|query|component|api)\b",
    r"\bdebug\b", r"\bfix this error\b", r"\bsyntax error\b", r"\brefactor\b", r"\bsql query\b"
]

DATA_PATTERNS = [
    r"\b(csv|xlsx|excel|dataframe|dataset|columns|rows|missing values|mean|median|std dev|correlation|trend|table)\b",
    r"\banalyze (this|the) (data|table|csv|dataset)\b"
]

STUDY_PATTERNS = [
    r"\b(quiz|mcqs?|flashcards?|viva|exam questions?|syllabus|study plan|revision|explain like i am 5|eli5)\b",
    r"\b(solve step by step|practice questions?|university exam)\b"
]

RESEARCH_PATTERNS = [
    r"\b(research paper|research review|conduct research|investigate topic|literature review|empirical evidence|citations?|peer review|findings)\b",
    r"\bresearch\b"
]

REASONING_PATTERNS = [
    r"\b(prove that|derive the formula|architectural trade-offs|identify contradictions|logical deduction|counterexample)\b",
    r"\bcompare and contrast\b"
]

SUMMARIZATION_PATTERNS = [
    r"\b(summarize|summary|tl;?dr|executive summary|key takeaways|synopsis|brief overview)\b"
]

TRANSLATION_PATTERNS = [
    r"\b(translate|in spanish|in french|in german|in hindi|in japanese|in chinese|translation)\b"
]

WRITING_PATTERNS = [
    r"\b(write an essay|draft a letter|cover letter|report|blog post|whitepaper|documentation|memo)\b"
]

VISION_PATTERNS = [
    r"\b(image|picture|diagram|photo|screenshot|graphic|illustration)\b"
]

SIMPLE_CHAT_PATTERNS = [
    r"^(hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you|ok|okay)[\.!\?]?$",
    r"^(what is your name|who are you|help|what can you do)[\.!\?]?$"
]


DOC_QA_PATTERNS = [
    r"\b(this (pdf|document|paper|file)|in this (document|pdf|file)|according to (the|this) (document|pdf|text))\b",
    r"\b(what does page \d+|summarize (chapter|section|page) \d+|on page \d+)\b",
    r"\b(what is this (pdf|document) about|what does this document say)\b"
]


def detect_query_intent(prompt: str, has_image: bool = False, is_doc_qa: bool = False) -> str:
    """
    Classifies user query into one of 13 intents:
    Date/Time, Unsupported, Vision, Coding, Data Analysis, Study, Research, Reasoning,
    Summarization, Translation, Writing, Document QA, or General.
    """
    if has_image:
        return "Vision"

    clean_p = prompt.strip().lower()

    # Check for unsupported capabilities (e.g. image generation)
    is_unsupported, _, _ = check_unsupported_capability(prompt, has_image_attachment=has_image)
    if is_unsupported:
        return "Unsupported"

    # Check for date / time questions
    if is_datetime_query(prompt):
        return "Date/Time"

    for pat in VISION_PATTERNS:
        if re.search(pat, clean_p):
            return "Vision"

    if is_doc_qa:
        return "Document QA"

    for pat in DOC_QA_PATTERNS:
        if re.search(pat, clean_p):
            return "Document QA"

    for pat in SIMPLE_CHAT_PATTERNS:
        if re.match(pat, clean_p):
            return "General"

    for pat in CODE_PATTERNS:
        if re.search(pat, prompt, re.IGNORECASE):
            return "Coding"

    for pat in DATA_PATTERNS:
        if re.search(pat, clean_p):
            return "Data Analysis"

    for pat in STUDY_PATTERNS:
        if re.search(pat, clean_p):
            return "Study"

    for pat in RESEARCH_PATTERNS:
        if re.search(pat, clean_p):
            return "Research"

    for pat in REASONING_PATTERNS:
        if re.search(pat, clean_p):
            return "Reasoning"

    for pat in SUMMARIZATION_PATTERNS:
        if re.search(pat, clean_p):
            return "Summarization"

    for pat in TRANSLATION_PATTERNS:
        if re.search(pat, clean_p):
            return "Translation"

    for pat in WRITING_PATTERNS:
        if re.search(pat, clean_p):
            return "Writing"

    if len(prompt) > 800:
        return "Document QA"

    return "General"


def route_model(prompt: str, override_mode: str = "Auto", has_image: bool = False, is_doc_qa: bool = False) -> Tuple[str, str, str]:
    """
    Selects the best model for the task.
    Returns: (selected_model_name, category_name, explanation)
    """
    info = route_model_detailed(prompt, override_mode=override_mode, has_image=has_image, is_doc_qa=is_doc_qa)
    return info["model_used"], info["category"], info["explanation"]


def _safe_first(available_list: list, default: str = "qwen2.5:1.5b") -> str:
    return available_list[0] if (available_list and len(available_list) > 0) else default


def route_model_detailed(
    prompt: str,
    override_mode: str = "Auto",
    has_image: bool = False,
    is_doc_qa: bool = False,
    project_preferred: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detailed model routing returning exact model used, intent, reason, and fallback status.
    Ensures safe fallbacks without IndexErrors even when model catalogues are partial.
    """
    catalogue = get_all_models()
    presets = catalogue.get("presets", {})
    available_ollama = [m["name"] for m in catalogue.get("ollama_models", [])]
    safe_default = _safe_first(available_ollama, "qwen2.5:1.5b")

    if project_preferred and override_mode == "Auto" and project_preferred != "Balanced":
        override_mode = project_preferred

    # Manual override handling
    if override_mode != "Auto":
        target = presets.get(override_mode) or override_mode
        fallback = None
        if available_ollama and target not in available_ollama:
            fallback = safe_default
            model_used = fallback
        else:
            model_used = target or safe_default

        reason = f"Manual override mode: {override_mode}"
        return {
            "model_used": model_used,
            "intent": override_mode,
            "category": override_mode,
            "reason": reason,
            "fallback": fallback or "None",
            "explanation": f"Model used: {model_used} | Reason: {reason} | Fallback: {fallback or 'None'}"
        }

    # Auto Intent Detection
    intent = detect_query_intent(prompt, has_image=has_image, is_doc_qa=is_doc_qa)
    fallback = None

    if intent == "Date/Time":
        model_used = "Local Clock (Asia/Kolkata)"
        reason = "System clock and timezone-aware datetime query detected; answered deterministically."
        category = "Date/Time"

    elif intent == "Unsupported":
        model_used = "Capability Guard"
        reason = "Unsupported capability requested (e.g. image generation); explainable fallback provided."
        category = "Unsupported"

    elif intent == "Vision":
        target = presets.get("Vision")
        if target and (not available_ollama or target in available_ollama):
            model_used = target
            reason = "Multimodal visual query detected; routed to vision model."
        else:
            model_used = presets.get("Balanced") or presets.get("Fast") or safe_default
            fallback = model_used
            reason = "Vision model unavailable; routed to Balanced model with OCR fallback."
        category = "Vision"

    elif intent == "Coding":
        target = presets.get("Coding")
        if target and (not available_ollama or target in available_ollama):
            model_used = target
            reason = "Code or software engineering pattern detected."
        else:
            model_used = presets.get("Balanced") or presets.get("Fast") or safe_default
            fallback = model_used
            reason = "Preferred coding model unavailable; routed to Balanced model."
        category = "Coding"

    elif intent in ["Reasoning", "Research"]:
        target = presets.get("Advanced") or presets.get("Balanced")
        if target and (not available_ollama or target in available_ollama):
            model_used = target
            reason = f"Complex academic or {intent.lower()} task detected; routed to Advanced model."
        else:
            model_used = presets.get("Fast") or safe_default
            fallback = model_used
            reason = "Advanced model unavailable; routed to Fast model."
        category = "Advanced" if intent == "Reasoning" else "Research"

    elif intent == "Document QA":
        model_used = presets.get("Balanced") or presets.get("Fast") or safe_default
        reason = "Document intelligence / RAG context pipeline."
        category = "Document QA"

    elif intent in ["Data Analysis", "Study", "Writing", "Translation", "Summarization"]:
        target = presets.get("Balanced")
        if target and (not available_ollama or target in available_ollama):
            model_used = target
            reason = f"Specialized {intent.lower()} task routed to Balanced model."
        else:
            model_used = presets.get("Fast") or safe_default
            fallback = model_used
            reason = f"Balanced model unavailable; routed {intent.lower()} task to Fast model."
        category = intent

    else:  # General / Short query
        model_used = presets.get("Fast") or presets.get("Balanced") or safe_default
        reason = "Standard conversational interaction routed to Fast model."
        category = "Fast"

    explanation = f"Model used: {model_used} | Reason: {reason} | Fallback: {fallback or 'None'}"

    return {
        "model_used": model_used,
        "intent": intent,
        "category": category,
        "reason": reason,
        "fallback": fallback or "None",
        "explanation": explanation
    }


def get_fallback_model_cascade(requested_model: str = "") -> list:
    """Returns an ordered cascade of fallback models."""
    cascade = [requested_model] if requested_model else []
    for m in ["qwen2.5:1.5b", "gemma3:4b", "dolphin-mistral:latest"]:
        if m not in cascade:
            cascade.append(m)
    return cascade

