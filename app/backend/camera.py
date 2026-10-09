"""
Infinity AI - Local Camera & Vision Capture Subsystem
Captures images locally via native Windows APIs without external cloud dependencies.
100% offline, private, and air-gapped.
"""

import ctypes
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image

WM_CAP_START = 0x0400
WM_CAP_DRIVER_CONNECT = WM_CAP_START + 10
WM_CAP_DRIVER_DISCONNECT = WM_CAP_START + 11
WM_CAP_GRAB_FRAME = WM_CAP_START + 60
WM_CAP_FILE_SAVEDIB = WM_CAP_START + 25


def is_camera_available() -> bool:
    """Checks whether a local camera video capture driver is present."""
    try:
        avicap = ctypes.windll.avicap32
        name = ctypes.create_string_buffer(128)
        ver = ctypes.create_string_buffer(128)
        success = avicap.capGetDriverDescriptionA(0, name, 128, ver, 128)
        return bool(success)
    except Exception:
        return False


def capture_camera_frame(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Captures a single frame from the local default camera.
    Saves image to target_path or temporary PNG file.
    Returns:
        {"ok": True, "path": path, "width": w, "height": h}
        or
        {"ok": False, "error": "friendly error message"}
    """
    try:
        user32 = ctypes.windll.user32
        avicap = ctypes.windll.avicap32

        hwnd = avicap.capCreateCaptureWindowA(b"InfinityCamCapture", 0, 0, 0, 640, 480, 0, 0)
        if not hwnd:
            return {"ok": False, "error": "Could not create camera capture interface."}

        connected = user32.SendMessageA(hwnd, WM_CAP_DRIVER_CONNECT, 0, 0)
        if not connected:
            user32.DestroyWindow(hwnd)
            return {"ok": False, "error": "Camera is currently busy or unavailable. Check Windows camera permissions."}

        # Allow camera hardware sensor to adjust exposure and stream frames
        time.sleep(0.25)
        user32.SendMessageA(hwnd, WM_CAP_GRAB_FRAME, 0, 0)
        time.sleep(0.1)
        user32.SendMessageA(hwnd, WM_CAP_GRAB_FRAME, 0, 0)

        temp_bmp = os.path.join(tempfile.gettempdir(), f"infinity_cam_{int(time.time() * 1000)}.bmp")
        res = user32.SendMessageA(hwnd, WM_CAP_FILE_SAVEDIB, 0, temp_bmp.encode("utf-8"))

        user32.SendMessageA(hwnd, WM_CAP_DRIVER_DISCONNECT, 0, 0)
        user32.DestroyWindow(hwnd)

        if not os.path.exists(temp_bmp) or os.path.getsize(temp_bmp) == 0:
            return {"ok": False, "error": "No image frame was received from the camera."}

        # Convert BMP to high-quality PNG
        final_path = target_path or os.path.join(tempfile.gettempdir(), f"camera_capture_{int(time.time())}.png")
        with Image.open(temp_bmp) as im:
            rgb_im = im.convert("RGB")
            rgb_im.save(final_path, format="PNG")
            w, h = rgb_im.size

        try:
            os.remove(temp_bmp)
        except Exception:
            pass

        return {
            "ok": True,
            "path": final_path,
            "width": w,
            "height": h
        }

    except Exception as exc:
        return {"ok": False, "error": f"Camera capture failed: {str(exc)}"}


# Alias for compatibility
capture_frame = capture_camera_frame
