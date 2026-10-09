"""
Infinity AI - Local OCR & Vision Subsystem
Provides local OCR extraction (via pytesseract / PyMuPDF) and local vision model support.
Handles screenshots, scanned documents, diagrams, charts, and image Q&A.
Gracefully explains and falls back if a vision model is not installed.
"""

import base64
import io
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

import pymupdf
from PIL import Image

try:
    import pytesseract
except Exception:
    pytesseract = None

from backend.ai_engine import client, check_ollama, STOP_EVENT
from backend.model_manager import get_all_models


def is_ocr_available() -> bool:
    """Checks if Tesseract OCR is available on the machine."""
    if pytesseract is None:
        return False
    try:
        # Test with a tiny blank image
        img = Image.new("RGB", (30, 30), color="white")
        pytesseract.image_to_string(img)
        return True
    except Exception:
        return False


def ocr_image(image_path_or_bytes) -> str:
    """Extract text from an image file path or raw bytes using OCR."""
    if not is_ocr_available():
        return "[OCR is not available. Please ensure Tesseract OCR is installed on Windows.]"
    try:
        if isinstance(image_path_or_bytes, (str, Path)):
            img = Image.open(str(image_path_or_bytes))
        else:
            img = Image.open(io.BytesIO(image_path_or_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip() or "[No text detected in image.]"
    except Exception as exc:
        return f"[OCR error: {exc}]"


def get_available_vision_model() -> Optional[str]:
    """Detect if an Ollama vision model is currently installed and ready."""
    try:
        catalogue = get_all_models()
        v_preset = catalogue.get("presets", {}).get("Vision")
        if v_preset:
            return v_preset
        # Check running models
        res = client.list()
        raw_list = res.get("models", []) if isinstance(res, dict) else getattr(res, "models", [])
        for m in raw_list:
            name = m.get("name", "") if isinstance(m, dict) else getattr(m, "model", "")
            lower = name.lower()
            if any(term in lower for term in ["llava", "vision", "moondream", "bakllava", "minicpm-v", "gemma3"]):
                return name
    except Exception:
        pass
    return None


def encode_image_to_base64(image_path: str) -> str:
    """Converts an image file to base64 string for multimodal LLM APIs."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image_with_vision(
    image_path: str,
    prompt: str = "Describe this image in detail and transcribe any visible text or diagrams.",
    chunk_callback=None
) -> str:
    """
    Analyzes an image using a local vision model if available,
    or falls back to OCR + text-based reasoning.
    """
    vision_model = get_available_vision_model()
    
    # 1. Vision Model Path
    if vision_model:
        try:
            b64_img = encode_image_to_base64(image_path)
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64_img]
                }
            ]
            response = client.chat(
                model=vision_model,
                messages=messages,
                stream=True
            )
            output = []
            for chunk in response:
                if STOP_EVENT.is_set():
                    break
                token = chunk.get("message", {}).get("content", "") if isinstance(chunk, dict) else getattr(getattr(chunk, "message", None), "content", "")
                if token:
                    output.append(token)
                    if chunk_callback:
                        chunk_callback(token)
            return "".join(output)
        except Exception as exc:
            pass # Fallback to OCR

    # 2. Fallback Path: OCR + Text LLM
    ocr_result = ocr_image(image_path)
    fallback_prompt = (
        f"The user attached an image ({Path(image_path).name}).\n"
        f"Note: A native local vision model (e.g. llava/moondream) is not currently installed.\n"
        f"Extracted OCR Text from the image:\n```\n{ocr_result}\n```\n\n"
        f"User Question: {prompt}\n\n"
        f"Please answer based on the extracted text from the image, and note that installing a vision model with 'ollama pull moondream' or 'ollama pull llava' will enable rich visual diagram and chart understanding."
    )
    from backend.ai_engine import generate_simple_response
    return generate_simple_response(fallback_prompt, chunk_callback=chunk_callback)
