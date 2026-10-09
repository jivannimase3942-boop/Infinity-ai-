import os
import re
import threading
import time
from typing import Callable, Optional

import ollama

try:
    import psutil
    _physical_cores = psutil.cpu_count(logical=False)
except Exception:
    _physical_cores = None

from backend.cache import get_cached_answer, save_cached_answer
from backend.vector_store import search_documents, search_documents_per_doc
from backend.capability_engine import check_unsupported_capability
from backend.datetime_engine import is_datetime_query, handle_datetime_query, get_datetime_answer

def _detect_ollama_host():
    env_host = os.environ.get("INFINITY_OLLAMA_URL") or os.environ.get("OLLAMA_HOST")
    candidates = []
    if env_host:
        candidates.append(env_host if env_host.startswith("http") else f"http://{env_host}")
    candidates.extend(["http://127.0.0.1:11435", "http://127.0.0.1:11434"])
    for h in candidates:
        try:
            c = ollama.Client(host=h)
            c.list()
            return h
        except Exception:
            pass
    return candidates[0]

OLLAMA_HOST = _detect_ollama_host()
MODEL_PRESETS = {
    "Basic": "qwen2.5:1.5b",
    "Moderate": "dolphin-mistral:latest",
}

def _detect_default_model():
    try:
        c = ollama.Client(host=OLLAMA_HOST)
        res = c.list()
        models = res.get("models", []) if isinstance(res, dict) else getattr(res, "models", [])
        names = []
        for m in models or []:
            name = m.get("name", "") if isinstance(m, dict) else (getattr(m, "model", "") or getattr(m, "name", ""))
            if name:
                names.append(name)
        for preferred in ["qwen2.5:1.5b", "gemma3:4b", "dolphin-mistral:latest", "qwen3:8b", "deepseek-r1:8b", "qwen3.5:9b", "gpt-oss:20b"]:
            for name in names:
                if name == preferred or name.startswith(preferred + ":"):
                    return name
        if names:
            return names[0]
    except Exception:
        pass
    return "qwen2.5:1.5b"

OLLAMA_MODEL = _detect_default_model()
DEFAULT_RESULTS = 3
MAX_RESULTS = 8
NUM_CONTEXT = 4096
NUM_PREDICT_QA = 1024
NUM_PREDICT_SUMMARY = 700
NUM_PREDICT = NUM_PREDICT_QA
TEMPERATURE = 0.2
REPEAT_PENALTY = 1.05
KEEP_ALIVE = "60m"
NUM_THREADS = int(os.environ.get("OLLAMA_NUM_THREADS") or _physical_cores or os.cpu_count() or 8)

client = ollama.Client(host=OLLAMA_HOST)
STOP_EVENT = threading.Event()


def check_ollama(force=False, model_name=None):
    global OLLAMA_HOST, OLLAMA_MODEL, client
    model_name = model_name or OLLAMA_MODEL
    hosts_to_try = [OLLAMA_HOST]
    for h in ["http://127.0.0.1:11435", "http://127.0.0.1:11434"]:
        if h not in hosts_to_try:
            hosts_to_try.append(h)
    last_err = ""
    for h in hosts_to_try:
        try:
            test_client = ollama.Client(host=h)
            result = test_client.list()
            OLLAMA_HOST = h
            client = test_client
            models = result.get("models", []) if isinstance(result, dict) else getattr(result, "models", [])
            names = []
            for model in models or []:
                if isinstance(model, dict):
                    names.append(model.get("name", ""))
                else:
                    names.append(getattr(model, "model", "") or getattr(model, "name", ""))
            installed = any(name == model_name or name.startswith(model_name + ":") for name in names) if model_name else (len(names) > 0)
            if not installed and len(names) > 0 and (not model_name or model_name == OLLAMA_MODEL or model_name in ["qwen2.5:1.5b", "Basic", "Moderate"]):
                OLLAMA_MODEL = names[0]
                installed = True
            return {
                "ok": installed,
                "server": True,
                "model": installed,
                "host": OLLAMA_HOST,
                "error": None if installed else f"Model '{model_name}' is not installed. Run: ollama pull {model_name}",
            }
        except Exception as exc:
            last_err = str(exc)
            continue
    return {"ok": False, "server": False, "model": False, "error": f"Ollama is not running. Start Ollama, then try again.\n\n{last_err}"}


def preload_model(model_name=None):
    """Pre-warm the model into memory so user requests start generating immediately without delay."""
    model_name = model_name or OLLAMA_MODEL
    try:
        client.generate(
            model=model_name,
            prompt="",
            keep_alive=KEEP_ALIVE,
            options={
                "num_ctx": NUM_CONTEXT,
                "num_thread": NUM_THREADS,
            },
        )
        return True
    except Exception:
        return False



def reset_generation_stop():
    STOP_EVENT.clear()


def stop_generation():
    STOP_EVENT.set()


def _format_empty_response_message(model_name: str = "", error_detail: str = "") -> str:
    m_info = f" ({model_name})" if model_name else ""
    err_info = f"\n\n*Technical Details:* `{error_detail}`" if error_detail else ""
    return (
        f"⚠️ **Could not generate a response.**\n\n"
        f"The local model{m_info} is unavailable, timed out, or encountered an error. "
        f"Please verify that Ollama is running and has a compatible model loaded.\n\n"
        f"Click **🔄 Retry** below to try generating this response again.{err_info}"
    )


def _stream_chat(prompt, num_predict=NUM_PREDICT_QA, num_ctx=NUM_CONTEXT, chunk_callback=None, model_name=None):
    reset_generation_stop()

    # Extract clean text representation of prompt
    user_query = prompt[1] if isinstance(prompt, tuple) else str(prompt)
    clean_p = user_query.strip()

    # 1. Unsupported capability guard (e.g. image/video/audio generation)
    is_unsupported, cap_type, cap_msg = check_unsupported_capability(clean_p)
    if is_unsupported and cap_msg:
        if chunk_callback:
            chunk_callback(cap_msg)
        return cap_msg

    # 2. Deterministic real-time datetime queries (Asia/Kolkata default & global DST)
    if is_datetime_query(clean_p):
        dt_ans = get_datetime_answer(clean_p)
        if chunk_callback:
            chunk_callback(dt_ans)
        return dt_ans

    requested_model = model_name or OLLAMA_MODEL
    # Available models from local Ollama
    available = get_available_models()
    available_set = set(available)
    available_prefixes = {a.split(":")[0] for a in available}

    # Fallback cascade: requested model -> installed models -> standard cascade
    candidates = [requested_model] if requested_model else []
    for m in available:
        if m not in candidates:
            candidates.append(m)
    for fb in ["qwen2.5:1.5b", "gemma3:4b", "dolphin-mistral:latest"]:
        if fb not in candidates:
            candidates.append(fb)

    start_time = time.perf_counter()
    last_error = ""

    for candidate in candidates:
        if STOP_EVENT.is_set():
            break

        # Fast-path: if candidate is known not to be installed, skip expensive check
        if available_set and candidate not in available_set and candidate not in available_prefixes:
            last_error = f"Model '{candidate}' is not installed."
            continue

        cand_status = check_ollama(model_name=candidate)
        if not cand_status["ok"]:
            last_error = cand_status.get("error", "Model not available")
            continue

        output = []
        try:
            if isinstance(prompt, tuple):
                system_msg, user_msg = prompt
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ]
            else:
                messages = [{"role": "user", "content": str(prompt)}]

            response = client.chat(
                model=candidate,
                messages=messages,
                stream=True,
                keep_alive=KEEP_ALIVE,
                options={
                    "temperature": TEMPERATURE,
                    "num_ctx": num_ctx,
                    "num_predict": num_predict,
                    "repeat_penalty": REPEAT_PENALTY,
                    "num_thread": NUM_THREADS,
                },
            )
            for chunk in response:
                if STOP_EVENT.is_set():
                    break
                if isinstance(chunk, dict):
                    token = chunk.get("message", {}).get("content", "")
                else:
                    token = getattr(getattr(chunk, "message", None), "content", "")
                if token:
                    output.append(token)
                    if chunk_callback:
                        chunk_callback(token)

            if STOP_EVENT.is_set():
                if output:
                    return "".join(output)
                return "*[Generation stopped by user]*"

            res_str = "".join(output).strip()
            if res_str:
                latency = (time.perf_counter() - start_time) * 1000
                from backend.diagnostics import log_ai_operation
                log_ai_operation(
                    operation="stream_chat",
                    model=candidate,
                    latency_ms=latency,
                    success=True
                )
                return "".join(output)
            else:
                last_error = f"Model '{candidate}' returned an empty response."
                continue

        except Exception as exc:
            last_error = str(exc)
            if output and len("".join(output).strip()) > 20:
                # Preserve partial output if generation fails after producing useful text
                partial = "".join(output)
                res_msg = partial + f"\n\n*[Generation interrupted: {last_error}]*"
                if chunk_callback:
                    chunk_callback(f"\n\n*[Generation interrupted: {last_error}]*")
                return res_msg
            continue

    if STOP_EVENT.is_set():
        return "*[Generation stopped by user]*"

    from backend.diagnostics import log_ai_operation
    log_ai_operation(
        operation="stream_chat",
        model=requested_model,
        success=False,
        error_category="all_models_failed"
    )

    fallback_msg = _format_empty_response_message(requested_model, last_error)
    if chunk_callback:
        chunk_callback(fallback_msg)
    return fallback_msg


def generate_simple_response(prompt, temperature=0.2, num_ctx=NUM_CONTEXT, num_predict=NUM_PREDICT, chunk_callback=None, model_name=None):
    return _stream_chat(prompt, num_predict=num_predict, num_ctx=num_ctx, chunk_callback=chunk_callback, model_name=model_name)


SUMMARY_INTENT_PATTERNS = [
    r"^\s*summarise\b",
    r"^\s*summarize\b",
    r"^\s*summary\b",
    r"\bgive\s+(me\s+)?(a\s+)?summary\b",
    r"\bgive\s+summary\b",
    r"\bexplain\s+(this\s+)?(document|pdf|file)\b",
    r"\bsummarize\s+(this|the\s+pdf|the\s+document|the\s+file|uploaded\s+pdf|uploaded\s+document)\b",
    r"\bsummarise\s+(this|the\s+pdf|the\s+document|the\s+file|uploaded\s+pdf|uploaded\s+document)\b",
    r"\bsummarize\s+.*?(pdf|document|file)\b",
    r"\bsummarise\s+.*?(pdf|document|file)\b",
    r"\b(pdf|document)\s+summary\b",
    r"\b(short|detailed|executive|quick|full)\s+summary\b",
    r"\bgive\s+(me\s+)?notes\b",
    r"\bmake\s+notes\s+from\s+this\b",
    r"\bmake\s+notes\b",
    r"\bgenerate\s+summary\b",
    r"\bdocument\s+summary\b",
]


def is_summary_intent(query: str) -> bool:
    if not query:
        return False
    q = query.strip().lower()
    return any(re.search(pat, q) for pat in SUMMARY_INTENT_PATTERNS)


def _is_outside_knowledge_requested(query: str) -> bool:
    q = query.lower()
    keywords = [
        "outside", "general knowledge", "in general", "own knowledge",
        "beyond the doc", "beyond the document", "not in the doc",
        "not in doc", "not in document", "from your knowledge",
        "without document", "regardless", "ignore the document",
        "generally speaking", "outside of the document", "outside of document"
    ]
    return any(kw in q for kw in keywords)


def _is_doc_specific_question(query: str) -> bool:
    if is_summary_intent(query):
        return True
    q = query.lower()
    keywords = [
        "this pdf", "this document", "the document", "the pdf", "what does page",
        "summarize chapter", "summarize section", "according to", "in chapter",
        "in section", "on page", "what is this document about", "what is this pdf about",
        "in the file", "from the document", "from the pdf", "does this document",
        "does the pdf", "in the assignment", "in assignment"
    ]
    return any(kw in q for kw in keywords)


def _build_context(query, doc_id, n_results, all_doc_ids=None):
    """Build labeled document excerpts for the prompt."""
    if all_doc_ids and len(all_doc_ids) > 1:
        chunks_per_doc = max(2, n_results)
        results = search_documents_per_doc(query, chunks_per_doc=chunks_per_doc, doc_ids=all_doc_ids)
    else:
        results = search_documents(query, n_results=n_results, doc_id=doc_id)

    if not results:
        return "", results

    from collections import OrderedDict
    grouped = OrderedDict()
    for r in results:
        fname = r.get("filename", "Unknown")
        grouped.setdefault(fname, []).append(r)

    parts = []
    doc_number = 0
    for fname, chunks in grouped.items():
        doc_number += 1
        for chunk in chunks:
            page = chunk.get("page", 1)
            text = chunk.get("text", "").strip()
            if len(text) > 1200:
                text = text[:1200] + "..."
            parts.append(
                f"[Document {doc_number}: {fname}, page {page}]\n"
                f"{text}"
            )
    return "\n\n".join(parts), results


def _build_prompt(query, context, history, selected_text, mode, context_mode="normal", doc_name=None):
    history_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-3:]) if history else ""
    selected_info = f"\nSELECTED PAGE/TEXT:\n{selected_text}\n" if selected_text else ""
    history_info = f"\nCONVERSATION HISTORY:\n{history_text}\n" if history_text else ""

    c_mode = (context_mode or "normal").lower()
    dn = doc_name or "the uploaded document"

    if c_mode == "normal":
        system_msg = (
            "You are Infinity AI, an expert, thoughtful, private, offline-first desktop assistant "
            "running entirely on the user's local machine with zero cloud connectivity.\n\n"
            "Guidelines:\n"
            "1. Comprehensive & Helpful: Answer the user's questions clearly, accurately, and thoroughly.\n"
            "2. Direct & Concise: Answer immediately. For simple questions, remain concise and direct without boilerplate.\n"
            "3. Presentation & Formatting: Format answers cleanly with Markdown:\n"
            "   - Major topic: clear heading (# or ##).\n"
            "   - Important concepts: bold key terms.\n"
            "   - Procedures & steps: numbered list.\n"
            "   - Comparisons: comparison table with clear columns.\n"
            "   - Programming: organize with Approach, Code (syntax-highlighted code block), Explanation, and Complexity.\n"
            "   - Do not force every answer into the same template; adapt naturally to the question type.\n"
            "4. Conversational Flow: Seamlessly maintain context from prior turns."
        )
        user_msg = (
            f"{selected_info}{history_info}"
            f"QUESTION: {query}"
        )
    elif c_mode == "document":
        system_msg = (
            f"You are Infinity AI, an expert, private offline desktop assistant analyzing the document: {dn}.\n\n"
            "Guidelines:\n"
            f"1. Document Grounding: When answering questions regarding {dn}, prioritize and ground your explanations in the provided DOCUMENT EXCERPTS. Always cite the specific page number(s) (e.g. 'Page 1') when referencing facts, topics, or questions from {dn}.\n"
            "2. Complete & Accurate Explanations: When the excerpts mention a concept, assignment question, or topic, provide a complete, clear, and comprehensive answer using the document context and accurate principles.\n"
            f"3. Missing Information: If the user specifically asks whether {dn} covers or mentions a topic that is completely absent from the excerpts and the document, clearly state that this information is not found in {dn}.\n"
            "4. Formatting: Use rich markdown with clear headings, bullet points, numbered steps, and formatted code blocks."
        )
        user_msg = (
            f"DOCUMENT EXCERPTS ({dn}):\n{context or '(no matching excerpts found)'}\n"
            f"{selected_info}{history_info}\n"
            f"QUESTION: {query}"
        )
    else:  # "rag"
        system_msg = (
            "You are Infinity AI, an expert offline assistant synthesizing information from the user's indexed knowledge base.\n\n"
            "Guidelines:\n"
            "1. Knowledge Base Synthesis: Base answers on the provided excerpts across all indexed documents. Never invent facts or citations.\n"
            "2. Missing Information: If no relevant information is found in the knowledge base, state:\n"
            "\"I couldn't find this information in the indexed documents.\"\n"
            "3. Multi-Document Citations: Distinguish clearly between different source documents and pages.\n"
            "4. Formatting: Use clear markdown formatting."
        )
        user_msg = (
            f"KNOWLEDGE BASE EXCERPTS:\n{context or '(no matching excerpts found)'}\n"
            f"{selected_info}{history_info}\n"
            f"QUESTION: {query}"
        )

    return system_msg, user_msg


def ask_document(
    query: str,
    selected_text: Optional[str] = None,
    mode: str = "Balanced",
    doc_id: Optional[str] = None,
    history=None,
    chunk_callback: Optional[Callable[[str], None]] = None,
    document_hash_value: str = "",
    all_doc_ids=None,
    model_name: Optional[str] = None,
    context_mode: str = "normal",
    doc_name: Optional[str] = None,
):
    query = query.strip()
    if not query:
        return ""
    reset_generation_stop()

    c_mode = (context_mode or "normal").lower()
    dn = doc_name or "the uploaded document"

    # 0. Check for unsupported capabilities (image/video/music generation)
    is_unsupported, cap_type, cap_msg = check_unsupported_capability(query, has_image_attachment=False)
    if is_unsupported and cap_msg:
        if chunk_callback:
            chunk_callback(cap_msg)
        return cap_msg

    # 1. Check for deterministic date/time questions
    if is_datetime_query(query):
        dt_ans = get_datetime_answer(query)
        if chunk_callback:
            chunk_callback(dt_ans)
        return dt_ans

    # Route summary intent directly to summarizer if document is present
    if is_summary_intent(query) and (doc_id or c_mode == "document"):
        from backend.vector_store import get_all_document_text
        from backend.summarizer import summarize_document
        full_text = get_all_document_text(doc_id) if doc_id else ""
        if full_text:
            return summarize_document(full_text, chunk_callback=chunk_callback, model_name=model_name)

    clean_q = query.lower().strip()
    is_greeting = clean_q in ["hi", "hello", "hey", "good morning", "good evening", "who are you", "what can you do"]
    if is_greeting and c_mode == "document":
        prompt = (
            f"User said: '{query}'. Respond warmly and concisely as Infinity AI, letting them know that '{dn}' is loaded and you are ready to answer questions about it or help them understand it."
        )
        return generate_simple_response(prompt, num_predict=256, chunk_callback=chunk_callback, model_name=model_name)

    allow_outside = _is_outside_knowledge_requested(query)
    doc_asked = _is_doc_specific_question(query) or bool(selected_text)
    has_docs = bool(doc_id or all_doc_ids)

    # Determine whether document retrieval should be enforced
    enforce_doc = (c_mode in ["document", "rag"] or doc_asked) and has_docs

    context, results = "", []
    if enforce_doc:
        n_results = {"Basic": 2, "Balanced": 3, "Advanced": 5}.get(mode, DEFAULT_RESULTS)
        search_target_id = doc_id if (c_mode == "document" or doc_id) else None
        search_all_ids = all_doc_ids if (c_mode == "rag" or (not doc_id and all_doc_ids)) else None
        context, results = _build_context(query, search_target_id, min(n_results, MAX_RESULTS), all_doc_ids=search_all_ids)
        max_score = max((r.get("score", 0) for r in results), default=0)
        is_meta_query = any(t in query.lower() for t in ["what is this document about", "what is this pdf about", "overview of this document", "what topics are", "table of contents"])
        has_evidence = bool(results) and (max_score >= 0.08 or is_meta_query)
        if not allow_outside and not has_evidence:
            if doc_asked or c_mode == "document":
                # If question explicitly asked about the document or is in document mode without relevance
                # Check if it was a general question mistakenly in document mode
                is_general_qa = any(query.lower().startswith(p) for p in ["what is ", "what are ", "explain ", "write a ", "how to ", "how do ", "solve "]) and not doc_asked
                if is_general_qa:
                    # Seamlessly answer general question
                    context = ""
                else:
                    msg = f"I couldn't find this information in {dn}." if c_mode == "document" else "I couldn't find this information in the uploaded document. No supporting evidence was found in the indexed sources."
                    if chunk_callback:
                        chunk_callback(msg)
                    return msg
    elif has_docs and doc_asked:
        n_results = {"Basic": 2, "Balanced": 3, "Advanced": 5}.get(mode, DEFAULT_RESULTS)
        context, results = _build_context(query, doc_id, min(n_results, MAX_RESULTS), all_doc_ids=all_doc_ids)

    reset_generation_stop()
    history = history or []
    cache_hash = document_hash_value or "|".join(f"{r.get('filename')}:{r.get('page')}:{r.get('text', '')[:80]}" for r in results)
    model_name = model_name or OLLAMA_MODEL
    cache_mode = f"{mode}:{model_name}:{c_mode}"
    cached = None if history or selected_text or allow_outside else get_cached_answer(cache_hash, query, cache_mode)
    if cached:
        if chunk_callback:
            chunk_callback(cached)
        return cached

    num_predict = {"Basic": 512, "Balanced": 768, "Advanced": 1024}.get(mode, NUM_PREDICT_QA)
    effective_context_mode = c_mode if context else "normal"
    answer = generate_simple_response(
        _build_prompt(query, context, history, selected_text, mode, context_mode=effective_context_mode, doc_name=dn),
        num_predict=num_predict,
        chunk_callback=chunk_callback,
        model_name=model_name,
    )
    if not history and not selected_text and not allow_outside and answer and not STOP_EVENT.is_set():
        save_cached_answer(cache_hash, query, cache_mode, answer)
    return answer



def ask_document_simple(**kwargs):
    return ask_document(**kwargs)


def test_ollama():
    return check_ollama()["ok"]


def get_available_models():
    try:
        result = client.list()
        models = result.get("models", []) if isinstance(result, dict) else getattr(result, "models", [])
        return [m.get("name", "") if isinstance(m, dict) else getattr(m, "model", "") for m in models]
    except Exception:
        return []
