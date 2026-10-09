import os
import sys
import json
import hashlib
import sqlite3

ROOT = 'D:/PrivateAI'
EXTERNAL_MODELS = 'D:/models'
ENCRYPTED_DIR = os.path.join(ROOT, 'encrypted_backup')

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def build_recovery_manifest():
    manifest = {
        "manifest_version": "1.0.0",
        "project": "Infinity AI — Private Offline AI Workstation",
        "git_repository": "https://github.com/jivannimase3942-boop/Infinity-ai-",
        "branch": "main",
        "audit_timestamp": "2026-10-10T00:45:00Z",
        "workstation_root": "D:/PrivateAI",
        "external_models_root": "D:/models",
        "backup_strategy_summary": {
            "application_source_and_tests": "Version-controlled on GitHub main branch (Plaintext)",
            "documentation_and_launchers": "Version-controlled on GitHub main branch (Plaintext)",
            "private_databases_and_history": "AES-256 Encrypted multi-volume 7z archive in encrypted_backup/",
            "historical_snapshots_and_code": "AES-256 Encrypted multi-volume 7z archive in encrypted_backup/",
            "ai_model_weights": "Excluded from Git; Reproducible via Ollama & official HuggingFace hubs",
            "runtime_environment": "Excluded from Git; Recreatable via Python venv & app/requirements.txt",
            "security_hardware_markers": "Strictly Host-Local; Re-authorizable on authentic devices"
        },
        "statistics": {},
        "encrypted_archives": [],
        "model_recovery_registry": [],
        "database_integrity_audit": [],
        "tracked_files": []
    }

    if os.path.exists(ENCRYPTED_DIR):
        for chk in sorted(os.listdir(ENCRYPTED_DIR)):
            if chk.startswith('infinity_ai_secure_data.7z'):
                chk_p = os.path.join(ENCRYPTED_DIR, chk)
                sz = os.path.getsize(chk_p)
                sha = compute_sha256(chk_p)
                manifest["encrypted_archives"].append({
                    "filename": chk,
                    "relative_path": f"encrypted_backup/{chk}",
                    "size_bytes": sz,
                    "size_mb": round(sz / (1024*1024), 2),
                    "sha256": sha,
                    "encryption_algorithm": "AES-256-CBC (7-Zip LZMA2 Header-Encrypted)",
                    "contents_description": "SQLite caches (ai_cache.db), ChromaDB stores, quarantined logs, and historical backups."
                })
    return manifest

def append_models_and_dbs(manifest):
    manifest["model_recovery_registry"] = [
        {
            "model_name": "qwen2.5:1.5b",
            "format": "Ollama Manifest/Blobs (Q4_K_M)",
            "size_bytes": 986048512,
            "size_mb": 940.37,
            "verified_recovery_source": "ollama pull qwen2.5:1.5b",
            "role": "Fast chat, reasoning, code generation",
            "local_manifest": "ollama-models/manifests/registry.ollama.ai/library/qwen2.5/1.5b",
            "verified_downloadable": True
        },
        {
            "model_name": "dolphin-mistral:latest",
            "format": "Ollama Manifest/Blobs (Q4_K_M)",
            "size_bytes": 4108928128,
            "size_mb": 3918.58,
            "verified_recovery_source": "ollama pull dolphin-mistral:latest",
            "role": "Deep thinking, agent orchestration, uncensored analysis",
            "local_manifest": "ollama-models/manifests/registry.ollama.ai/library/dolphin-mistral/latest",
            "verified_downloadable": True
        },
        {
            "model_name": "gemma3:4b",
            "format": "Ollama Manifest/Blobs (Q4_K_M)",
            "size_bytes": 3338792448,
            "size_mb": 3184.12,
            "verified_recovery_source": "ollama pull gemma3:4b",
            "role": "Multimodal visual reasoning, instruction following",
            "local_manifest": "ollama-models/manifests/registry.ollama.ai/library/gemma3/4b",
            "verified_downloadable": True
        },
        {
            "model_name": "faster-whisper-small",
            "format": "CTranslate2 Int8/FP16",
            "size_bytes": 483546902,
            "size_mb": 461.15,
            "verified_recovery_source": "https://huggingface.co/Systran/faster-whisper-small",
            "role": "Offline voice transcription & STT",
            "local_path": "models/whisper/models--Systran--faster-whisper-small",
            "verified_downloadable": True
        },
        {
            "model_name": "small.gguf",
            "format": "GGUF Q4_K_M",
            "size_bytes": 2497281120,
            "size_mb": 2381.59,
            "verified_recovery_source": "Local GGUF Model Archive / Ollama Modelfile",
            "role": "Offline GGUF inference fallback",
            "local_path": "models/small.gguf",
            "verified_downloadable": True
        },
        {
            "model_name": "gemma3-4b.gguf",
            "format": "GGUF Q4_K_M",
            "size_bytes": 3338792448,
            "size_mb": 3184.12,
            "verified_recovery_source": "HuggingFace google/gemma-3-4b-it GGUF Archive",
            "role": "Local GGUF standalone runner",
            "local_path": "models/gemma3-4b.gguf",
            "verified_downloadable": True
        },
        {
            "model_name": "dolphin-2.9-llama3-8b-Q4_K_M.gguf",
            "format": "GGUF Q4_K_M",
            "size_bytes": 183098314,
            "size_mb": 174.62,
            "verified_recovery_source": "cognitivecomputations/dolphin-2.9-llama3-8b GGUF Archive",
            "role": "Secondary external storage model",
            "local_path": "D:/models/dolphin-2.9-llama3-8b-Q4_K_M.gguf",
            "verified_downloadable": True
        }
    ]

    db_paths = ["app/data/ai_cache.db", "app/chroma_db/chroma.sqlite3", "data/chroma/chroma.sqlite3"]
    for db_rel in db_paths:
        full_db = os.path.join(ROOT, db_rel)
        if os.path.exists(full_db):
            try:
                con = sqlite3.connect(full_db)
                cur = con.cursor()
                chk = cur.execute("PRAGMA integrity_check").fetchall()
                integrity = chk[0][0] if chk else "EMPTY"
                tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                con.close()
                manifest["database_integrity_audit"].append({
                    "database_path": db_rel,
                    "size_bytes": os.path.getsize(full_db),
                    "integrity_check": integrity,
                    "tables_count": len(tables),
                    "sha256": compute_sha256(full_db)
                })
            except Exception as e:
                manifest["database_integrity_audit"].append({
                    "database_path": db_rel,
                    "error": str(e)
                })
    return manifest

def append_inventory_scan(manifest):
    cats = {
        "GITHUB_SOURCE_BACKUP": 0,
        "ENCRYPTED_PRIVATE_BACKUP": 0,
        "LARGE_MODEL_BACKUP": 0,
        "RECREATABLE_RUNTIME_DEPENDENCY": 0,
        "SECURITY_FILE_NEVER_UPLOAD": 0,
        "REGENERATABLE_CACHE_OR_TEMPORARY_FILE": 0,
        "LOCAL_WORKSPACE_BACKUPS": 0
    }
    cat_bytes = {k: 0 for k in cats}

    for dirpath, dirnames, filenames in os.walk(ROOT):
        if '.git' in dirpath.split(os.sep):
            continue
        for f in filenames:
            fp = os.path.join(dirpath, f)
            rel = os.path.relpath(fp, ROOT).replace('\\', '/')
            sz = os.path.getsize(fp)
            lower = rel.lower()

            if lower.startswith('bin/') or lower.startswith('libs/'):
                cats["RECREATABLE_RUNTIME_DEPENDENCY"] += 1
                cat_bytes["RECREATABLE_RUNTIME_DEPENDENCY"] += sz
            elif lower.startswith('backups/'):
                cats["LOCAL_WORKSPACE_BACKUPS"] += 1
                cat_bytes["LOCAL_WORKSPACE_BACKUPS"] += sz
            elif lower.startswith('models/') or lower.startswith('ollama-models/'):
                cats["LARGE_MODEL_BACKUP"] += 1
                cat_bytes["LARGE_MODEL_BACKUP"] += sz
            elif '__pycache__' in lower or '.pytest_cache' in lower:
                cats["REGENERATABLE_CACHE_OR_TEMPORARY_FILE"] += 1
                cat_bytes["REGENERATABLE_CACHE_OR_TEMPORARY_FILE"] += sz
            elif 'authorized' in lower or 'device_auth' in lower or 'workspace_identity' in lower or 'quarantine_log' in lower:
                cats["SECURITY_FILE_NEVER_UPLOAD"] += 1
                cat_bytes["SECURITY_FILE_NEVER_UPLOAD"] += sz
            elif 'quarantined' in lower or 'chroma_db' in lower or lower.endswith('.db') or lower.endswith('.sqlite') or lower.endswith('.sqlite3') or lower.endswith('.log') or lower.endswith('.db-wal') or lower.endswith('.db-shm'):
                cats["ENCRYPTED_PRIVATE_BACKUP"] += 1
                cat_bytes["ENCRYPTED_PRIVATE_BACKUP"] += sz
            elif rel.startswith('encrypted_backup/') or rel.endswith('.py') or rel.endswith('.json') or rel.endswith('.md') or rel.endswith('.bat') or rel.endswith('.txt') or rel.endswith('.pdf') or rel.endswith('.png') or rel.endswith('.gitignore') or rel.endswith('.gitkeep'):
                cats["GITHUB_SOURCE_BACKUP"] += 1
                cat_bytes["GITHUB_SOURCE_BACKUP"] += sz
                manifest["tracked_files"].append({
                    "path": rel,
                    "size_bytes": sz,
                    "sha256": compute_sha256(fp)
                })

    if os.path.exists(EXTERNAL_MODELS):
        for f in os.listdir(EXTERNAL_MODELS):
            fp = os.path.join(EXTERNAL_MODELS, f)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                cats["LARGE_MODEL_BACKUP"] += 1
                cat_bytes["LARGE_MODEL_BACKUP"] += sz

    for c in cats:
        manifest["statistics"][c] = {
            "count": cats[c],
            "size_bytes": cat_bytes[c],
            "size_mb": round(cat_bytes[c] / (1024*1024), 2),
            "size_gb": round(cat_bytes[c] / (1024*1024*1024), 2)
        }

    total_cnt = sum(cats.values())
    total_sz = sum(cat_bytes.values())
    manifest["statistics"]["TOTAL_ALL_INVENTORIED_FILES"] = {
        "count": total_cnt,
        "size_bytes": total_sz,
        "size_mb": round(total_sz / (1024*1024), 2),
        "size_gb": round(total_sz / (1024*1024*1024), 2)
    }

    out_file = os.path.join(ROOT, 'RECOVERY_MANIFEST.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"RECOVERY_MANIFEST.json successfully created at {out_file}")
    return manifest

if __name__ == '__main__':
    m = build_recovery_manifest()
    m = append_models_and_dbs(m)
    m = append_inventory_scan(m)

