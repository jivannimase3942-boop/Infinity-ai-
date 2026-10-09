"""
Infinity AI - Production Offline Voice Assistant Subsystem
Architecture:
  Microphone (sounddevice) -> Local faster-whisper (small, INT8/FP16) -> Infinity AI -> Local Windows SAPI TTS

Operates 100% offline without cloud APIs, telemetry, or external network requests.
Features:
- faster-whisper small model cached locally in D:\\PrivateAI\\models\\whisper
- CTranslate2 INT8 compute type on CPU for fast inference, CUDA/FP16 when compatible on GPU
- English, Hindi, and Marathi support, including mixed-language speech (Hinglish/Marathi-English)
- Automatic language detection with optional manual language selector
- Pre-processing: DC offset removal, RMS energy check, peak normalization, VAD filtering, beam search
- Device selection, microphone permissions handling, empty audio and noise handling
- Non-blocking asynchronous recording with clean Stop and Cancel workflows
"""

import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union

import numpy as np

# Optional sounddevice for microphone capture
try:
    import sounddevice as sd
except ImportError:
    sd = None

# Optional faster_whisper for offline speech-to-text
try:
    import faster_whisper
except ImportError:
    faster_whisper = None

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WHISPER_CACHE_DIR = BASE_DIR / "models" / "whisper"

SUPPORTED_LANGUAGES = {
    "auto": "Auto Detect",
    "en": "English",
    "hi": "Hindi (हिंदी)",
    "mr": "Marathi (मराठी)"
}

MICROPHONE_STATE = {
    "active": False,
    "listening": False,
    "transcribing": False,
    "last_error": None,
    "selected_language": "auto",
    "selected_device": None,
}

ACTIVE_SPEECH_PROC: Optional[subprocess.Popen] = None
_WHISPER_MODEL_INSTANCE = None
_MODEL_LOCK = threading.Lock()
_RECORDING_LOCK = threading.Lock()

ACTIVE_RECORDER = None


def _find_local_model_path() -> Optional[str]:
    """Finds the local faster-whisper snapshot directory if already downloaded."""
    if not WHISPER_CACHE_DIR.exists():
        return None
    snapshots_dir = WHISPER_CACHE_DIR / "models--Systran--faster-whisper-small" / "snapshots"
    if snapshots_dir.exists():
        for snap in snapshots_dir.iterdir():
            if snap.is_dir() and (snap / "model.bin").exists():
                return str(snap)
    # Check directly in cache dir
    if (WHISPER_CACHE_DIR / "model.bin").exists():
        return str(WHISPER_CACHE_DIR)
    return None


def get_whisper_model():
    """
    Singleton loader for faster-whisper small model.
    Attempts CUDA/FP16 first if available and compatible; falls back to CPU INT8.
    """
    global _WHISPER_MODEL_INSTANCE
    if _WHISPER_MODEL_INSTANCE is not None:
        return _WHISPER_MODEL_INSTANCE

    with _MODEL_LOCK:
        if _WHISPER_MODEL_INSTANCE is not None:
            return _WHISPER_MODEL_INSTANCE

        if faster_whisper is None:
            raise RuntimeError("faster-whisper is not installed in the environment.")

        local_path = _find_local_model_path()
        model_source = local_path if local_path else "small"
        download_root = str(WHISPER_CACHE_DIR)

        # 1. Attempt CUDA/FP16 if GPU is present and functional
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                supported_cuda = ctranslate2.get_supported_compute_types("cuda")
                if "float16" in supported_cuda:
                    try:
                        # Try loading with CUDA
                        model = faster_whisper.WhisperModel(
                            model_source,
                            device="cuda",
                            compute_type="float16",
                            download_root=download_root,
                            local_files_only=bool(local_path)
                        )
                        # Verify CUDA actually works with an inference pass (catches missing cublas64_12.dll etc.)
                        dummy = np.zeros(1600, dtype=np.float32)
                        _ = list(model.transcribe(dummy, beam_size=1)[0])
                        _WHISPER_MODEL_INSTANCE = model
                        return model
                    except Exception:
                        # Fall back to CPU INT8
                        pass
        except Exception:
            pass

        # 2. Fall back to CPU with CTranslate2 INT8
        model = faster_whisper.WhisperModel(
            model_source,
            device="cpu",
            compute_type="int8",
            download_root=download_root,
            local_files_only=bool(local_path)
        )
        _WHISPER_MODEL_INSTANCE = model
        return model


def list_audio_input_devices() -> List[Dict[str, Any]]:
    """Lists available microphone input devices."""
    if sd is None:
        return []
    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0] if sd.default.device else None
        result = []
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                result.append({
                    "id": i,
                    "name": d.get("name", f"Microphone {i}"),
                    "channels": d.get("max_input_channels", 1),
                    "default_samplerate": int(d.get("default_samplerate", 16000)),
                    "is_default": (i == default_input)
                })
        return result
    except Exception as exc:
        MICROPHONE_STATE["last_error"] = str(exc)
        return []


def get_voice_status() -> Dict[str, Any]:
    """Returns the current state and capabilities of the local voice system."""
    dev_list = list_audio_input_devices()
    has_mic = len(dev_list) > 0

    engine_info = "faster-whisper small (INT8/FP16 local)"
    if _WHISPER_MODEL_INSTANCE is not None:
        dev_name = getattr(_WHISPER_MODEL_INSTANCE.model, "device", "cpu")
        engine_info = f"faster-whisper small ({dev_name.upper()})"

    status_text = "Voice Ready"
    if MICROPHONE_STATE["transcribing"]:
        status_text = "Transcribing audio…"
    elif MICROPHONE_STATE["listening"]:
        status_text = "Recording audio… (Click Stop when finished)"

    return {
        "voice_enabled": True,
        "mic_available": has_mic,
        "tts_available": True,
        "stt_available": True,
        "stt_engine": engine_info,
        "tts_engine": "Windows Native SpeechSynthesis (SAPI)",
        "is_listening": MICROPHONE_STATE["listening"],
        "is_transcribing": MICROPHONE_STATE["transcribing"],
        "status": status_text,
        "supported_languages": SUPPORTED_LANGUAGES,
        "selected_language": MICROPHONE_STATE["selected_language"],
        "devices": dev_list,
    }


def speak_text(text: str) -> bool:
    """Uses local Windows speech engine to speak text offline without cloud APIs."""
    global ACTIVE_SPEECH_PROC
    if not text:
        return False
    stop_speaking()
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(text)
        return True
    except Exception:
        # Robust PowerShell SAPI fallback
        clean_text = text.replace('"', '\"').replace("'", "")[:500]
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak('{clean_text}'); $synth.Dispose()"
        ]
        try:
            ACTIVE_SPEECH_PROC = subprocess.Popen(cmd)
            return True
        except Exception:
            return False


def stop_speaking():
    """Immediately stops any ongoing speech synthesis."""
    global ACTIVE_SPEECH_PROC
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak("", 2)
    except Exception:
        pass

    if ACTIVE_SPEECH_PROC:
        try:
            ACTIVE_SPEECH_PROC.terminate()
        except Exception:
            pass
        ACTIVE_SPEECH_PROC = None


class AudioRecorder:
    """Thread-safe background microphone recorder using sounddevice."""

    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None):
        self.sample_rate = sample_rate
        self.device_index = device_index
        self.stream: Optional[sd.InputStream] = None
        self.chunks: List[np.ndarray] = []
        self.q = queue.Queue()
        self.is_recording = False
        self.is_cancelled = False
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if not self.is_cancelled and self.is_recording:
            self.chunks.append(indata.copy())

    def start(self) -> Tuple[bool, Optional[str]]:
        if sd is None:
            return False, "sounddevice library is not available."
        with self._lock:
            try:
                self.chunks.clear()
                self.is_recording = True
                self.is_cancelled = False

                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    device=self.device_index,
                    callback=self._callback
                )
                self.stream.start()
                return True, None
            except Exception as exc:
                self.is_recording = False
                err_str = str(exc)
                if "device" in err_str.lower() or "permission" in err_str.lower() or "unanticipated" in err_str.lower():
                    return False, "Microphone unavailable. Check Windows microphone permissions and default input device."
                return False, f"Failed to open microphone: {err_str}"

    def stop(self) -> Optional[np.ndarray]:
        with self._lock:
            self.is_recording = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            if self.is_cancelled or not self.chunks:
                return None

            try:
                data = np.concatenate(self.chunks, axis=0).flatten()
                return data
            except Exception:
                return None

    def cancel(self):
        with self._lock:
            self.is_cancelled = True
            self.is_recording = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            self.chunks.clear()


def preprocess_audio(audio: np.ndarray, sample_rate: int = 16000) -> Tuple[bool, Optional[np.ndarray], Optional[str]]:
    """
    Applies audio normalization, DC offset removal, silence detection, and noise checks.
    Returns (ok, normalized_audio, error_message).
    """
    if audio is None or len(audio) == 0:
        return False, None, "No speech detected. Please speak into the microphone."

    # Minimum length: 0.3 seconds
    duration = len(audio) / sample_rate
    if duration < 0.3:
        return False, None, "Recording was too short. No speech detected."

    # 1. Remove DC offset
    audio = audio - np.mean(audio)

    # 2. Check RMS energy & Peak amplitude
    rms = np.sqrt(np.mean(audio ** 2))
    peak = np.max(np.abs(audio))

    if rms < 0.002 or peak < 0.008:
        return False, None, "No speech detected. Please speak closer to the microphone."

    # 3. Peak normalization to 0.95
    if peak > 0:
        audio = (audio / peak) * 0.95

    return True, audio.astype(np.float32), None


def transcribe_numpy_audio(
    audio: np.ndarray,
    language: Optional[str] = "auto",
    beam_size: int = 5
) -> Dict[str, Any]:
    """
    Transcribes audio numpy array using the local faster-whisper small model.
    Supports English, Hindi, Marathi, and mixed speech.
    """
    ok, clean_audio, err = preprocess_audio(audio)
    if not ok:
        return {"ok": False, "error": err, "text": None}

    try:
        model = get_whisper_model()
    except Exception as exc:
        return {"ok": False, "error": f"Speech model error: {exc}", "text": None}

    lang_param = None if (not language or language == "auto") else language

    try:
        # VAD filtering with fine-tuned parameters + beam search
        vad_params = dict(
            min_silence_duration_ms=400,
            speech_pad_ms=250
        )

        segments, info = model.transcribe(
            clean_audio,
            language=lang_param,
            task="transcribe",
            beam_size=beam_size,
            vad_filter=True,
            vad_parameters=vad_params,
            temperature=[0.0, 0.2, 0.4]
        )

        tokens = []
        for segment in segments:
            if segment.text:
                tokens.append(segment.text.strip())

        transcribed_text = " ".join(tokens).strip()

        if not transcribed_text:
            return {"ok": False, "error": "No speech detected. Please speak clearly into your microphone.", "text": None}

        detected_lang = getattr(info, "language", language or "en")
        lang_prob = getattr(info, "language_probability", 1.0)

        return {
            "ok": True,
            "text": transcribed_text,
            "language": detected_lang,
            "confidence": lang_prob,
            "error": None
        }

    except Exception as exc:
        global _WHISPER_MODEL_INSTANCE
        if _WHISPER_MODEL_INSTANCE and getattr(_WHISPER_MODEL_INSTANCE.model, "device", "") == "cuda":
            try:
                local_path = _find_local_model_path()
                model_source = local_path if local_path else "small"
                _WHISPER_MODEL_INSTANCE = faster_whisper.WhisperModel(
                    model_source,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(WHISPER_CACHE_DIR),
                    local_files_only=bool(local_path)
                )
                return transcribe_numpy_audio(clean_audio, language=language, beam_size=beam_size)
            except Exception as cpu_exc:
                return {"ok": False, "error": f"Transcription error: {cpu_exc}", "text": None}
        return {"ok": False, "error": f"Transcription error: {exc}", "text": None}


def start_listening(device_index: Optional[int] = None, language: str = "auto") -> Dict[str, Any]:
    """Starts microphone recording in the background."""
    global ACTIVE_RECORDER
    with _RECORDING_LOCK:
        if ACTIVE_RECORDER and ACTIVE_RECORDER.is_recording:
            return {"status": "already_recording", "message": "Microphone is already active."}

        stop_speaking()
        recorder = AudioRecorder(sample_rate=16000, device_index=device_index)
        ok, err = recorder.start()
        if not ok:
            MICROPHONE_STATE["listening"] = False
            MICROPHONE_STATE["last_error"] = err
            return {"status": "error", "message": err}

        ACTIVE_RECORDER = recorder
        MICROPHONE_STATE["listening"] = True
        MICROPHONE_STATE["transcribing"] = False
        MICROPHONE_STATE["selected_language"] = language
        MICROPHONE_STATE["selected_device"] = device_index
        MICROPHONE_STATE["last_error"] = None
        return {"status": "listening", "message": "Microphone active. Speak clearly into the microphone."}


def stop_listening_and_transcribe(language: Optional[str] = None) -> Dict[str, Any]:
    """Stops microphone recording and runs faster-whisper transcription."""
    global ACTIVE_RECORDER
    with _RECORDING_LOCK:
        recorder = ACTIVE_RECORDER
        ACTIVE_RECORDER = None
        MICROPHONE_STATE["listening"] = False

    if not recorder:
        return {"ok": False, "error": "No active recording found.", "text": None}

    MICROPHONE_STATE["transcribing"] = True
    try:
        audio = recorder.stop()
        if audio is None or len(audio) == 0:
            return {"ok": False, "error": "No speech recorded.", "text": None}

        lang = language or MICROPHONE_STATE["selected_language"]
        result = transcribe_numpy_audio(audio, language=lang)
        return result
    finally:
        MICROPHONE_STATE["transcribing"] = False


def cancel_listening() -> Dict[str, Any]:
    """Immediately aborts recording, discards audio buffer, and resets state."""
    global ACTIVE_RECORDER
    with _RECORDING_LOCK:
        if ACTIVE_RECORDER:
            ACTIVE_RECORDER.cancel()
            ACTIVE_RECORDER = None
    MICROPHONE_STATE["listening"] = False
    MICROPHONE_STATE["transcribing"] = False
    return {"status": "cancelled", "message": "Recording cancelled."}


def stop_listening() -> Dict[str, Any]:
    """Compatibility wrapper that stops recording."""
    global ACTIVE_RECORDER
    with _RECORDING_LOCK:
        if ACTIVE_RECORDER:
            ACTIVE_RECORDER.stop()
            ACTIVE_RECORDER = None
    MICROPHONE_STATE["listening"] = False
    MICROPHONE_STATE["transcribing"] = False
    return {"status": "idle", "message": "Microphone stopped."}


def listen_and_transcribe_result(
    timeout_seconds: int = 7,
    language: str = "auto",
    device_index: Optional[int] = None
) -> Dict[str, Any]:
    """
    Synchronous / bounded recording and transcription.
    Records for up to timeout_seconds (or until stopped) and transcribes with faster-whisper small.
    """
    res = start_listening(device_index=device_index, language=language)
    if res.get("status") == "error":
        return {"ok": False, "error": res.get("message", "Microphone error"), "text": None}

    recorder = ACTIVE_RECORDER
    t_start = time.time()
    try:
        while time.time() - t_start < timeout_seconds:
            if not MICROPHONE_STATE["listening"] or (recorder and not recorder.is_recording):
                break
            time.sleep(0.1)

        return stop_listening_and_transcribe(language=language)
    except Exception as exc:
        cancel_listening()
        return {"ok": False, "error": f"Voice recording failed: {exc}", "text": None}


def listen_and_transcribe(timeout_seconds: int = 7) -> Optional[str]:
    """Backward-compatible helper returning recognized text string or None."""
    res = listen_and_transcribe_result(timeout_seconds=timeout_seconds)
    return res.get("text") if res.get("ok") else None
