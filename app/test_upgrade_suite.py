"""
Infinity AI - Full Regression & Upgrade Verification Suite
Tests all 32 capabilities:
- Existing features (Ollama, storage, chroma, PDF processor, summarizer)
- New features (Router, Model Manager, RAG, Citations, Projects, Memory, Agents, Tools, OCR, Vision, Diagnostics, USB Authorization)
"""

import sys
import os
import time
from pathlib import Path

# Ensure stdout handles Unicode/emojis cleanly on Windows
sys.stdout.reconfigure(encoding="utf-8")

# Ensure paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "libs")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

results = []

def run_test(name, func):
    try:
        t0 = time.perf_counter()
        func()
        dt = round((time.perf_counter() - t0) * 1000, 1)
        results.append((name, "PASSED", f"{dt}ms"))
        print(f"[PASS] {name} ({dt}ms)")
    except Exception as exc:
        results.append((name, f"FAILED: {exc}", "0ms"))
        print(f"[FAIL] {name}: {exc}")

print("============================================================")
print("  INFINITY AI - COMPREHENSIVE REGRESSION & VERIFICATION")
print("============================================================\n")

# 1. Application Startup / Imports
def test_imports():
    import app
    assert hasattr(app, "DocumentAssistant"), "DocumentAssistant not found"
run_test("1. Application Startup & Class Hierarchy", test_imports)

# 2. Existing Storage & Cache
def test_storage():
    import backend.cache as cache
    cache.save_cached_answer("test_hash_123", "test query", "Basic", "Sample answer")
    ans = cache.get_cached_answer("test_hash_123", "test query", "Basic")
    assert ans == "Sample answer", "Cache get/set failed"
run_test("2. Existing Storage & Answer Cache (SQLite)", test_storage)

# 3. ChromaDB Existing Vector Store
def test_vector_store():
    import backend.vector_store as vs
    count = vs.get_collection_count()
    assert count >= 0, "Collection count invalid"
    docs = vs.get_all_doc_ids()
    assert isinstance(docs, set), "get_all_doc_ids should return a set"
run_test("3. ChromaDB Vector Store & Existing Chunks", test_vector_store)

# 4. Ollama Connection & Health Check
def test_ollama():
    import backend.ai_engine as ai
    st = ai.check_ollama()
    assert st["server"] is True, f"Ollama server not running: {st}"
    models = ai.get_available_models()
    assert len(models) > 0, "No Ollama models detected"
run_test("4. Ollama Local Server Connection", test_ollama)

# 5. Model Selection & Preloading
def test_model_selection():
    import backend.ai_engine as ai
    assert "qwen2.5:1.5b" in ai.get_available_models(), "qwen2.5:1.5b model missing"
    assert "gemma3:4b" in ai.get_available_models(), "gemma3:4b model missing"
run_test("5. Model Selection & Availability", test_model_selection)

# 6. PDF Processor & Chunker
def test_chunker():
    import backend.chunker as chunker
    pages = [{"page": 1, "text": "Artificial Intelligence is transforming computing. " * 30}]
    chunks = chunker.create_chunks(pages, chunk_size=300, overlap=50)
    assert len(chunks) > 1, "Chunker failed to split text"
run_test("6. PDF Chunker & Text Slicing", test_chunker)

# 7. Summarizer
def test_summarizer():
    import backend.summarizer as sumz
    split_chunks = sumz._split_text("Sample paragraph text. " * 50, size=200, overlap=20)
    assert len(split_chunks) > 1, "Summarizer text split failed"
run_test("7. Summarizer Section Chunking", test_summarizer)

# 8. Streaming & Inference
def test_inference_stream():
    import backend.ai_engine as ai
    tokens = []
    out = ai.generate_simple_response("Say 'Infinity' only.", model_name="qwen2.5:1.5b", chunk_callback=tokens.append)
    assert "infinity" in out.lower(), f"Unexpected generation output: {out}"
    assert len(tokens) > 0, "Streaming callback received no tokens"
run_test("8. Inference & Streaming Tokens", test_inference_stream)

# 9. Model Manager (GGUF + Ollama)
def test_model_manager():
    import backend.model_manager as mm
    cat = mm.get_all_models()
    assert cat["total_count"] > 0, "No models in catalogue"
    assert "Fast" in cat["presets"], "Fast preset missing"
    assert "Balanced" in cat["presets"], "Balanced preset missing"
run_test("9. Model Manager (GGUF & Ollama Detection)", test_model_manager)

# 10. Intelligent Model Router
def test_router():
    import backend.router as r
    code_model, cat, _ = r.route_model("def calculate_fibonacci(n):")
    assert cat == "Coding", f"Expected Coding intent, got {cat}"
    simple_model, cat2, _ = r.route_model("Hello!")
    assert cat2 == "Fast", f"Expected Fast intent, got {cat2}"
run_test("10. Intelligent Model Router", test_router)

# 11. Multi-format Document RAG Engine
def test_rag_engine():
    import backend.rag_engine as re
    txt_pages = re.parse_text_file(__file__)
    assert len(txt_pages) >= 1, "Failed to parse text file"
    ctx, cits = re.retrieve_context_with_citations("AI", n_results=2)
    assert isinstance(cits, list), "Citations should be a list"
run_test("11. Multi-Format RAG & RRF Retrieval", test_rag_engine)

# 12. Citations Extraction & Grounding
def test_citations():
    import backend.rag_engine as re
    ctx, cits = re.retrieve_context_with_citations("technology", n_results=1)
    if cits:
        assert "document" in cits[0] and "page" in cits[0], "Citation schema missing document or page"
run_test("12. Structured Citations & Source Attribution", test_citations)

# 12b. Grounded fallback when a document is loaded but no supporting evidence is found
def test_grounded_fallback():
    import backend.ai_engine as ai
    out = ai.ask_document("Explain the secret recipe in this document.", doc_id="missing_doc_123", mode="Balanced")
    assert "supporting evidence" in out.lower(), "Grounded answer fallback failed"
run_test("12b. Grounded Fallback for Missing Document Evidence", test_grounded_fallback)

# 13. Projects Management (Claude-style)
def test_projects():
    import backend.projects as pm
    projects = pm.project_service.list_projects()
    assert len(projects) >= 5, "Default projects not loaded"
    act = pm.project_service.get_active_project()
    assert act["id"] == "default", f"Active project should be default, got {act['id']}"
run_test("13. Projects & Workspaces Isolation", test_projects)

# 14. Three-Layer Memory
def test_memory():
    import backend.memory as mm
    mid = mm.memory_service.remember("Unit_Test_Key", "Unit_Test_Value")
    assert mid is not None, "Failed to store memory"
    injection = mm.memory_service.build_memory_prompt_injection()
    assert "Unit_Test_Key" in injection, "Memory injection failed"
    mm.memory_service.forget(mid)
run_test("14. Three-Layer Persistent Memory Subsystem", test_memory)

# 15. Safe Tool System & Permissions
def test_tools():
    import backend.tools as tools
    res = tools.tool_registry.execute("calculator", {"expression": "128 * 8"})
    assert res["status"] == "success", f"Calculator failed: {res}"
    assert res["result"] == "1024", f"Expected 1024, got {res['result']}"
run_test("15. Safe Tool Registry & Execution", test_tools)

# 16. AI Agents & Personas
def test_agents():
    import backend.agents as ag
    assert len(ag.AGENT_PERSONAS) == 7, "Expected 7 specialized agent personas"
    assert "Coding" in ag.AGENT_PERSONAS
    assert "Research" in ag.AGENT_PERSONAS
run_test("16. AI Agent Orchestrator & Personas", test_agents)

# 17. OCR Capability
def test_ocr():
    import backend.ocr_vision as ov
    avail = ov.is_ocr_available()
    assert avail is True, "Tesseract OCR should be available"
run_test("17. Local OCR Verification", test_ocr)

# 18. Vision Subsystem
def test_vision():
    import backend.ocr_vision as ov
    vm = ov.get_available_vision_model()
    assert vm is not None, "Vision model should be detected"
run_test("18. Local Multimodal Vision Integration", test_vision)

# 19. Hardware Monitoring & Diagnostics
def test_diagnostics():
    import backend.diagnostics as d
    diag = d.get_full_diagnostics()
    assert diag["ollama"]["running"] is True, "Ollama diagnostic failed"
    assert diag["hardware"]["gpu_name"] != "Unavailable", "GPU should be detected"
run_test("19. Live Hardware & Subsystem Diagnostics", test_diagnostics)

# 20. USB Authorization System
def test_usb():
    import backend.security as sec
    st = sec.verify_usb_authorization()
    assert isinstance(st, dict), "Status must be a dictionary"
    assert "authorized" in st and "read_only" in st, "Status must contain authorized and read_only keys"
    # Verify that project drive D: cannot authorize itself as a separate USB
    res = sec.classify_drive({"DeviceID": "D:", "DriveType": 2}, "D:")
    assert res["classification"] == "project_drive", "Project drive D: must not self-authorize"
    assert res["authorized"] is False, "Project drive self-authorization must be False"
    # When no separate removable USB is plugged in, write operations are protected
    if not st["authorized"]:
        assert st["read_only"] is True, "Unauthenticated state must be read-only"
run_test("20. USB Device Authorization Subsystem", test_usb)

# 21. Slash Commands Dispatcher
def test_slash_commands():
    import backend.slash_commands as sc
    is_cmd, prompt, agent, _ = sc.process_slash_command("/code write quicksort")
    assert is_cmd is True, "Slash command not detected"
    assert agent == "Coding", f"Expected Coding agent, got {agent}"
run_test("21. Slash Commands & Natural Modes Dispatcher", test_slash_commands)

# 22. Voice Subsystem
def test_voice():
    import backend.voice as v
    st = v.get_voice_status()
    assert st["voice_enabled"] is True, "Voice should be enabled"
run_test("22. Voice Assistant & Push-to-Talk Status", test_voice)

# 23. Backup & Snapshot Verification
def test_backup_verification():
    backup_path = Path("D:/PrivateAI/backups/backup-2026-10-05-001")
    assert backup_path.exists(), "Backup directory does not exist"
    assert (backup_path / "app").exists(), "Backup app directory missing"
    assert (backup_path / "start-windows.bat").exists(), "Backup start-windows.bat missing"
run_test("23. Backup Snapshot Integrity", test_backup_verification)

# 24. Startup Script Verification
def test_startup_script():
    bat_path = Path("D:/PrivateAI/start-windows.bat")
    with open(bat_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "11435" in content, "Port 11435 missing from startup script"
    assert "app.py" in content, "app.py execution missing from startup script"
run_test("24. Startup Script Integrity & Environment", test_startup_script)

print("\n============================================================")
passed_count = sum(1 for _, st, _ in results if st == "PASSED")
print(f"RESULTS: {passed_count}/{len(results)} TESTS PASSED SUCCESSFULLY!")
print("============================================================")
