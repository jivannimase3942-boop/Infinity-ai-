import os
import sys
import json
import sqlite3
from pathlib import Path

ROOT = Path("D:/PrivateAI")
DB_PATH = ROOT / "app" / "data" / "ai_cache.db"
CHROMA_DIR = ROOT / "app" / "chroma_db"
MODELS_DIR = ROOT / "ollama-models"
BACKUPS_DIR = ROOT / "backups"

print("=" * 60)
print("INFINITY AI - SAFETY CHECKPOINT AUDIT")
print("=" * 60)

# 1. DB Verification
print(f"Database path: {DB_PATH}")
assert DB_PATH.exists(), f"Database not found at {DB_PATH}"

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# PRAGMA integrity_check
cur.execute("PRAGMA integrity_check;")
integrity_result = [r[0] for r in cur.fetchall()]
print(f"SQLite PRAGMA integrity_check: {integrity_result}")

# Tables and counts
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = sorted([r[0] for r in cur.fetchall()])
print(f"Database tables found ({len(tables)}): {tables}")

counts = {}
for tbl in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        counts[tbl] = cur.fetchone()[0]
    except Exception as e:
        counts[tbl] = f"Error: {e}"

print("Table row counts:")
for k, v in counts.items():
    print(f"  - {k}: {v}")

# Workspace metadata
print("\nWorkspace Metadata:")
try:
    cur.execute("SELECT * FROM workspace_metadata;")
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        print(f"  {r}")
except Exception as e:
    print(f"  Error reading workspace_metadata: {e}")

conn.close()

# 2. ChromaDB verification
print(f"\nChromaDB path: {CHROMA_DIR}")
print(f"ChromaDB exists: {CHROMA_DIR.exists()}")
if CHROMA_DIR.exists():
    chroma_files = list(CHROMA_DIR.glob("*"))
    print(f"ChromaDB items count: {len(chroma_files)}")

# 3. Installed Models
print(f"\nOllama models path: {MODELS_DIR}")
manifests_dir = MODELS_DIR / "manifests"
if manifests_dir.exists():
    manifest_files = [str(p.relative_to(manifests_dir)) for p in manifests_dir.rglob("*") if p.is_file()]
    print(f"Found {len(manifest_files)} installed model manifests: {manifest_files}")

# 4. USB security files
auth_file = ROOT / ".infinity-ai-authorized"
device_auth_file = ROOT / "app" / "data" / ".device_auth.json"
ws_ident_file = ROOT / "app" / "data" / ".workspace_identity.json"

print("\nSecurity files:")
print(f"  .infinity-ai-authorized: {auth_file.exists()} (size: {auth_file.stat().st_size if auth_file.exists() else 0} bytes)")
print(f"  .device_auth.json: {device_auth_file.exists()}")
print(f"  .workspace_identity.json: {ws_ident_file.exists()}")

if ws_ident_file.exists():
    with open(ws_ident_file, "r") as f:
        print(f"  Workspace identity content: {f.read().strip()}")

# 5. Backups verification
print(f"\nExisting backups in {BACKUPS_DIR}:")
if BACKUPS_DIR.exists():
    backups = [p.name for p in BACKUPS_DIR.iterdir() if p.is_dir()]
    print(f"  Found {len(backups)} backups: {backups}")

print("=" * 60)
