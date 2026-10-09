# Infinity AI — Disaster Recovery & System Restoration Manual

This manual provides the step-by-step procedure to reconstruct the **Infinity AI Private Offline Workstation** on any Windows 10/11 machine from scratch using the GitHub repository, official model hubs, and encrypted data backups.

---

## 1. System Architecture & Backup Overview

Infinity AI uses a multi-tier disaster recovery architecture separating deterministic code, reproducible model weights, recreatable runtime environments, and encrypted sensitive state:

| Component | Recovery Strategy | Storage Destination |
| :--- | :--- | :--- |
| **Application Source & Tests** | Tracked in Git | GitHub (`origin/main`) |
| **Assets & Launchers** | Tracked in Git | GitHub (`origin/main`) |
| **Private Data & Embeddings** | AES-256 Encrypted Archive | `encrypted_backup/infinity_ai_secure_data.7z.*` |
| **Historical Snapshots** | AES-256 Encrypted Archive | `encrypted_backup/infinity_ai_secure_data.7z.*` |
| **AI Model Weights (13.91 GB)** | Upstream Model Registries | Ollama Registry & HuggingFace Hub |
| **Python Runtime & Libraries** | Virtual Environment | PyPI via `app/requirements.txt` |
| **USB Security Markers** | Host-Local Device Marker | Generated on authentic USB Flash Drive |

---

## 2. Model Re-Acquisition Registry

The following models must be pulled or downloaded to restore full offline inference capabilities:

### Primary Ollama Models
```cmd
# 1. Primary fast chat & reasoning engine (940 MB)
ollama pull qwen2.5:1.5b

# 2. Deep thinking, uncensored analysis & complex coding agent (3.92 GB)
ollama pull dolphin-mistral:latest

# 3. Multimodal vision and instruction following (3.18 GB)
ollama pull gemma3:4b
```

### Voice Transcription & GGUF Models
- **Offline Voice STT (Faster-Whisper)**: Automatically cached on first voice input or manually downloaded from `https://huggingface.co/Systran/faster-whisper-small` to `models/whisper/`.
- **Standalone GGUF Weights**: Place optional GGUF weights into `models/small.gguf` or `models/gemma3-4b.gguf` for direct C++ inference fallbacks.


---

## 3. Clean Machine Restoration Runbook (10 Steps)

Follow these steps to restore a fully functional Infinity AI workstation on a new Windows computer:

### Step 1: Clone Repository from GitHub
```cmd
git clone https://github.com/jivannimase3942-boop/Infinity-ai-.git D:\PrivateAI
cd D:\PrivateAI
```

### Step 2: Create and Activate Python Virtual Environment
```cmd
python -m venv .venv
call .venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```cmd
python -m pip install --upgrade pip
pip install -r app\requirements.txt
```

### Step 4: Install and Start Ollama
1. Download Ollama for Windows from [https://ollama.com](https://ollama.com).
2. Start the Ollama background service:
   ```cmd
   ollama serve
   ```

### Step 5: Pull Required AI Models
```cmd
ollama pull qwen2.5:1.5b
ollama pull dolphin-mistral:latest
ollama pull gemma3:4b
```

### Step 6: Decrypt and Restore Private Data & Embeddings
If you have encrypted workspace data (`encrypted_backup/infinity_ai_secure_data.7z.001`):
```cmd
"C:\Program Files\7-Zip\7z.exe" x encrypted_backup\infinity_ai_secure_data.7z.001 -oD:\PrivateAI\ -p"<YOUR_OFFLINE_PASSPHRASE>" -y
```
*(If starting clean without prior user history, the application will initialize empty databases automatically on first boot).*

### Step 7: Authorize USB Hardware Key
1. Insert any dedicated USB flash drive (e.g., Drive `E:\` or `F:\`).
2. Generate the authorization key file on the root of the USB drive:
   ```cmd
   type nul > E:\.infinity-ai-authorized
   ```

### Step 8: Verify SQLite Database Integrity
```cmd
python -c "import sqlite3; con=sqlite3.connect('app/data/ai_cache.db'); print('Integrity:', con.execute('PRAGMA integrity_check').fetchall())"
```
*Expected Output: `Integrity: [('ok',)]`.*

### Step 9: Run Automated Verification Tests
```cmd
python app\test_upgrade_tasks_suite.py
python app\test_upgrade_suite.py
```
*Verify that all tests pass cleanly.*

### Step 10: Launch Infinity AI Workstation
```cmd
cd app
python app.py
```
*Alternatively, double click `start-windows.bat` or `app\run.bat`.*
