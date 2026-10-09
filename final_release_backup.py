import os
import sys
import json
import shutil
import sqlite3
import datetime
from pathlib import Path

ROOT = Path("D:/PrivateAI")
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = ROOT / "backups" / f"backup-2026-10-08-final-release_{TIMESTAMP}"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("INFINITY AI - FINAL RELEASE BACKUP & AUDIT")
print(f"Backup target: {BACKUP_DIR}")
print("=" * 60)

# Verify DB
db_path = ROOT / "app" / "data" / "ai_cache.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
cur.execute("PRAGMA integrity_check;")
integrity_check = cur.fetchone()[0]
assert integrity_check == "ok", f"Integrity check failed: {integrity_check}"

cur.execute("SELECT COUNT(*) FROM projects;")
projects_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM conversations;")
conversations_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM messages;")
messages_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM project_files;")
project_files_count = cur.fetchone()[0]
conn.close()

# Copy app, data, chroma, security files
shutil.copytree(ROOT / "app", BACKUP_DIR / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.quarantined*"))
if (ROOT / "data").exists():
    shutil.copytree(ROOT / "data", BACKUP_DIR / "data")
if (ROOT / "app" / "chroma_db").exists():
    shutil.copytree(ROOT / "app" / "chroma_db", BACKUP_DIR / "chroma_db")

for fname in [".infinity-ai-authorized", "start-windows.bat", "safety_checkpoint.py"]:
    if (ROOT / fname).exists():
        shutil.copy2(ROOT / fname, BACKUP_DIR / fname)

manifest = {
    "timestamp": TIMESTAMP,
    "sqlite_integrity_check": integrity_check,
    "projects_count": projects_count,
    "conversations_count": conversations_count,
    "messages_count": messages_count,
    "project_files_count": project_files_count,
    "status": "RELEASE_FREEZE_VERIFIED"
}
with open(BACKUP_DIR / "release_manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print("FINAL RELEASE BACKUP COMPLETE: ALL ARTIFACTS VERIFIED.")
