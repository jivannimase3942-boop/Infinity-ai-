import os
import sys
import json
import shutil
import hashlib
import sqlite3
import datetime
from pathlib import Path

ROOT = Path("D:/PrivateAI")
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = ROOT / "backups" / f"backup-2026-10-08-phase0-master_{TIMESTAMP}"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

print(f"============================================================")
print(f"INFINITY AI - PHASE 0: NON-NEGOTIABLE BACKUP & VERIFICATION")
print(f"Backup target: {BACKUP_DIR}")
print(f"============================================================")

# 1. SQLite Database integrity and counts verification
db_path = ROOT / "app" / "data" / "ai_cache.db"
assert db_path.exists(), f"DB path missing: {db_path}"

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# PRAGMA integrity_check
cur.execute("PRAGMA integrity_check;")
integrity_check = cur.fetchone()[0]
print(f"SQLite PRAGMA integrity_check: {integrity_check}")
assert integrity_check == "ok", f"Database integrity check failed: {integrity_check}"

# Verify projects count
cur.execute("SELECT COUNT(*) FROM projects;")
projects_count = cur.fetchone()[0]
print(f"Existing projects count: {projects_count}")

# Verify conversations and messages count
cur.execute("SELECT COUNT(*) FROM conversations;")
conversations_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM messages;")
messages_count = cur.fetchone()[0]
print(f"Existing conversations count: {conversations_count}")
print(f"Existing messages count: {messages_count}")

# Verify project files count
cur.execute("SELECT COUNT(*) FROM project_files;")
project_files_count = cur.fetchone()[0]
print(f"Existing project files count: {project_files_count}")

# Workspace metadata
cur.execute("SELECT * FROM workspace_metadata;")
ws_meta = [dict(zip([col[0] for col in cur.description], row)) for row in cur.fetchall()]
print(f"Workspace metadata: {ws_meta}")

conn.close()

# 2. ChromaDB verification
chroma_paths = [ROOT / "app" / "chroma_db", ROOT / "data" / "chroma", ROOT / "chroma_db"]
chroma_info = {}
for cp in chroma_paths:
    if cp.exists():
        files = list(cp.rglob("*"))
        chroma_info[str(cp)] = {
            "exists": True,
            "total_files": len(files),
            "file_names": [str(f.relative_to(cp)) for f in files if f.is_file()]
        }
    else:
        chroma_info[str(cp)] = {"exists": False}
print(f"ChromaDB inspection: {json.dumps(chroma_info, indent=2)}")

# 3. Security & Workspace Identity Files
auth_file = ROOT / ".infinity-ai-authorized"
device_auth_file = ROOT / "app" / "data" / ".device_auth.json"
ws_ident_file = ROOT / "app" / "data" / ".workspace_identity.json"

security_files_status = {
    ".infinity-ai-authorized": auth_file.exists(),
    ".device_auth.json": device_auth_file.exists(),
    ".workspace_identity.json": ws_ident_file.exists()
}
print(f"Security files status: {security_files_status}")

# 4. Local Models Verification
models_manifest = {}
models_dir = ROOT / "models"
if models_dir.exists():
    for f in models_dir.iterdir():
        if f.is_file():
            models_manifest[f.name] = {"size": f.stat().st_size, "path": str(f)}

ollama_models_dir = ROOT / "ollama-models"
ollama_manifests_found = []
if (ollama_models_dir / "manifests").exists():
    for m in (ollama_models_dir / "manifests").rglob("*"):
        if m.is_file():
            ollama_manifests_found.append(str(m.relative_to(ollama_models_dir / "manifests")))

print(f"Found GGUF models: {list(models_manifest.keys())}")
print(f"Found Ollama models: {ollama_manifests_found}")

# 5. EXECUTE BACKUP COPIES
# A. App directory (excluding large caches)
print("\n[Backing up D:\\PrivateAI\\app...]")
app_backup_dir = BACKUP_DIR / "app"
shutil.copytree(
    ROOT / "app",
    app_backup_dir,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.quarantined*")
)
print(f"Copied app to {app_backup_dir}")

# B. Data directory
print("\n[Backing up D:\\PrivateAI\\data...]")
data_backup_dir = BACKUP_DIR / "data"
if (ROOT / "data").exists():
    shutil.copytree(ROOT / "data", data_backup_dir)
    print(f"Copied data to {data_backup_dir}")

# C. Root files (start-windows.bat, security files, etc.)
print("\n[Backing up root configuration and security files...]")
for fname in ["start-windows.bat", ".infinity-ai-authorized", "safety_checkpoint.py"]:
    fpath = ROOT / fname
    if fpath.exists():
        shutil.copy2(fpath, BACKUP_DIR / fname)

if auth_file.exists():
    shutil.copy2(auth_file, BACKUP_DIR / ".infinity-ai-authorized")
if device_auth_file.exists():
    shutil.copy2(device_auth_file, BACKUP_DIR / ".device_auth.json")
if ws_ident_file.exists():
    shutil.copy2(ws_ident_file, BACKUP_DIR / ".workspace_identity.json")

# D. ChromaDB (app/chroma_db)
print("\n[Backing up ChromaDB...]")
chroma_backup_dir = BACKUP_DIR / "chroma_db"
if (ROOT / "app" / "chroma_db").exists():
    shutil.copytree(ROOT / "app" / "chroma_db", chroma_backup_dir)
    print(f"Copied chroma_db to {chroma_backup_dir}")

# E. Backups metadata log
print("\n[Backing up backups metadata state...]")
existing_backups = [p.name for p in (ROOT / "backups").iterdir() if p.is_dir()]

# F. Models & Ollama manifests & state metadata
print("\n[Recording models and ollama-models metadata...]")
ollama_meta_backup = BACKUP_DIR / "ollama_metadata"
if (ollama_models_dir / "manifests").exists():
    shutil.copytree(ollama_models_dir / "manifests", ollama_meta_backup / "manifests")
if (ollama_models_dir / "metadata").exists():
    shutil.copytree(ollama_models_dir / "metadata", ollama_meta_backup / "metadata")

# Record complete audit manifest
manifest_report = {
    "timestamp": TIMESTAMP,
    "backup_directory": str(BACKUP_DIR),
    "sqlite_integrity_check": integrity_check,
    "projects_count": projects_count,
    "conversations_count": conversations_count,
    "messages_count": messages_count,
    "project_files_count": project_files_count,
    "workspace_metadata": ws_meta,
    "security_files": security_files_status,
    "chroma_info": chroma_info,
    "models": models_manifest,
    "ollama_models": ollama_manifests_found,
    "existing_backups_list": existing_backups
}

manifest_file = BACKUP_DIR / "backup_manifest.json"
with open(manifest_file, "w", encoding="utf-8") as f:
    json.dump(manifest_report, f, indent=2)

print(f"\nManifest successfully written to: {manifest_file}")
print("PHASE 0 BACKUP & VERIFICATION COMPLETE: ALL CHECKS PASSED.")
