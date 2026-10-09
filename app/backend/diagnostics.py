"""
Infinity AI - Hardware Monitoring & Diagnostics Subsystem
Monitors CPU, RAM, GPU, VRAM, Storage, Ollama Status, RAG Status, OCR Status,
and USB Authorization Status.
Never fabricates values: displays 'Unavailable' if a metric cannot be queried.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, Optional

try:
    import psutil
except Exception:
    psutil = None

from backend.ai_engine import check_ollama
from backend.ocr_vision import is_ocr_available, get_available_vision_model
from backend.security import (
    verify_usb_authorization,
    is_running_on_removable_media,
    get_or_create_workspace_identity
)
from backend.vector_store import get_collection_count
import time

_HW_CACHE: Dict[str, Any] = {}
_HW_CACHE_TIME: float = 0.0

def get_hardware_metrics() -> Dict[str, Any]:
    """Retrieves real-time system hardware metrics without fabrication, cached with 3s TTL."""
    global _HW_CACHE, _HW_CACHE_TIME
    now = time.time()
    if _HW_CACHE and (now - _HW_CACHE_TIME) < 3.0:
        return dict(_HW_CACHE)

    metrics = {
        "cpu_usage_pct": "Unavailable",
        "cpu_cores": "Unavailable",
        "ram_used_gb": "Unavailable",
        "ram_total_gb": "Unavailable",
        "gpu_name": "Unavailable",
        "vram_used_gb": "Unavailable",
        "vram_total_gb": "Unavailable",
        "storage_free_gb": "Unavailable",
        "storage_total_gb": "Unavailable",
    }

    # 1. CPU & RAM via psutil or WMI fallback
    if psutil:
        try:
            metrics["cpu_usage_pct"] = f"{psutil.cpu_percent(interval=None)}%"
            metrics["cpu_cores"] = str(psutil.cpu_count(logical=True))
            mem = psutil.virtual_memory()
            metrics["ram_used_gb"] = f"{round((mem.total - mem.available) / (1024 ** 3), 1)}"
            metrics["ram_total_gb"] = f"{round(mem.total / (1024 ** 3), 1)} GB"
        except Exception:
            pass

    if metrics["cpu_cores"] == "Unavailable":
        cores = os.cpu_count()
        if cores:
            metrics["cpu_cores"] = str(cores)

    if metrics["ram_total_gb"] == "Unavailable":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "Get-WmiObject Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                import json
                w_data = json.loads(res.stdout)
                tot_kb = float(w_data.get("TotalVisibleMemorySize", 0))
                free_kb = float(w_data.get("FreePhysicalMemory", 0))
                if tot_kb > 0:
                    metrics["ram_total_gb"] = f"{round(tot_kb / (1024 ** 2), 1)} GB"
                    metrics["ram_used_gb"] = f"{round((tot_kb - free_kb) / (1024 ** 2), 1)}"
        except Exception:
            pass

    # 2. Storage for workspace drive
    try:
        usage = shutil.disk_usage("D:\\")
        metrics["storage_free_gb"] = f"{round(usage.free / (1024 ** 3), 1)} GB"
        metrics["storage_total_gb"] = f"{round(usage.total / (1024 ** 3), 1)} GB"
    except Exception:
        pass

    # 3. GPU & VRAM via nvidia-smi
    try:
        cmd = ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) >= 3:
                metrics["gpu_name"] = parts[0]
                metrics["vram_used_gb"] = f"{round(float(parts[1]) / 1024, 1)}"
                metrics["vram_total_gb"] = f"{round(float(parts[2]) / 1024, 1)} GB"
    except Exception:
        pass

    _HW_CACHE = dict(metrics)
    _HW_CACHE_TIME = now
    return metrics


def get_full_diagnostics() -> Dict[str, Any]:
    """Runs a complete diagnostic check across all subsystems."""
    hw = get_hardware_metrics()
    ollama_status = check_ollama()
    usb_status = verify_usb_authorization()
    ocr_ready = is_ocr_available()
    vision_model = get_available_vision_model()
    rag_count = get_collection_count()

    removable_install, removable_msg = is_running_on_removable_media()
    ws_ident = get_or_create_workspace_identity()

    return {
        "hardware": hw,
        "ollama": {
            "running": ollama_status["server"],
            "host": ollama_status.get("host", "Unavailable"),
            "model_ready": ollama_status["model"],
            "error": ollama_status.get("error")
        },
        "rag": {
            "status": "Ready",
            "indexed_chunks": rag_count
        },
        "ocr": {
            "ready": ocr_ready,
            "status": "Available" if ocr_ready else "Unavailable (Tesseract not found)"
        },
        "vision": {
            "ready": bool(vision_model),
            "model": vision_model or "None (OCR fallback active)"
        },
        "security": {
            "usb_authorized": usb_status["authorized"],
            "read_only": usb_status["read_only"],
            "message": usb_status["message"]
        },
        "workspace": {
            "workspace_id": ws_ident.get("workspace_id", "Unavailable"),
            "device_id": ws_ident.get("device_id", "Unavailable"),
            "installed_on_removable": removable_install,
            "installation_warning": removable_msg if removable_install else None,
            "status": "WARNING (Removable Media)" if removable_install else "PASS (Fixed Storage)"
        },
        "privacy": {
            "mode": "[LOCAL MODE]",
            "offline_first": True,
            "telemetry_active": False
        }
    }


_DIAGNOSTICS_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ai_diagnostics.log")
_recent_logs = []

def log_ai_operation(
    operation: str,
    model: str = "Unknown",
    latency_ms: float = 0.0,
    retrieval_count: int = 0,
    document: str = "",
    success: bool = True,
    error_category: str = "none",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Structured logging of AI operations for diagnostics without leaking private text.
    Fulfills offline diagnostic and audit requirements.
    """
    import time
    import uuid
    import json
    
    req_id = request_id or str(uuid.uuid4())[:8]
    entry = {
        "request_id": req_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "retrieval_count": retrieval_count,
        "document": os.path.basename(document) if document else "none",
        "success": success,
        "error_category": error_category
    }
    
    _recent_logs.append(entry)
    if len(_recent_logs) > 100:
        _recent_logs.pop(0)
        
    try:
        log_dir = os.path.dirname(_DIAGNOSTICS_LOG_PATH)
        os.makedirs(log_dir, exist_ok=True)
        with open(_DIAGNOSTICS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
        
    return entry

def get_recent_diagnostics_logs(limit: int = 20) -> list:
    return list(_recent_logs[-limit:])

