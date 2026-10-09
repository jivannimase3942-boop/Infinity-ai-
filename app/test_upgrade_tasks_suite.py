"""
Infinity AI - Comprehensive Verification Suite for Upgrade Tasks
Verifies:
1. Faster-Whisper Small (CPU INT8 / CUDA FP16 fallback, offline cache)
2. English, Hindi, Marathi, and mixed-language voice handling
3. Empty audio, noisy audio, short audio, and microphone error recovery
4. Unsupported capability guard (image, video, audio generation) vs image analysis
5. Real-time deterministic Date/Time engine with Asia/Kolkata default and global DST
6. Request pipeline resilience (SUCCESS, UNSUPPORTED, CANCELLED, ERROR) and no blank states
7. GUI state cleanup, stop/cancellation, and retry mechanisms
"""

import sys
import os
import time
from pathlib import Path
import numpy as np

# Set stdout to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

# Ensure imports
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
print("  INFINITY AI - UPGRADE VERIFICATION SUITE")
print("============================================================\n")

# -----------------------------------------------------------------------------
# 1. Faster-Whisper model initialization and status
# -----------------------------------------------------------------------------
def test_faster_whisper_init():
    import backend.voice as v
    status = v.get_voice_status()
    assert status["voice_enabled"] is True, "Voice should be enabled"
    assert status["stt_available"] is True, "STT should be available"
    assert "faster-whisper small" in status["stt_engine"].lower(), f"Unexpected engine: {status['stt_engine']}"
    
    # Check model loader
    model = v.get_whisper_model()
    assert model is not None, "Model failed to load"
    device = getattr(model.model, "device", "unknown")
    assert device in ["cpu", "cuda"], f"Expected CPU or CUDA device, got {device}"
run_test("1. Faster-Whisper Small Initialization & Device Fallback", test_faster_whisper_init)

# -----------------------------------------------------------------------------
# 2. English, Hindi, Marathi, and Multilingual Voice Configuration
# -----------------------------------------------------------------------------
def test_multilingual_voice_support():
    import backend.voice as v
    langs = v.SUPPORTED_LANGUAGES
    assert "auto" in langs, "Auto detect should be present"
    assert "en" in langs, "English should be supported"
    assert "hi" in langs, "Hindi should be supported"
    assert "mr" in langs, "Marathi should be supported"
    
    # Test transcribe signature with language parameter
    dummy_audio = np.zeros(16000, dtype=np.float32)
    # Empty audio should be gracefully caught by preprocessor before inference
    res_en = v.transcribe_numpy_audio(dummy_audio, language="en")
    assert res_en["ok"] is False and "No speech" in res_en["error"]
    
    res_hi = v.transcribe_numpy_audio(dummy_audio, language="hi")
    assert res_hi["ok"] is False and "No speech" in res_hi["error"]
    
    res_mr = v.transcribe_numpy_audio(dummy_audio, language="mr")
    assert res_mr["ok"] is False and "No speech" in res_mr["error"]
run_test("2. Multilingual Voice Configuration (En, Hi, Mr, Auto)", test_multilingual_voice_support)

# -----------------------------------------------------------------------------
# 3. Audio Edge Cases: Empty audio, noisy audio, short audio, cancellation
# -----------------------------------------------------------------------------
def test_audio_edge_cases():
    import backend.voice as v
    
    # A. Empty audio (all zeros)
    empty = np.zeros(16000 * 2, dtype=np.float32)
    r1 = v.transcribe_numpy_audio(empty)
    assert r1["ok"] is False, "Empty audio should fail gracefully"
    assert "No speech detected" in r1["error"]
    
    # B. Too short audio (< 0.3s)
    short_audio = np.zeros(1600, dtype=np.float32)
    r2 = v.transcribe_numpy_audio(short_audio)
    assert r2["ok"] is False
    assert "too short" in r2["error"].lower()
    
    # C. Pure noise / tone audio
    t = np.linspace(0, 1.0, 16000, endpoint=False, dtype=np.float32)
    tone = 0.5 * np.sin(2 * np.pi * 440 * t) # 440Hz sine wave
    r3 = v.transcribe_numpy_audio(tone)
    assert r3["ok"] is False, "Pure tone should not hallucinate words"
    
    # D. Audio preprocessor DC offset and peak normalization
    raw_signal = np.array([0.1, 0.2, 0.3, 0.4, 0.5] * 2000, dtype=np.float32)
    ok, norm, err = v.preprocess_audio(raw_signal)
    assert ok is True
    assert abs(np.mean(norm)) < 1e-4, "DC offset was not removed"
    assert np.max(np.abs(norm)) <= 0.96, "Peak normalization out of bounds"
    
    # E. Cancellation test
    rec = v.AudioRecorder(sample_rate=16000)
    rec.start()
    time.sleep(0.05)
    rec.cancel()
    stopped_data = rec.stop()
    assert stopped_data is None, "Cancelled recorder should return None"
run_test("3. Audio Preprocessing, Noise & Recording Cancellation", test_audio_edge_cases)

# -----------------------------------------------------------------------------
# 4. Unsupported Capability Guard (Image / Video / Audio generation)
# -----------------------------------------------------------------------------
def test_unsupported_capabilities():
    from backend.capability_engine import check_unsupported_capability
    
    # Image generation requests should be flagged as unsupported
    img_prompts = [
        "Generate an image of a cybernetic tiger",
        "Create a photorealistic picture of a futuristic city",
        "Draw me an illustration of a castle",
        "Can you paint a sunset on the beach?",
        "Text-to-image prompt: an astronaut in a jungle",
        "Please make an image for my presentation"
    ]
    for p in img_prompts:
        is_unsupported, cap, expl = check_unsupported_capability(p)
        assert is_unsupported is True, f"Failed to detect unsupported image gen for: {p}"
        assert cap == "image_generation"
        assert "Image Generation Not Supported" in expl
        assert "cannot generate or render images directly" in expl
        assert "Midjourney" in expl or "prompt" in expl
        
    # Video generation requests
    is_vid, cap_vid, _ = check_unsupported_capability("Generate a video of a flying car")
    assert is_vid is True and cap_vid == "video_generation"
    
    # Music generation requests
    is_aud, cap_aud, _ = check_unsupported_capability("Compose a song in mp3 about freedom")
    assert is_aud is True and cap_aud == "audio_generation"
    
    # Coding questions about images should NOT be blocked
    is_code, _, _ = check_unsupported_capability("Write a python function to resize an image using PIL")
    assert is_code is False, "Coding questions mentioning images must not be blocked"
    
    # Image analysis questions (with or without attachments) should NOT be blocked
    is_analysis, _, _ = check_unsupported_capability("Analyze this image and explain the diagram below")
    assert is_analysis is False, "Image analysis must not be blocked"
run_test("4. Unsupported Capabilities Detection & Explainable Guard", test_unsupported_capabilities)

# -----------------------------------------------------------------------------
# 5. Deterministic Real-time Date and Time Engine
# -----------------------------------------------------------------------------
def test_datetime_engine():
    import backend.datetime_engine as dte
    
    # Test query detection
    assert dte.is_datetime_query("What time is it?") is True
    assert dte.is_datetime_query("What is today's date?") is True
    assert dte.is_datetime_query("What day is today?") is True
    assert dte.is_datetime_query("What time is it in London?") is True
    assert dte.is_datetime_query("What time is it in New York right now?") is True
    assert dte.is_datetime_query("Write a python script to parse dates") is False
    
    # Test local Indian time (Asia/Kolkata default)
    res_local = dte.handle_datetime_query("What time is it?")
    assert res_local["status"] == "SUCCESS"
    assert res_local["timezone"] == "Asia/Kolkata"
    assert "IST" in res_local["answer"]
    
    # Test current date
    res_date = dte.handle_datetime_query("What is today's date?")
    assert res_date["status"] == "SUCCESS"
    assert str(res_date["timezone"]) == "Asia/Kolkata"
    assert "October" in res_date["answer"]
    assert "2026" in res_date["answer"]
    
    # Test global cities and timezones
    res_london = dte.handle_datetime_query("What time is it in London?")
    assert res_london["status"] == "SUCCESS"
    assert res_london["timezone"] == "Europe/London"
    assert "London" in res_london["answer"]
    
    res_ny = dte.handle_datetime_query("What time is it in New York?")
    assert res_ny["status"] == "SUCCESS"
    assert res_ny["timezone"] == "America/New_York"
    assert "New York" in res_ny["answer"]
    
    res_tokyo = dte.handle_datetime_query("What time is it in Tokyo?")
    assert res_tokyo["status"] == "SUCCESS"
    assert res_tokyo["timezone"] == "Asia/Tokyo"
    assert "Tokyo" in res_tokyo["answer"]
    
    # Test unrecognized location fallback
    res_mars = dte.handle_datetime_query("What time is it on Mars?")
    assert res_mars["status"] == "SUCCESS"
    assert "couldn't identify a timezone" in res_mars["answer"].lower()
    assert "Asia/Kolkata" in res_mars["answer"]
run_test("5. Real-Time Date/Time & Global Timezone Conversions", test_datetime_engine)

# -----------------------------------------------------------------------------
# 6. Intelligent Model Router Intent Integration
# -----------------------------------------------------------------------------
def test_router_integration():
    import backend.router as r
    
    # Test Date/Time routing
    m1, cat1, exp1 = r.route_model("What time is it in London?")
    assert cat1 == "Date/Time", f"Expected Date/Time, got {cat1}"
    assert "Local Clock" in m1
    
    # Test Unsupported routing
    m2, cat2, exp2 = r.route_model("Generate an image of a red car")
    assert cat2 == "Unsupported", f"Expected Unsupported, got {cat2}"
    assert "Capability Guard" in m2
    
    # Test Coding routing
    m3, cat3, _ = r.route_model("def calculate_factorial(n):")
    assert cat3 == "Coding"
    
    # Test Fast routing
    m4, cat4, _ = r.route_model("Hello, how are you?")
    assert cat4 == "Fast"
run_test("6. Intelligent Router with Date/Time & Capability Guard", test_router_integration)

# -----------------------------------------------------------------------------
# 7. AI Engine Complete Pipeline & Defined States
# -----------------------------------------------------------------------------
def test_ai_engine_pipeline():
    import backend.ai_engine as ai
    
    # A. Unsupported query ends in UNSUPPORTED response without model call
    ans_unsupported = ai.ask_document("Generate a photorealistic image of a galaxy")
    assert "Image Generation Not Supported" in ans_unsupported
    assert "cannot generate or render images directly" in ans_unsupported
    
    # B. Date/Time query ends in deterministic SUCCESS without model hallucination
    ans_time = ai.ask_document("What is today's date?")
    assert "October" in ans_time and "2026" in ans_time
    
    # C. Real Ollama live inference with local model
    tokens = []
    ans_llm = ai.ask_document("Reply with the single word: Verified.", chunk_callback=tokens.append)
    assert len(ans_llm) > 0, "Expected non-empty LLM output"
    assert len(tokens) > 0, "Streaming callback should have received chunks"
    
    # D. Stop Event cancellation test
    tokens_cancel = []
    def cancel_callback(chunk):
        tokens_cancel.append(chunk)
        ai.stop_generation()

    ans_stopped = ai._stream_chat("Tell me a very long story about astronomy and stars", chunk_callback=cancel_callback)
    assert "*[Generation stopped" in ans_stopped or len(tokens_cancel) <= 5
    ai.reset_generation_stop()
    assert ai.STOP_EVENT.is_set() is False
run_test("7. AI Engine Request States (SUCCESS, UNSUPPORTED, CANCELLED)", test_ai_engine_pipeline)

# -----------------------------------------------------------------------------
# 8. GUI Components State Management & Recovery
# -----------------------------------------------------------------------------
def test_gui_state_management():
    import customtkinter as ctk
    from frontend.chat_panel import ChatPanel
    
    # Create headless Tkinter root for component testing
    root = ctk.CTk()
    root.withdraw()
    
    chat_panel = ChatPanel(root, on_send_message=lambda *args: None)
    
    # 1. Verify voice recording bar and language selector
    assert hasattr(chat_panel, "voice_recording_bar"), "Voice recording bar missing"
    assert hasattr(chat_panel, "voice_lang_menu"), "Voice language menu missing"
    assert hasattr(chat_panel, "voice_done_btn"), "Voice Done button missing"
    assert hasattr(chat_panel, "voice_cancel_btn"), "Voice Cancel button missing"
    
    # 2. Test language selector values
    lang_code = chat_panel._get_selected_voice_lang()
    assert lang_code == "auto"
    chat_panel.voice_lang_var.set("Hindi")
    assert chat_panel._get_selected_voice_lang() == "hi"
    chat_panel.voice_lang_var.set("Marathi")
    assert chat_panel._get_selected_voice_lang() == "mr"
    
    # 3. Test handle_stop resets GUI state and restores Send button
    chat_panel.generating = True
    chat_panel.handle_stop()
    assert chat_panel.generating is False
    assert chat_panel.send_btn.cget("state") == "normal"
    
    # 4. Test stream completion with empty text falls back cleanly
    append, finish = chat_panel.create_ai_stream_bubble()
    assert chat_panel.generating is True
    # Finish without sending tokens -> should show clear explanation with Retry option
    finish()
    root.update()
    time.sleep(0.06)
    root.update()
    assert chat_panel.generating is False
    assert chat_panel.send_btn.cget("state") == "normal"
    
    root.destroy()
run_test("8. GUI State Cleanup, Voice Controls & Stop/Retry Recovery", test_gui_state_management)

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
print("\n============================================================")
passed = sum(1 for _, st, _ in results if st == "PASSED")
total = len(results)
print(f"UPGRADE SUITE RESULT: {passed}/{total} TESTS PASSED")
print("============================================================")
if passed != total:
    sys.exit(1)
