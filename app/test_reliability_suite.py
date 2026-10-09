"""
Infinity AI - Comprehensive Reliability & Verification Test Suite
Tests all 25 specific test conditions (A through Y) defined in Requirement 32.
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Set up paths exactly as required for local dependencies
APP_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = APP_DIR.parent
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "libs")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure Ollama host is directed to port 11435
os.environ["OLLAMA_HOST"] = "127.0.0.1:11435"

results = []

def run_subtest(letter: str, name: str, fn):
    t0 = time.perf_counter()
    try:
        fn()
        elapsed = (time.perf_counter() - t0) * 1000
        results.append((letter, name, "PASS", f"{elapsed:.1f}ms"))
        print(f"[{letter}] PASS: {name} ({elapsed:.1f}ms)")
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append((letter, name, "FAIL", str(exc)))
        print(f"[{letter}] FAIL: {name} - {exc}")

# ==============================================================================
# A. Chat response
# ==============================================================================
def test_a_chat_response():
    from backend.ai_engine import ask_document
    resp = ask_document("Say 'Infinity AI online' and nothing else.", mode="Basic", context_mode="normal")
    assert resp and len(resp.strip()) > 0, "Empty chat response returned"
    assert "Traceback" not in resp, f"Unexpected error response: {resp}"

# ==============================================================================
# B. Model unavailable handling
# ==============================================================================
def test_b_model_unavailable():
    from backend.ai_engine import ask_document
    # Request a non-existent model to verify fallback cascade or clean user diagnostic
    resp = ask_document("Test query", model_name="nonexistent_fantasy_model:99b", context_mode="normal")
    assert resp and len(resp.strip()) > 0, "Model failure resulted in empty response string"
    assert "Traceback (most recent call last)" not in resp, "Raw Python stack trace leaked to user"

# ==============================================================================
# C. Empty response handling
# ==============================================================================
def test_c_empty_response():
    from backend.ai_engine import _format_empty_response_message
    msg = _format_empty_response_message("qwen2.5:1.5b")
    assert msg and len(msg) > 0, "Empty response message formatter failed"
    assert "qwen2.5:1.5b" in msg, "Model name missing in empty response message"
    assert "unavailable" in msg.lower() or "check" in msg.lower(), "Expected helpful diagnostic in empty response message"

# ==============================================================================
# D. Fallback model
# ==============================================================================
def test_d_fallback_model():
    from backend.router import get_fallback_model_cascade
    cascade = get_fallback_model_cascade("nonexistent:1b")
    assert len(cascade) >= 2, f"Fallback cascade too short: {cascade}"
    assert "qwen2.5:1.5b" in cascade or "gemma3:4b" in cascade or "dolphin-mistral:latest" in cascade, "Missing core models in fallback cascade"

# ==============================================================================
# E. PDF upload / validation
# ==============================================================================
def test_e_pdf_upload():
    from backend.pdf_processor import validate_document_file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        tf.write(b"Valid document content for testing.")
        tf_name = tf.name
    try:
        valid, err = validate_document_file(tf_name)
        assert valid is True, f"Failed to validate valid document: {err}"
        # Validate rejection of non-existent file
        inv_valid, inv_err = validate_document_file("C:/nonexistent_file_xyz_123.pdf")
        assert inv_valid is False, "Nonexistent file was falsely marked valid"
    finally:
        if os.path.exists(tf_name):
            os.unlink(tf_name)

# ==============================================================================
# F. PDF extraction
# ==============================================================================
def test_f_pdf_extraction():
    import pymupdf
    from backend.pdf_processor import extract_text_from_pdf
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf_path = tf.name
    try:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 72), "Infinity AI Test Heading\nThis is paragraph one with important physics information.")
        doc.save(pdf_path)
        doc.close()

        pages = extract_text_from_pdf(pdf_path)
        assert len(pages) == 1, f"Expected 1 page, got {len(pages)}"
        assert "Infinity AI Test Heading" in pages[0]["text"], "Extracted text missing heading"
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

# ==============================================================================
# G. PDF page count
# ==============================================================================
def test_g_pdf_page_count():
    import pymupdf
    from backend.pdf_processor import extract_text_from_pdf, get_pdf_page_count
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf_path = tf.name
    try:
        doc = pymupdf.open()
        for i in range(3):
            p = doc.new_page()
            p.insert_text((50, 72), f"Page content number {i + 1}")
        doc.save(pdf_path)
        doc.close()

        cnt = get_pdf_page_count(pdf_path)
        assert cnt == 3, f"Expected page count 3, got {cnt}"
        pages = extract_text_from_pdf(pdf_path)
        assert len(pages) == 3, f"Expected 3 pages, got {len(pages)}"
        assert pages[0]["page"] == 1 and pages[2]["page"] == 3, "Page numbering corrupted"
    finally:
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

# ==============================================================================
# H. PDF chunking
# ==============================================================================
def test_h_pdf_chunking():
    from backend.chunker import create_chunks
    sample_pages = [
        {"page": 1, "text": "Section 1: Overview\n" + ("Quantum computing accelerates simulation. " * 30), "tables": []},
        {"page": 2, "text": "Section 2: Architecture\n" + ("Superconducting qubits operate at cryogenic temperatures. " * 30), "tables": []}
    ]
    chunks = create_chunks(sample_pages, chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 2, f"Expected multiple chunks, got {len(chunks)}"
    first = chunks[0]
    assert "page" in first and "chunk_id" in first and "text" in first, "Chunk missing required metadata fields"
    assert first["page"] == 1, "Page metadata mismatched"

# ==============================================================================
# I. PDF indexing into vector store
# ==============================================================================
def test_i_pdf_indexing():
    from backend.vector_store import add_chunks, remove_document_chunks
    test_doc_id = "test_doc_reliability_xyz"
    test_chunks = [
        {"page": 1, "text": "The speed of light in vacuum is approximately 299,792,458 meters per second.", "chunk_id": "c1"},
        {"page": 2, "text": "Einstein formulated the theory of general relativity in 1915.", "chunk_id": "c2"}
    ]
    try:
        count = add_chunks(test_chunks, test_doc_id, "rel_test.pdf", "/tmp/rel_test.pdf", "hash123")
        assert count == 2, f"Expected 2 indexed chunks, got {count}"
    finally:
        remove_document_chunks(test_doc_id)

# ==============================================================================
# J. ChromaDB retrieval
# ==============================================================================
def test_j_chromadb_retrieval():
    from backend.vector_store import add_chunks, search_chunks, remove_document_chunks
    test_doc_id = "test_retrieval_doc_abc"
    test_chunks = [
        {"page": 1, "text": "The boiling point of liquid nitrogen is 77 Kelvin at atmospheric pressure.", "chunk_id": "n1"}
    ]
    try:
        add_chunks(test_chunks, test_doc_id, "nitrogen.pdf", "/tmp/nitrogen.pdf", "hash_n")
        results = search_chunks("boiling point liquid nitrogen Kelvin", doc_id=test_doc_id, n_results=1)
        assert len(results) > 0, "ChromaDB retrieval returned empty results"
        assert "77 Kelvin" in results[0]["text"], f"Expected '77 Kelvin' in retrieved chunk, got: {results[0]['text']}"
        assert results[0].get("document_id") == test_doc_id, "Document ID not preserved in search result"
    finally:
        remove_document_chunks(test_doc_id)

# ==============================================================================
# K. PDF Q&A
# ==============================================================================
def test_k_pdf_qa():
    from backend.vector_store import add_chunks, remove_document_chunks
    from backend.ai_engine import ask_document
    test_doc_id = "test_qa_doc_qed"
    test_chunks = [
        {"page": 4, "text": "The Golden Gate Bridge opened to pedestrian traffic on May 27, 1937 in San Francisco.", "chunk_id": "gg1"}
    ]
    try:
        add_chunks(test_chunks, test_doc_id, "bridge.pdf", "/tmp/bridge.pdf", "hash_b")
        answer = ask_document("When did the bridge open to pedestrian traffic?", doc_id=test_doc_id, mode="Balanced", context_mode="document")
        assert answer and len(answer) > 0, "Empty answer returned for document QA"
        assert "1937" in answer or "May 27" in answer, f"Expected '1937' or 'May 27' in answer, got: {answer}"
    finally:
        remove_document_chunks(test_doc_id)

# ==============================================================================
# L. PDF summary
# ==============================================================================
def test_l_pdf_summary():
    from backend.summarizer import summarize_document
    doc_text = (
        "Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics. "
        "Key concepts include superposition and entanglement. In 2019, Google claimed quantum supremacy. "
        "Practical applications include cryptography, material science, and pharmaceutical drug discovery."
    )
    tokens = []
    def callback(tok):
        tokens.append(tok)

    summarize_document(doc_text, callback, model_name="qwen2.5:1.5b")
    full_summary = "".join(tokens)
    assert len(full_summary) > 50, f"Summary output too short: {full_summary}"
    assert "Summary" in full_summary or "Key Points" in full_summary or "Quantum" in full_summary, "Summary missing structured headers"

# ==============================================================================
# M. Large PDF handling
# ==============================================================================
def test_m_large_pdf():
    from backend.summarizer import summarize_hierarchical
    sections = [f"Chapter {i}: Detailed analysis of subsystem component {i}. " + ("Data points and metrics. " * 30) for i in range(1, 6)]
    large_text = "\n\n".join(sections)
    out = summarize_hierarchical(large_text, chunk_callback=None, model_name="qwen2.5:1.5b")
    assert len(out) > 80, "Hierarchical summary output too short"
    assert "Summary" in out or "Key Points" in out, "Hierarchical summary missing standard sections"

# ==============================================================================
# N. Corrupt PDF handling
# ==============================================================================
def test_n_corrupt_pdf():
    from backend.pdf_processor import extract_text_from_pdf
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(b"%PDF-1.4\nCORRUPTED_BYTES_RANDOM_GARBAGE_NO_XREF_TABLE_HERE")
        corrupt_path = tf.name
    try:
        try:
            pages = extract_text_from_pdf(corrupt_path)
            assert isinstance(pages, list), "Corrupt PDF did not return a list"
        except (ValueError, RuntimeError) as err:
            assert "corrupt" in str(err).lower() or "error" in str(err).lower()
    finally:
        if os.path.exists(corrupt_path):
            os.unlink(corrupt_path)

# ==============================================================================
# O. Empty PDF handling
# ==============================================================================
def test_o_empty_pdf():
    from backend.pdf_processor import extract_text_from_pdf, validate_document_file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        empty_path = tf.name
    try:
        valid, err = validate_document_file(empty_path)
        assert valid is False, "0-byte PDF was marked valid"
        pages = extract_text_from_pdf(empty_path)
        assert len(pages) >= 1 and ("empty" in pages[0]["text"].lower() or len(pages[0]["text"]) == 0), "Empty PDF should return empty notice"
    finally:
        if os.path.exists(empty_path):
            os.unlink(empty_path)

# ==============================================================================
# P. Document source citations
# ==============================================================================
def test_p_citations():
    from backend.rag_engine import retrieve_context_with_citations
    from backend.vector_store import add_chunks, remove_document_chunks
    test_doc_id = "test_cit_doc_111"
    test_chunks = [
        {"page": 7, "text": "Photosynthesis converts carbon dioxide and water into glucose and oxygen.", "chunk_id": "p7"}
    ]
    try:
        add_chunks(test_chunks, test_doc_id, "biology.pdf", "/tmp/biology.pdf", "hash_bio")
        ctx, cits = retrieve_context_with_citations("photosynthesis glucose oxygen", doc_id=test_doc_id, n_results=1)
        assert len(cits) > 0, "No citations returned"
        cit = cits[0]
        assert "document" in cit and "page" in cit and "text" in cit, f"Citation schema missing fields: {cit}"
        assert cit["page"] == 7, f"Expected page 7 in citation, got: {cit['page']}"
    finally:
        remove_document_chunks(test_doc_id)

# ==============================================================================
# Q. UI initialization
# ==============================================================================
def test_q_ui_initialization():
    from frontend.theme import THEME
    assert "bg_primary" in THEME and "accent" in THEME, "Theme tokens missing"
    from frontend.welcome_screen import WelcomeScreen
    from frontend.chat_panel import ChatPanel
    assert WelcomeScreen is not None and ChatPanel is not None

# ==============================================================================
# R. Sidebar sections
# ==============================================================================
def test_r_sidebar_sections():
    from frontend.sidebar import Sidebar
    import inspect
    src = inspect.getsource(Sidebar)
    assert "CHATS" in src, "CHATS section missing in Sidebar"
    assert "WORKSPACE" in src, "WORKSPACE section missing in Sidebar"
    assert "TOOLS" in src, "TOOLS section missing in Sidebar"
    assert "SYSTEM" in src, "SYSTEM section missing in Sidebar"

# ==============================================================================
# S. Sidebar collapse
# ==============================================================================
def test_s_sidebar_collapse():
    from frontend.sidebar import Sidebar
    assert hasattr(Sidebar, "toggle_collapse"), "Sidebar missing toggle_collapse method"
    assert hasattr(Sidebar, "_render_expanded"), "Sidebar missing _render_expanded"
    assert hasattr(Sidebar, "_render_collapsed"), "Sidebar missing _render_collapsed"

# ==============================================================================
# T. File upload UI & Document card
# ==============================================================================
def test_t_file_upload_ui():
    from frontend.chat_panel import ChatPanel
    assert hasattr(ChatPanel, "show_document_card"), "ChatPanel missing show_document_card"
    assert hasattr(ChatPanel, "hide_document_card"), "ChatPanel missing hide_document_card"
    assert hasattr(ChatPanel, "set_document_context_mode"), "ChatPanel missing set_document_context_mode"

# ==============================================================================
# U. USB Security
# ==============================================================================
def test_u_usb_security():
    from backend.security import verify_usb_authorization, is_running_on_removable_media, classify_drive
    auth = verify_usb_authorization()
    assert "authorized" in auth and "read_only" in auth, "USB auth dict missing keys"
    is_rem, _ = is_running_on_removable_media()
    assert isinstance(is_rem, bool), "is_running_on_removable_media must return bool"
    res = classify_drive({"DeviceID": "D:", "DriveType": 2}, "D:")
    assert res["authorized"] is False, "Project drive D: must not self-authorize"

# ==============================================================================
# V. Workspace Isolation
# ==============================================================================
def test_v_workspace_isolation():
    from backend.db import verify_and_isolate_database
    from backend.vector_store import verify_and_isolate_chroma
    db_res = verify_and_isolate_database()
    assert db_res.get("status") in ["valid", "bound", "quarantined_foreign_workspace"], f"Unexpected DB isolation status: {db_res}"
    chroma_res = verify_and_isolate_chroma()
    assert chroma_res.get("status") in ["valid", "bound", "quarantined_foreign_chroma"], f"Unexpected Chroma isolation status: {chroma_res}"

# ==============================================================================
# W. Database integrity
# ==============================================================================
def test_w_database_integrity():
    from backend.db import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        row = cursor.fetchone()
        assert row and row[0] == "ok", f"SQLite integrity check failed: {row}"
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
        tbl_count = cursor.fetchone()[0]
        assert tbl_count >= 10, f"Expected at least 10 tables, found {tbl_count}"

# ==============================================================================
# X. Existing project functionality
# ==============================================================================
def test_x_projects():
    from backend.projects import project_service
    projs = project_service.list_projects()
    assert len(projs) >= 5, f"Expected at least 5 projects, got {len(projs)}"
    active = project_service.get_active_project()
    assert active is not None and "id" in active, "Active project invalid"

# ==============================================================================
# Y. Existing memory functionality
# ==============================================================================
def test_y_memory():
    from backend.memory import memory_service
    m_id = memory_service.remember("Reliability_Key_123", "Reliability_Val_456")
    try:
        assert m_id is not None, "Failed to create memory"
        injection = memory_service.build_memory_prompt_injection()
        assert "Reliability_Key_123" in injection, "Created memory not found in prompt injection"
    finally:
        memory_service.forget(m_id)


def main():
    print("============================================================")
    print("  INFINITY AI - RELIABILITY TEST SUITE (TESTS A THROUGH Y)")
    print("============================================================")

    test_list = [
        ("A", "Chat Response Generation", test_a_chat_response),
        ("B", "Model Unavailable Handling", test_b_model_unavailable),
        ("C", "Empty Response Handling & Diagnostics", test_c_empty_response),
        ("D", "Fallback Model Cascade", test_d_fallback_model),
        ("E", "PDF Upload & File Validation", test_e_pdf_upload),
        ("F", "PDF Text Extraction", test_f_pdf_extraction),
        ("G", "PDF Page Count Preservation", test_g_pdf_page_count),
        ("H", "PDF Chunking with Metadata", test_h_pdf_chunking),
        ("I", "PDF Vector Store Indexing", test_i_pdf_indexing),
        ("J", "ChromaDB Top-K Retrieval", test_j_chromadb_retrieval),
        ("K", "PDF Grounded Question Answering", test_k_pdf_qa),
        ("L", "Structured PDF Summarization", test_l_pdf_summary),
        ("M", "Large Multi-Page Document Hierarchical Handling", test_m_large_pdf),
        ("N", "Corrupt PDF Resilient Handling", test_n_corrupt_pdf),
        ("O", "Empty & 0-Byte PDF Handling", test_o_empty_pdf),
        ("P", "Document Source Citations Schema", test_p_citations),
        ("Q", "UI Initialization & Design Tokens", test_q_ui_initialization),
        ("R", "Sidebar Categorization (Chats/Workspace/Tools/System)", test_r_sidebar_sections),
        ("S", "Sidebar Collapse / Expand State", test_s_sidebar_collapse),
        ("T", "File Upload UI & Document Card Action Buttons", test_t_file_upload_ui),
        ("U", "USB Security & Hardware Lock Subsystem", test_u_usb_security),
        ("V", "Workspace & Database Hardware Isolation", test_v_workspace_isolation),
        ("W", "SQLite Database Integrity Verification", test_w_database_integrity),
        ("X", "Existing Projects Subsystem Preservation", test_x_projects),
        ("Y", "Existing Three-Layer Memory Subsystem Preservation", test_y_memory),
    ]

    for letter, name, fn in test_list:
        run_subtest(letter, name, fn)

    print("\n============================================================")
    passed = sum(1 for _, _, status, _ in results if status == "PASS")
    total = len(results)
    print(f"RELIABILITY RESULTS: {passed}/{total} TESTS PASSED")
    print("============================================================")
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()
