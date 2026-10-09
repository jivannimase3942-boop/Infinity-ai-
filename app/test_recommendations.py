"""
Infinity AI - Dynamic Context-Aware Recommendations Test Suite
Test file: app/test_recommendations.py

Validates that Related topics & actions recommendations are:
1. Sick leave email -> email-related suggestions (professional, shorter, subject line, polite, WhatsApp)
2. Dijkstra -> algorithm-specific suggestions (simple example, step-by-step, C++ implementation, time complexity)
3. PDF summary -> document-analysis suggestions (key points, exam notes, generate questions, difficult sections)
4. Python error -> debugging suggestions (explain error/code, find bugs, optimize, test cases)
5. General knowledge question -> topic-specific follow-ups (clean entity-bound follow-ups, zero code suggestions)
6. Negative tests: Unrelated generic suggestions are NOT returned
7. Suggestion clicking execution verification (_set_prompt_and_send)
8. Suggestions update dynamically with new AI responses
9. Database integrity and data preservation verification (8 projects, 6 files, 16 conversations, 27 messages, 1278 chunks)
"""

import sys
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "libs"))
sys.path.insert(0, str(APP_DIR))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from backend.intent_engine import intent_engine
from backend.db import get_connection
from backend.vector_store import get_collection_count

passed_count = 0
failed_count = 0
results = []


def record(test_num: int, name: str, passed: bool, detail: str = ""):
    global passed_count, failed_count
    status = "PASS" if passed else "FAIL"
    if passed:
        passed_count += 1
    else:
        failed_count += 1
    results.append((test_num, name, status, detail))
    print(f"[{test_num:02d}] {status}: {name}" + (f" ({detail})" if detail else ""), flush=True)


def run_tests():
    print("=" * 76, flush=True)
    print("  INFINITY AI — CONTEXT-AWARE RECOMMENDATION TEST SUITE", flush=True)
    print("=" * 76, flush=True)

    initial_counts = {}
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        initial_counts["integrity"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM projects")
        initial_counts["projects"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM project_files")
        initial_counts["files"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM conversations")
        initial_counts["conversations"] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        initial_counts["messages"] = c.fetchone()[0]
    initial_counts["chroma"] = get_collection_count()

    # -----------------------------------------------------------------
    # Case 1: Sick leave email -> email-related suggestions
    # -----------------------------------------------------------------
    email_q = "Write a sick leave email for 2 days due to fever"
    email_resp = (
        "Subject: Sick Leave Request - 2 Days\n\n"
        "Dear Manager,\n\n"
        "I am writing to inform you that I am unwell with a fever and will be unable "
        "to work for the next 2 days. I will return to the office on Monday.\n\n"
        "Sincerely,\nAlex"
    )
    email_analysis = intent_engine.analyze(email_q, ai_response=email_resp)
    suggs_email = email_analysis.get("suggestions", [])

    p1 = (
        email_analysis.get("category") == "communication"
        and any("professional" in s.lower() for s in suggs_email)
        and any("shorter" in s.lower() for s in suggs_email)
        and any("subject line" in s.lower() for s in suggs_email)
        and any("polite" in s.lower() for s in suggs_email)
        and any("whatsapp" in s.lower() for s in suggs_email)
    )
    # Critical negative check: ZERO code/developer suggestions
    p1_no_code = not any(
        "code" in s.lower() or "bug" in s.lower() or "unit test" in s.lower() or "memory" in s.lower()
        for s in suggs_email
    )
    record(1, "Sick leave email -> Email-related recommendations", p1 and p1_no_code, f"Got: {suggs_email[:3]}")

    # -----------------------------------------------------------------
    # Case 2: Dijkstra -> algorithm-specific suggestions
    # -----------------------------------------------------------------
    dijkstra_q = "Explain Dijkstra algorithm"
    dijkstra_resp = (
        "Dijkstra's algorithm finds the shortest path between nodes in a weighted graph. "
        "It uses a priority queue with greedy selection to achieve O((V + E) log V) time complexity."
    )
    dijkstra_analysis = intent_engine.analyze(dijkstra_q, ai_response=dijkstra_resp)
    suggs_dijkstra = dijkstra_analysis.get("suggestions", [])

    p2 = (
        dijkstra_analysis.get("category") in ["algorithms", "programming"]
        and any("simple example" in s.lower() or "example" in s.lower() for s in suggs_dijkstra)
        and any("step by step" in s.lower() for s in suggs_dijkstra)
        and any("implementation" in s.lower() or "c++" in s.lower() for s in suggs_dijkstra)
        and any("time complexity" in s.lower() or "complexity" in s.lower() for s in suggs_dijkstra)
    )
    p2_no_email = not any("email" in s.lower() or "subject line" in s.lower() for s in suggs_dijkstra)
    record(2, "Dijkstra algorithm -> Algorithm-specific recommendations", p2 and p2_no_email, f"Got: {suggs_dijkstra[:3]}")

    # -----------------------------------------------------------------
    # Case 3: PDF summary -> document-analysis suggestions
    # -----------------------------------------------------------------
    doc_q = "Summarize this PDF document"
    doc_resp = "This document presents the quarterly financial performance of Q3 2026."
    doc_analysis = intent_engine.analyze(
        doc_q,
        ai_response=doc_resp,
        has_active_document=True,
        active_document={"name": "financial_report.pdf", "page_count": 18}
    )
    suggs_doc = doc_analysis.get("suggestions", [])

    p3 = (
        doc_analysis.get("category") == "document"
        and any("key points" in s.lower() for s in suggs_doc)
        and any("exam notes" in s.lower() or "notes" in s.lower() for s in suggs_doc)
        and any("questions" in s.lower() for s in suggs_doc)
        and any("difficult sections" in s.lower() for s in suggs_doc)
    )
    p3_no_code = not any("unit test" in s.lower() or "memory" in s.lower() for s in suggs_doc)
    record(3, "PDF summary -> Document-analysis recommendations", p3 and p3_no_code, f"Got: {suggs_doc[:3]}")

    # -----------------------------------------------------------------
    # Case 4: Python error -> debugging suggestions
    # -----------------------------------------------------------------
    err_q = "Why am I getting IndexError: list index out of range in Python?"
    err_resp = (
        "This error occurs when attempting to access an index that does not exist in the list. "
        "For example, accessing myList[len(myList)] raises IndexError because lists are 0-indexed."
    )
    err_analysis = intent_engine.analyze(err_q, ai_response=err_resp)
    suggs_err = err_analysis.get("suggestions", [])

    p4 = (
        err_analysis.get("category") in ["debugging", "programming"]
        and any("code" in s.lower() for s in suggs_err)
        and any("bugs" in s.lower() for s in suggs_err)
        and any("optimize" in s.lower() for s in suggs_err)
        and any("test cases" in s.lower() for s in suggs_err)
    )
    p4_no_email = not any("email" in s.lower() or "subject line" in s.lower() for s in suggs_err)
    record(4, "Python error -> Debugging recommendations", p4 and p4_no_email, f"Got: {suggs_err[:3]}")

    # -----------------------------------------------------------------
    # Case 5: General knowledge question -> topic-specific follow-ups
    # -----------------------------------------------------------------
    gk_q = "What is photosynthesis and why is it important?"
    gk_resp = (
        "Photosynthesis is the biochemical process by which green plants, algae, and some bacteria "
        "convert sunlight, water, and carbon dioxide into oxygen and glucose."
    )
    gk_analysis = intent_engine.analyze(gk_q, ai_response=gk_resp)
    suggs_gk = gk_analysis.get("suggestions", [])

    # Topic must be extracted and bound
    p5_topic = "photosynthesis" in gk_analysis.get("topic", "").lower()
    p5_relevance = any("analogy" in s.lower() or "applications" in s.lower() or "facts" in s.lower() for s in suggs_gk)
    # MUST NOT show developer suggestions
    p5_no_code = not any(
        "code" in s.lower() or "bug" in s.lower() or "unit test" in s.lower() or "memory" in s.lower()
        for s in suggs_gk
    )
    p5_no_email = not any("email" in s.lower() or "subject line" in s.lower() for s in suggs_gk)
    record(5, "General knowledge question -> Topic-specific follow-ups", p5_topic and p5_relevance and p5_no_code and p5_no_email, f"Topic='{gk_analysis.get('topic')}', Suggestions={suggs_gk[:2]}")

    # -----------------------------------------------------------------
    # Case 6: Negative verification: Zero generic developer suggestions for non-coding
    # -----------------------------------------------------------------
    non_coding_queries = [
        "How to plan a surprise birthday party?",
        "What caused the French Revolution in 1789?",
        "Compare renewable energy vs fossil fuels",
        "Write a formal apology letter to a customer"
    ]
    all_clean = True
    for query in non_coding_queries:
        analysis = intent_engine.analyze(query)
        suggs = analysis.get("suggestions", [])
        has_dev_suggs = any(
            "show clean code" in s.lower()
            or "edge-case bugs" in s.lower()
            or "unit tests" in s.lower()
            or "optimize performance and memory" in s.lower()
            for s in suggs
        )
        if has_dev_suggs:
            all_clean = False
            print(f"   [!] Leaked dev suggestions on non-coding query: '{query}' -> {suggs}")
            break

    record(6, "Negative check: No generic developer suggestions for non-coding topics", all_clean, "100% domain isolated")

    # -----------------------------------------------------------------
    # Case 7: Suggestion click execution test
    # -----------------------------------------------------------------
    from unittest.mock import MagicMock
    from frontend.ui import DocumentAssistant

    # Test that _set_prompt_and_send triggers handle_send with the exact suggestion
    app = DocumentAssistant()
    app.withdraw()
    try:
        panel = app.chat
        panel.handle_send = MagicMock()

        test_action = "Make this email more professional"
        panel._set_prompt_and_send(test_action)

        sent_text = panel.input.get("1.0", "end-1c")
        p7 = (sent_text == test_action and panel.handle_send.called)
        record(7, "Clicking suggestion executes exact suggested action as next user request", p7, f"Input set & handle_send called: {panel.handle_send.called}")
    finally:
        for attr in ["_startup_job", "_hw_poll_job"]:
            job = getattr(app, attr, None)
            if job:
                try:
                    app.after_cancel(job)
                except Exception:
                    pass
        app.update_idletasks()
        app.destroy()

    # -----------------------------------------------------------------
    # Case 8: Dynamic update after each AI response
    # -----------------------------------------------------------------
    # Simulate first turn (Sick leave email)
    t1_analysis = intent_engine.analyze("Draft a sick leave email", ai_response="Subject: Sick Leave\n\nDear Manager, ...")
    t1_suggs = t1_analysis.get("suggestions", [])
    t1_is_email = any("professional" in s.lower() for s in t1_suggs)

    # Simulate second turn (Follow-up asking for algorithm in same conversation)
    t2_analysis = intent_engine.analyze("Also explain Dijkstra algorithm", ai_response="Dijkstra is a shortest path algorithm...")
    t2_suggs = t2_analysis.get("suggestions", [])
    t2_is_algo = any("time complexity" in s.lower() or "example" in s.lower() for s in t2_suggs)

    p8 = (t1_is_email and t2_is_algo and t1_suggs != t2_suggs)
    record(8, "Recommendations update dynamically after every new AI response", p8, "Pills refresh seamlessly across conversation turns")

    # -----------------------------------------------------------------
    # Case 9: Database integrity and data count preservation
    # -----------------------------------------------------------------
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        integrity_res = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM projects")
        proj_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM project_files")
        files_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM conversations")
        conv_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        msg_count = c.fetchone()[0]

    chroma_count = get_collection_count()

    p9 = (
        integrity_res == "ok"
        and proj_count == initial_counts["projects"] == 8
        and files_count == initial_counts["files"]
        and conv_count == initial_counts["conversations"] == 16
        and msg_count == initial_counts["messages"] == 27
        and chroma_count == initial_counts["chroma"]
    )
    record(9, "Data safety: SQLite integrity OK and exact counts preserved", p9, f"Projects={proj_count}, Files={files_count}, Conv={conv_count}, Msg={msg_count}, Chroma={chroma_count}")

    print("\n" + "=" * 76, flush=True)
    print(f"RECOMMENDATION SUITE SUMMARY: {passed_count}/{passed_count + failed_count} CHECKS PASSED", flush=True)
    print("=" * 76, flush=True)

    if failed_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    run_tests()
