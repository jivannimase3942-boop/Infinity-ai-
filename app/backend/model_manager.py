"""
Infinity AI - Local Model Manager
Detects Ollama models and local GGUF models in D:\\models and D:\\PrivateAI\\models.
Categorizes into Fast, Balanced, Advanced, Vision, Coding, and Embedding presets.
Shows RAM/VRAM requirements, capabilities, and health status without duplicating models.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional

import ollama
from backend.ai_engine import OLLAMA_HOST, client

EXTERNAL_MODELS_DIR = Path("D:/models")
INTERNAL_MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


def get_gguf_models() -> List[Dict[str, Any]]:
    """Scan D:\\models and D:\\PrivateAI\\models for GGUF files without moving them."""
    found = []
    search_dirs = [EXTERNAL_MODELS_DIR, INTERNAL_MODELS_DIR]
    
    for s_dir in search_dirs:
        if s_dir.exists():
            try:
                for item in s_dir.glob("*.gguf"):
                    size_bytes = item.stat().st_size
                    size_gb = round(size_bytes / (1024 ** 3), 2)
                    name = item.stem
                    
                    # Estimate requirements based on file size
                    est_ram = round(size_gb * 1.2 + 0.5, 1)
                    
                    # Infer capabilities from name
                    lower_name = name.lower()
                    capabilities = ["Text Generation", "Offline Chat"]
                    if "code" in lower_name or "coder" in lower_name:
                        capabilities.append("Coding")
                    if "vision" in lower_name or "vl" in lower_name:
                        capabilities.append("Vision")
                    if "dolphin" in lower_name:
                        capabilities.append("Uncensored Reasoning")
                    if "gemma" in lower_name:
                        capabilities.append("Balanced Reasoning")
                        
                    found.append({
                        "name": item.name,
                        "display_name": f"{name} (GGUF)",
                        "provider": "llama.cpp / GGUF",
                        "format": "GGUF",
                        "path": str(item),
                        "size_gb": size_gb,
                        "ram_required_gb": est_ram,
                        "context_length": 4096,
                        "capabilities": capabilities,
                        "status": "Available on disk",
                        "is_ollama": False,
                    })
            except Exception:
                continue
    return found


def get_ollama_models() -> List[Dict[str, Any]]:
    """Detect models served by the local Ollama instance."""
    models = []
    try:
        res = client.list()
        raw_list = res.get("models", []) if isinstance(res, dict) else getattr(res, "models", [])
        for m in raw_list:
            if isinstance(m, dict):
                m_name = m.get("name", "")
                m_size = m.get("size", 0)
                details = m.get("details", {})
            else:
                m_name = getattr(m, "model", "") or getattr(m, "name", "")
                m_size = getattr(m, "size", 0)
                details = getattr(m, "details", {})
                if not isinstance(details, dict):
                    details = {
                        "family": getattr(details, "family", ""),
                        "parameter_size": getattr(details, "parameter_size", ""),
                        "quantization_level": getattr(details, "quantization_level", "")
                    }
                    
            size_gb = round(m_size / (1024 ** 3), 2) if m_size else 1.0
            lower = m_name.lower()
            
            capabilities = ["Chat", "Local RAG", "Streaming"]
            if "vision" in lower or "llava" in lower or "moondream" in lower or "gemma3" in lower:
                capabilities.append("Vision / Multimodal")
            if "code" in lower or "coder" in lower:
                capabilities.append("Code Synthesis")
            if "qwen" in lower or "dolphin" in lower:
                capabilities.append("Instruction Following")
                
            models.append({
                "name": m_name,
                "display_name": m_name,
                "provider": "Ollama",
                "format": "Ollama / GGUF",
                "path": f"ollama://{m_name}",
                "size_gb": size_gb,
                "ram_required_gb": round(size_gb * 1.1 + 0.3, 1),
                "context_length": 4096 if "1.5b" in lower else 8192,
                "capabilities": capabilities,
                "status": "Ready",
                "is_ollama": True,
            })
    except Exception:
        pass
    return models


def get_all_models() -> Dict[str, Any]:
    """Returns a unified catalogue of both Ollama and GGUF models."""
    ollama_list = get_ollama_models()
    gguf_list = get_gguf_models()
    
    # Sort Ollama models by size ascending so fast model picks the lightest responsive model
    sorted_ollama = sorted(ollama_list, key=lambda x: x.get("size_gb", 100))
    all_names = [m["name"] for m in sorted_ollama]

    fast_model = None
    balanced_model = None
    advanced_model = None
    vision_model = None
    coding_model = None

    # Check Ollama models first for active serving
    for m in sorted_ollama:
        name = m["name"].lower()
        caps = [c.lower() for c in m.get("capabilities", [])]
        if "1.5b" in name or "0.5b" in name or ("qwen" in name and ("8b" in name or "7b" in name or "3b" in name)):
            if not fast_model:
                fast_model = m["name"]
        if "qwen3.5:9b" in name or "qwen3:8b" in name or "gemma3" in name or "4b" in name or "3b" in name:
            if not balanced_model:
                balanced_model = m["name"]
        if "deepseek" in name or "r1" in name or "14b" in name or "20b" in name or "dolphin" in name:
            if not advanced_model:
                advanced_model = m["name"]
        if "vision" in name or "llava" in name or "moondream" in name or any("vision" in c for c in caps):
            if not vision_model:
                vision_model = m["name"]
        if "coder" in name or "code" in name or ("qwen" in name and "8b" in name):
            if not coding_model:
                coding_model = m["name"]

    # Fallbacks if some are not matched
    if not fast_model and all_names:
        fast_model = all_names[0]
    if not balanced_model:
        balanced_model = sorted_ollama[min(1, len(sorted_ollama) - 1)]["name"] if sorted_ollama else fast_model
    if not advanced_model:
        advanced_model = sorted_ollama[-1]["name"] if sorted_ollama else balanced_model
        
    return {
        "ollama_models": ollama_list,
        "gguf_models": gguf_list,
        "total_count": len(ollama_list) + len(gguf_list),
        "presets": {
            "Fast": fast_model or "qwen2.5:1.5b",
            "Balanced": balanced_model or "dolphin-mistral:latest",
            "Advanced": advanced_model or "dolphin-mistral:latest",
            "Vision": vision_model,
            "Coding": coding_model or balanced_model or fast_model or "qwen2.5:1.5b",
            "Embedding": "all-MiniLM-L6-v2 (ONNX local)",
        }
    }
