import hashlib
import hmac
import json
import os
import platform
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

AUTHORIZED_FILE_NAME = ".infinity-ai-authorized"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCAL_DEVICE_AUTH_FILE = LOCAL_DATA_DIR / ".device_auth.json"
WORKSPACE_IDENTITY_FILE = LOCAL_DATA_DIR / ".workspace_identity.json"
QUARANTINE_LOG_FILE = LOCAL_DATA_DIR / ".quarantine_log.json"

# In-memory session and lock state
_ACTIVE_SESSION_TOKEN: Optional[str] = None
_WORKSPACE_EXPLICITLY_LOCKED: bool = False
_PASSWORD_AUTHENTICATED: bool = False


def is_running_on_removable_media() -> tuple:
    """
    Checks if the application workspace is physically installed on removable media (DriveType == 2).
    Returns (is_removable: bool, diagnostic_message: str).
    """
    try:
        drive_letter = os.path.splitdrive(str(PROJECT_ROOT))[0].rstrip("\\")
        drives = get_system_drives()
        for d in drives:
            dev = d.get("DeviceID", "").rstrip("\\")
            if dev.upper() == drive_letter.upper():
                dtype = int(d.get("DriveType", 0))
                if dtype == 2:
                    msg = (
                        f"Infinity AI is currently installed on a removable drive ({drive_letter}). "
                        "For normal secure deployment, install the application on a fixed internal drive "
                        "(e.g., C:\\PrivateAI) and use a separate USB as the authorization key."
                    )
                    return True, msg
    except Exception:
        pass
    return False, ""


def get_or_create_workspace_identity() -> Dict[str, Any]:
    """
    Retrieves or initializes the unique local workspace identity for this laptop.
    Stored locally in app/data/.workspace_identity.json.
    NEVER stored or synchronized on USB.
    """
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_dev = get_device_id()

    if WORKSPACE_IDENTITY_FILE.exists():
        try:
            with open(WORKSPACE_IDENTITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("device_id") == current_dev:
                return data
            else:
                data["is_mismatch"] = True
                data["current_device_id"] = current_dev
                return data
        except Exception:
            pass

    ws_id = f"ws-{uuid.uuid4()}"
    identity = {
        "workspace_id": ws_id,
        "device_id": current_dev,
        "host_node": platform.node(),
        "created_at": subprocess.check_output(["powershell", "-NoProfile", "-Command", "Get-Date -Format o"], text=True).strip() if os.name == "nt" else "2026-10-05T00:00:00Z",
        "schema_version": 1
    }
    with open(WORKSPACE_IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identity, f, indent=2)
    return identity


def get_workspace_id() -> str:
    """Returns the stable local workspace ID for this laptop."""
    ident = get_or_create_workspace_identity()
    return ident.get("workspace_id", "default-workspace")


def is_workspace_identity_matching() -> bool:
    """Verifies that the workspace identity on disk matches the current physical device."""
    ident = get_or_create_workspace_identity()
    return not ident.get("is_mismatch", False)


def get_device_id() -> str:
    """
    Computes a deterministic, tamper-resistant hardware identifier for the local laptop.
    Uses Windows Machine GUID and CPU/node identity.
    """
    guid = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
    except Exception:
        guid = platform.node()

    raw_ident = f"{guid}:{platform.node()}:{platform.machine()}"
    return hashlib.sha256(raw_ident.encode("utf-8")).hexdigest()[:32]


def get_device_auth_record() -> Optional[Dict[str, Any]]:
    """Reads local laptop workspace authorization record. Stored on laptop only."""
    if not LOCAL_DEVICE_AUTH_FILE.exists():
        return None
    try:
        with open(LOCAL_DEVICE_AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("device_id") == get_device_id() and data.get("authorized"):
            return data
    except Exception:
        pass
    return None


def is_device_authorized() -> bool:
    """Checks if this specific laptop has been authorized as a trusted Infinity AI workspace."""
    return get_device_auth_record() is not None


def authorize_device(auth_key_id: str) -> Dict[str, Any]:
    """
    Authorizes this specific laptop host.
    Creates a private local workspace credential on the laptop.
    NEVER writes this credential to the USB.
    """
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dev_id = get_device_id()
    record = {
        "device_id": dev_id,
        "authorized": True,
        "auth_key_id": auth_key_id,
        "host_node": platform.node(),
        "created_at": subprocess.check_output(["powershell", "-NoProfile", "-Command", "Get-Date -Format o"], text=True).strip() if os.name == "nt" else "2026-10-05T00:00:00Z"
    }
    with open(LOCAL_DEVICE_AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return record


def deauthorize_device() -> bool:
    """Revokes local computer authorization."""
    if LOCAL_DEVICE_AUTH_FILE.exists():
        try:
            LOCAL_DEVICE_AUTH_FILE.unlink()
            return True
        except Exception:
            return False
    return True


_CLEANLINESS_AUDIT_CACHE: Dict[str, Any] = {}

def audit_usb_cleanliness(drive_id: str) -> Dict[str, Any]:
    """
    CRITICAL PRIVACY AUDIT:
    Verifies that the USB device is STRICTLY a security key and does NOT contain:
    - SQLite databases (*.db, *.sqlite)
    - ChromaDB vector stores
    - Conversation logs / chat exports
    - Project documents / personal user files
    """
    global _CLEANLINESS_AUDIT_CACHE
    drive_str = str(drive_id).rstrip("\\") + "\\"
    now = time.time()
    cached = _CLEANLINESS_AUDIT_CACHE.get(drive_str)
    if cached and (now - cached.get("ts", 0)) < 15.0:
        return cached["result"]

    drive_path = Path(drive_str)
    violations = []

    if drive_path.exists():
        try:
            with os.scandir(str(drive_path)) as it:
                for entry in it:
                    name = entry.name.lower()
                    if name == AUTHORIZED_FILE_NAME.lower():
                        continue
                    if entry.is_file() and name.endswith((".db", ".sqlite", ".db-wal", ".db-shm")):
                        violations.append(f"Forbidden database found on USB: {entry.name}")
                    elif entry.is_dir() and "chroma" in name:
                        violations.append(f"Forbidden ChromaDB store found on USB: {entry.name}")
                    elif entry.is_dir() and name in ["chat_history", "conversations", "private_workspace"]:
                        violations.append(f"Forbidden chat store found on USB: {entry.name}")
        except Exception:
            pass

    res = {
        "is_clean": len(violations) == 0,
        "violations": violations
    }
    _CLEANLINESS_AUDIT_CACHE[drive_str] = {"ts": now, "result": res}
    return res


def lock_workspace():
    """Explicitly locks the private workspace and invalidates active session tokens."""
    global _WORKSPACE_EXPLICITLY_LOCKED, _ACTIVE_SESSION_TOKEN, _PASSWORD_AUTHENTICATED
    _WORKSPACE_EXPLICITLY_LOCKED = True
    _ACTIVE_SESSION_TOKEN = None
    _PASSWORD_AUTHENTICATED = False


def unlock_workspace(session_token: Optional[str] = None):
    """Unlocks the private workspace when an authorized USB is verified and password is valid."""
    global _WORKSPACE_EXPLICITLY_LOCKED, _ACTIVE_SESSION_TOKEN, _PASSWORD_AUTHENTICATED
    _WORKSPACE_EXPLICITLY_LOCKED = False
    _PASSWORD_AUTHENTICATED = True
    _ACTIVE_SESSION_TOKEN = session_token or str(uuid.uuid4())


def is_workspace_locked() -> bool:
    """Returns True if the private workspace is currently locked."""
    global _WORKSPACE_EXPLICITLY_LOCKED, _PASSWORD_AUTHENTICATED
    if _WORKSPACE_EXPLICITLY_LOCKED:
        return True
    try:
        from backend.password_auth import password_auth_service
        if password_auth_service.is_password_configured() and not _PASSWORD_AUTHENTICATED:
            return True
    except Exception:
        pass
    return False


def is_password_authenticated() -> bool:
    """Returns True if password has been verified for the current RAM session."""
    global _PASSWORD_AUTHENTICATED
    return _PASSWORD_AUTHENTICATED


def set_password_authenticated(authenticated: bool):
    """Sets in-memory password authentication state and session token."""
    global _PASSWORD_AUTHENTICATED, _ACTIVE_SESSION_TOKEN
    _PASSWORD_AUTHENTICATED = authenticated
    if authenticated and not _ACTIVE_SESSION_TOKEN:
        _ACTIVE_SESSION_TOKEN = str(uuid.uuid4())
    elif not authenticated:
        _ACTIVE_SESSION_TOKEN = None


def get_security_state() -> str:
    """
    Returns explicit security state string:
    LOCKED, PASSWORD_REQUIRED, UNLOCKED, LOCKOUT
    Password-only local authentication state machine.
    """
    try:
        from backend.password_auth import password_auth_service
        is_locked, _ = password_auth_service.is_locked_out()
        if is_locked:
            return "LOCKOUT"
        if not password_auth_service.is_password_configured():
            return "PASSWORD_REQUIRED"
        if _WORKSPACE_EXPLICITLY_LOCKED or not _PASSWORD_AUTHENTICATED:
            return "PASSWORD_REQUIRED"
    except Exception:
        pass
    return "UNLOCKED"


def get_session_token() -> Optional[str]:
    """Returns the current active cryptographic session token if unlocked."""
    global _ACTIVE_SESSION_TOKEN
    return _ACTIVE_SESSION_TOKEN


def invalidate_session():
    """Purges session credentials upon USB detachment."""
    global _ACTIVE_SESSION_TOKEN, _PASSWORD_AUTHENTICATED
    _ACTIVE_SESSION_TOKEN = None
    _PASSWORD_AUTHENTICATED = False


def get_system_drives() -> List[Dict[str, Any]]:
    """Query all logical drives and their drive types via ultra-fast native Windows API with fallback."""
    drives = []
    try:
        import ctypes
        import string
        kernel32 = ctypes.windll.kernel32
        bitmask = kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                root = f"{letter}:\\"
                dtype = kernel32.GetDriveTypeW(root)
                vol_name = ctypes.create_unicode_buffer(260)
                serial = ctypes.c_ulong(0)
                try:
                    kernel32.GetVolumeInformationW(root, vol_name, 260, ctypes.byref(serial), None, None, None, 0)
                    v_name = vol_name.value
                    s_num = hex(serial.value)
                except Exception:
                    v_name = "Drive"
                    s_num = "UNKNOWN"
                drives.append({
                    "DeviceID": f"{letter}:",
                    "DriveType": dtype,
                    "VolumeName": v_name,
                    "SerialNumber": s_num
                })
            bitmask >>= 1
        if drives:
            return drives
    except Exception:
        pass

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-WmiObject Win32_LogicalDisk | Select-Object DeviceID, DriveType, VolumeName, SerialNumber, Size | ConvertTo-Json"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                drives.append(data)
            elif isinstance(data, list):
                drives.extend(data)
    except Exception:
        # Fallback inspection
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                drives.append({
                    "DeviceID": f"{letter}:",
                    "DriveType": 2 if letter in "DEF" else 3,
                    "VolumeName": "Drive",
                    "SerialNumber": "UNKNOWN"
                })
    return drives


def classify_drive(drive_info: Dict[str, Any], project_drive: str) -> Dict[str, Any]:
    """
    Evaluates a drive and classifies it into:
    - 'fixed_disk': Non-removable media (DriveType != 2)
    - 'project_drive': The drive hosting the project itself (cannot act as external key)
    - 'unauthorized_removable': Removable media without a valid authorization key
    - 'authorized_removable': Removable media containing valid .infinity-ai-authorized
    """
    dev_id = drive_info.get("DeviceID", "").rstrip("\\")
    drive_type = int(drive_info.get("DriveType", 0))

    if drive_type != 2:
        return {"classification": "fixed_disk", "authorized": False, "drive": dev_id}

    # If this drive is the project drive itself, by design it cannot be its own separate authorization USB
    if dev_id.upper() == project_drive.upper():
        return {
            "classification": "project_drive",
            "authorized": False,
            "drive": dev_id,
            "reason": "Project drive cannot serve as its own separate authorization key."
        }

    # Check for marker on the separate removable drive
    marker_path = Path(f"{dev_id}\\") / AUTHORIZED_FILE_NAME
    if not marker_path.exists():
        return {"classification": "unauthorized_removable", "authorized": False, "drive": dev_id}

    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("project_name") == "Infinity AI" and meta.get("status") == "authorized":
            return {
                "classification": "authorized_removable",
                "authorized": True,
                "drive": dev_id,
                "metadata": meta
            }
        else:
            return {"classification": "invalid_marker", "authorized": False, "drive": dev_id}
    except Exception:
        return {"classification": "corrupt_marker", "authorized": False, "drive": dev_id}


def verify_usb_authorization(override_drives: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Compatibility stub. Infinity AI now uses PASSWORD-ONLY local authentication.
    USB/Pendrive has no role in workspace security or authentication.
    """
    return {
        "authorized": True,
        "read_only": False,
        "is_locked": is_workspace_locked(),
        "needs_device_setup": False,
        "password_configured": True,
        "password_authenticated": _PASSWORD_AUTHENTICATED,
        "session_token": _ACTIVE_SESSION_TOKEN,
        "message": "Password-only local workspace authentication.",
        "device": None
    }


def is_write_authorized() -> bool:
    """Quick check if protected write operations are authorized (workspace is unlocked)."""
    return not is_workspace_locked()


def check_protected_action(action_name: str) -> None:
    """Raises PermissionError if protected file modification is attempted while workspace is locked."""
    if is_workspace_locked():
        raise PermissionError(f"Action '{action_name}' blocked: Workspace is locked. Password authentication required.")

