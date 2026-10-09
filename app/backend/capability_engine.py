"""
Infinity AI - Capability Engine & Unsupported Feature Guard
Inspects user requests before routing to determine if an unsupported capability
(e.g., text-to-image generation, text-to-video generation, music generation) is requested.

Guarantees requests end in defined states (SUCCESS, UNSUPPORTED, CANCELLED, ERROR)
without leaving chat blank, permanently loading, or stuck in a streaming state.
"""

import re
from typing import Dict, Any, Optional, Tuple

IMAGE_GEN_PATTERNS = [
    r"\b(generate|create|draw|paint|make|render|produce|sketch|illustrate)\s+(me\s+)?(an?|the)?\s*(photorealistic|realistic|digital|ai|3d|hd|4k)?\s*(image|picture|photo|illustration|drawing|portrait|graphic|artwork|painting|sketch|wallpaper|diagram|logo|avatar|poster|scene)\b",
    r"\b(draw|paint|sketch|illustrate)\s+(me\s+)?(a|an|the)\b",
    r"\btext[\s\-]to[\s\-]image\b",
    r"\b(dall-?e|midjourney|stable\s*diffusion|flux(?:\.1)?|imagen|ideogram)\b",
    r"\bgenerate\s+(an?|the)?\s*image\b",
    r"\bcreate\s+(an?|the)?\s*image\b",
    r"\bmake\s+(an?|the)?\s*image\b",
    r"\bdraw\s+(an?|the)?\s*picture\b",
    r"\bgenerate\s+(an?|the)?\s*picture\b",
    r"\bcreate\s+(an?|the)?\s*picture\b",
]

# Patterns that indicate an image is being ANALYZED or DISCUSSED, NOT GENERATED
IMAGE_ANALYSIS_KEYWORDS = [
    "in this image", "in the image", "attached image", "this picture", "what is this",
    "analyze this", "read this", "ocr", "extract text", "explain this image",
    "what does this image show", "describe this image", "diagram below", "screenshot",
    "how does image", "image processing", "image compression", "jpg vs png",
    "format", "pillow", "opencv", "algorithm"
]

VIDEO_GEN_PATTERNS = [
    r"\b(generate|create|render|make)\s+(an?|the)?\s*(video|movie|clip|animation)\b",
    r"\btext[\s\-]to[\s\-]video\b",
    r"\b(sora|runway|gen-2|gen-3|pika\s*labs|kling)\b"
]

AUDIO_GEN_PATTERNS = [
    r"\b(generate|compose|create|make)\s+(an?|the)?\s*(song|music|mp3|soundtrack|audio\s*track)\b",
    r"\btext[\s\-]to[\s\-]music\b",
    r"\b(suno|udio)\b"
]


def check_unsupported_capability(prompt: str, has_image_attachment: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks if the user prompt requests an unsupported capability.
    Returns:
        (is_unsupported, capability_type, explanation_message)
    """
    if not prompt or not prompt.strip():
        return False, None, None

    clean = prompt.strip().lower()

    # If the user attached an image, they want vision inspection, not image generation
    if has_image_attachment:
        return False, None, None

    # Check if this is an image analysis query or discussion
    for kw in IMAGE_ANALYSIS_KEYWORDS:
        if kw in clean and not any(pat in clean for pat in ["generate an image", "create an image", "draw an image", "draw a picture"]):
            return False, None, None

    # 1. Image Generation Check
    is_image_gen = False
    for pat in IMAGE_GEN_PATTERNS:
        if re.search(pat, clean):
            # Guard against coding queries like "def generate_image(" or "write a function to create an image"
            if re.search(r"\b(def|class|function|python|script|code|opencv|pillow|pil)\b", clean):
                return False, None, None
            is_image_gen = True
            break

    if is_image_gen:
        explanation = (
            "### 🎨 Image Generation Not Supported\n\n"
            "Infinity AI is a local, privacy-focused offline workstation engineered for "
            "text intelligence, local document Q&A, code analysis, and visual image inspection.\n\n"
            "This installation runs completely offline on your device and **cannot generate or render images directly** "
            "(it does not include an image generation diffusion model such as Stable Diffusion or FLUX).\n\n"
            "#### 💡 How I Can Help You Instead:\n"
            "1. **Craft a Production-Ready Prompt**: I can write an ultra-detailed, stylistic prompt "
            "(including camera lens, lighting, composition, color palette, and negative prompts) "
            "ready to paste into Midjourney, DALL-E 3, or Stable Diffusion.\n"
            "2. **Analyze Existing Images**: If you attach an image or diagram using the **[+]** button, "
            "our local Vision & OCR engine can inspect, describe, or extract text from it.\n\n"
            "*Would you like me to write an optimized prompt for your image idea?*"
        )
        return True, "image_generation", explanation

    # 2. Video Generation Check
    for pat in VIDEO_GEN_PATTERNS:
        if re.search(pat, clean):
            explanation = (
                "### 🎬 Video Generation Not Supported\n\n"
                "Infinity AI does not include a local video generation model. "
                "However, I can help you write a comprehensive video script, storyboard, "
                "or generation prompt for video models like Sora or Runway."
            )
            return True, "video_generation", explanation

    # 3. Audio/Music Generation Check
    for pat in AUDIO_GEN_PATTERNS:
        if re.search(pat, clean):
            explanation = (
                "### 🎵 Music/Audio Generation Not Supported\n\n"
                "Infinity AI does not include a local music generation model. "
                "However, I can write song lyrics, chord progressions, musical structures, "
                "or descriptive prompts for music generation platforms like Suno."
            )
            return True, "audio_generation", explanation

    return False, None, None
