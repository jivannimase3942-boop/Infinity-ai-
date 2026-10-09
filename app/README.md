# Infinity AI — Private Offline AI Workstation

> **"Your AI. Your Files. Your Machine. Offline-First. Privacy-Focused."**

Infinity AI is a production-grade, local, offline-first AI workstation engineered for Windows. It combines a ChatGPT/Claude-style desktop experience with deep local document intelligence, project isolation, safe tool execution, multimodal vision, offline voice, and laptop-level privacy isolation backed by USB key authorization.

---

## 🔒 Critical Privacy Architecture: USB as Security Key

### The Core Principle: USB = KEY, Laptop = DATA STORAGE
**The USB drive is strictly an authorization / security key. It is NOT a portable data storage drive.**

* **What the USB Key Contains**:
  - A cryptographic device authorization marker (`.infinity-ai-authorized`).
  - Zero private chats or conversation history.
  - Zero databases (`*.db`, `*.sqlite`).
  - Zero vector embeddings (`ChromaDB`).
  - Zero project documents, notes, or artifacts.
  - Zero personal files or heavy model weights.
* **What the Host Laptop Contains**:
  - The host laptop's local private database (`app/data/ai_cache.db`).
  - The host laptop's ChromaDB vector store (`app/chroma_db/` or `data/chroma/`).
  - The host laptop's conversations, memories, projects, and generated artifacts.

### Independent Laptop Workspaces (Laptop A vs Laptop B)
Each computer running Infinity AI maintains an independent, isolated workspace:
```
USB Key + Laptop A  =  Laptop A Private Workspace
USB Key + Laptop B  =  Laptop B Private Workspace
USB Key Alone       =  Zero Private Data
```
- **Absolute Privacy Rule**: The same USB key may authorize both Laptop A and Laptop B, but **no private data is ever transferred or synchronized between them**.
- Chats created on Laptop A stay exclusively on Laptop A.
- Laptop B starts with a clean, fresh workspace upon authorization; it will never see Laptop A's chats, memory, or documents.
- Automatic USB data synchronization is strictly forbidden by architectural design.

### Seamless Removal & Reinsertion (Zero Data Loss)
- **When USB is Removed**:
  1. The application immediately detects removal via background device polling.
  2. Active authorization tokens are invalidated and persistent writes are blocked.
  3. The private workspace locks instantly behind a secure lock screen:
     ```
     🔒 Private Workspace Locked
     Authorized USB was removed.
     Your private data remains safe on this computer.
     [ Reconnect USB ]   [ Enter Password ]   [ Read-Only Mode ]
     ```
  4. Local data remains 100% intact on the laptop disk; zero deletion, zero crashing.
- **When USB is Reconnected**:
  1. The workstation detects the authorized key.
  2. The workspace unlocks seamlessly, restoring the active chat and view without data loss.

### New Laptop Setup (Single-Prompt Device Binding)
When an authorized USB is inserted into a new computer for the first time:
1. Infinity AI detects that the current device GUID is not yet registered in the local workspace.
2. A single, clean setup dialog appears:
   ```
   ✨ Infinity AI Authorization
   This USB is authorized.
   This computer does not have an Infinity AI workspace yet.
   [ Authorize Computer ]   [ Read-Only Mode ]
   ```
3. Clicking **[Authorize Computer]** creates a fresh, empty local workspace bound to that laptop.
4. **No Permission Spam**: Once authorized, the user is never asked for permission to send messages, create projects, save memory, or attach files. Only destructive actions (permanent deletion, workspace reset) require a single confirmation.

### Cloned-Database Quarantine & Workspace Isolation
If an entire application directory containing local data is copied from Laptop A to Laptop B:
1. **Device ID Verification**: On startup, Infinity AI compares the host machine's unique `device_id` against the `workspace_metadata` table in `ai_cache.db` and `.chroma_workspace_identity.json` in `chroma_db/`.
2. **Safe Quarantine (Zero Deletion)**: If a foreign device ID is detected, the database is **NEVER** deleted, wiped, or overwritten. Instead, it is safely moved and quarantined:
   - Database: `app/data/ai_cache_quarantined_<foreign_id>_<timestamp>.db`
   - ChromaDB: `app/chroma_db_quarantined_<foreign_id>_<timestamp>/`
3. **Fresh Local Workspace**: A clean, empty local database is initialized for Laptop B with 0 chats, 0 messages, default projects, and 0 documents.
4. **Result**: Laptop A's confidential data is never exposed on Laptop B, while preserving all original data for recovery.

### Physical Drive Deployment Architecture
- **Standard Recommended Deployment**:
  - Install the application and keep local databases on the laptop's internal fixed SSD (`C:\InfinityAI` or any chosen project folder).
  - Use a removable USB flash drive (e.g. `E:\` or `F:\`) containing `.infinity-ai-authorized` as the external physical authorization key.
- **Anti-Self-Authorization Guard**:
  - When running entirely from a removable drive, Infinity AI detects the removable drive type and prevents the hosting drive from self-authorizing without a distinct external key or password verification.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Infinity AI Desktop Workstation                      │
├─────────────────┬──────────────────────────────────────────────────────┤
│ Collapsible Nav │ Top Bar: Workspace | Context | Local Indicator       │
│ [◀/▶ Toggle]    ├──────────────────────────────────────────────────────┤
│ - Chats (Ctrl+N)│ Active Workspace View:                               │
│ - Projects      │  - ChatGPT-Style Conversation & Artifacts View       │
│ - Documents     │  - Dual-Pane Document Intelligence & PDF Viewer      │
│ - Artifacts     │  - Claude-Style Standalone Artifacts Inspector       │
│ - Research      │  - Academic Study & Viva Voce Pedagogy Workspace     │
│ - Study         │  - Senior Coding Assistant with Unified Diffs        │
│ - Code          │  - Tabular Data Analysis Engine (CSV / JSON)         │
│ - Agents        │  - Autonomous Agent Orchestrator & Task Graphs       │
│ - Models        │  - Hardware-Aware Model Manager & Router             │
│ - Diagnostics   │  - 15-Point Live Hardware Health & Diagnostic Matrix │
│ - Settings      ├──────────────────────────────────────────────────────┤
│                 │ Bottom Composer: [Attach 20+] [🎤 Voice] [Send]      │
└─────────────────┴──────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Local AI Processing Core (Air-Gapped)                │
│  - Device & Security Subsystem: Machine GUID Binding & USB Key Audit   │
│  - Hardware-Aware Router: Context & VRAM-aware model switching        │
│  - Agent Pipeline: Planner ➔ Specialized Agent ➔ Tools ➔ Verifier      │
│  - Hybrid RAG Engine: Keyword BM25 + Dense ChromaDB (1,241+ Chunks)    │
│  - Three-Layer Memory: Session, Project, Long-Term User Facts          │
│  - Offline Multimodal Core: Tesseract OCR + Local Vision Fallback      │
│  - Local Voice Engine: Windows SpeechRecognition STT + SAPI TTS       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 💻 Hardware Requirements & Target Machine

Optimized specifically for laptop hardware constraints:
- **Target GPU**: NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM).
- **Target CPU**: 16 Logical Processors (Intel Core i7 / AMD Ryzen).
- **Target RAM**: 16 GB Physical RAM.
- **Operating System**: Windows 10 / 11 (64-bit).
- **Hardware Safeguards**:
  - Real-time VRAM tracking prevents Out-Of-Memory (OOM) driver crashes.
  - VRAM-aware routing automatically falls back to compact models (`qwen2.5:1.5b`) if VRAM headroom is below 1.5 GB.
  - Unloads inactive models from GPU memory during idle periods.
  - Strict context length budgeting (4,096 tokens max prompt context).

---

## 🤖 Local Model Ecosystem & Routing

Infinity AI runs completely offline using local models managed by Ollama and local GGUF runners:
- **Fast / General**: `qwen2.5:1.5b` (Sub-second response time, minimal VRAM footprint).
- **Balanced**: `gemma3:4b` (High-quality conversational synthesis and reasoning).
- **Advanced / Uncensored**: `dolphin-mistral:latest` (Complex problem solving and logic).
- **Vision**: Local Gemma multimodal vision integration with automatic OCR fallback.
- **Coding**: Code-specialized local GGUF / Ollama models.

### Intelligent Model Router
Automatically analyzes user prompt intent across 11 categories:
1. `Vision`: Selected when images, diagrams, or screenshots are attached.
2. `Coding`: Selected for code generation, bug fixing, refactoring, and diff generation.
3. `Data Analysis`: Selected for datasets, CSV, statistics, and tabular structures.
4. `Study`: Selected for concept explanations, exam prep, quizzes, and flashcards.
5. `Research`: Selected for academic inquiry, hypothesis validation, and citations.
6. `Reasoning`: Selected for multi-step logic, math, and architectural evaluation.
7. `Summarization`: Selected for condensing lengthy reports and multi-page PDFs.
8. `Translation`: Selected for multilingual conversions.
9. `Writing`: Selected for drafting essays, emails, documentation, and outlines.
10. `Document QA`: Selected for single-document and multi-document inquiries.
11. `General`: Default conversational assistant.

*Advanced users can manually override automatic routing at any time in the Top Bar.*

---

## 🚀 Core Features & Workspaces

### 1. ChatGPT-Style Chat Experience
- **Conversation Management**: Create new chats (`Ctrl+N`), rename threads, pin favorite conversations, archive historical discussions, full-text history search, and delete conversations.
- **Message Editing & Regeneration**: Edit previous user messages, regenerate responses, stop active token generation (`Esc`), and continue interrupted responses.
- **Rich Rendering**: GitHub-flavored Markdown, syntax-highlighted code blocks with one-click copy, collapsible sections, and interactive citation cards.
- **Exporting**: Export entire conversation transcripts to Markdown (`.md`), JSON (`.json`), or Plain Text (`.txt`).

### 2. Isolated Claude-Style Projects
Maintain strict context boundaries across 8 pre-configured domains:
- `General Workspace`: Everyday queries and general assistance.
- `Academic Study & Revision`: Syllabus analysis, concept breakdown, and exam revision.
- `Coding & Software Engineering`: Codebase analysis, bug fixing, and unified diff proposals.
- `Deep Research`: Methodological research with evidence grounding and confidence scores.
- `Document Intelligence`: Cross-document QA, comparison, and verification.
- `AI Complaint Management`: Institutional grievance tracking and resolution workflows.
- `ManakAI`: Standards compliance, regulatory frameworks, and audit inspection.
- `Smart Disaster Management`: Emergency response protocols and risk assessment.

### 3. Three-Layer Persistent Memory Subsystem
- **Layer 1: Session Memory**: Ephemeral context maintained throughout the active conversation.
- **Layer 2: Project Memory**: Persistent project-specific facts and preferences.
- **Layer 3: Long-Term User Memory**: User-approved personal preferences and domain facts.
- **Full Transparency**: View, edit, forget, or clear memory directly from the Memory Workspace. Memory remains strictly local to the laptop and is never copied to the USB key.

### 4. Universal Document Intelligence & Hybrid RAG
- **Supported Formats (20+)**: `PDF`, `DOCX`, `PPTX`, `XLSX`, `CSV`, `TXT`, `MD`, `JSON`, `PY`, `JS`, `TS`, `HTML`, `CSS`, `JAVA`, `CPP`, `C`, `SQL`, `LOG`, `YAML`, `XML`, and image formats (`PNG`, `JPG`, `WEBP`).
- **Drag and Drop**: Drop a supported document anywhere in the workspace to index it. Drop one file onto the chat panel to attach it to your next message; multiple workspace files are processed one at a time.
- **Hybrid Retrieval**: Combines keyword retrieval with dense vector similarity via ChromaDB (1,241+ pre-indexed chunks across 6 documents).
- **Grounded Citations**: Responses cite exact document names and page numbers.
- **Honest Uncertainty Policy**: When evidence is missing from attached documents, the assistant explicitly states: *"I couldn't find supporting evidence in the provided documents"* rather than hallucinating facts.

### 5. Multimodal Vision & Local OCR
- Analyzes screenshots, error dialogs, system diagrams, and UI wireframes locally.
- Integrated Tesseract OCR fallback extracts text from scanned or un-selectable PDF pages.

### 6. Offline Voice Assistant
- **Local Speech-to-Text (STT)**: Windows Speech Recognition integration with push-to-talk.
- **Local Text-to-Speech (TTS)**: Offline Windows SAPI SpeechSynthesizer.
- **Controls**: Push-to-talk button (`Ctrl+Shift+V`), stop speaking button, and speech queue instant purge (`Esc`).

### 7. Senior Coding Assistant with Unified Diffs
- Provides code explanations, bug root-cause analysis, and refactoring proposals.
- Generates standard unified diff patches (`---` / `+++`) without silently overwriting source code files on disk.

### 8. Academic Study & Engineering Pedagogy Mode
- **Concept Simplification**: First-principles breakdown using real-world analogies.
- **Rigorous Examination Quizzes**: Generates 5 multi-choice questions with answer keys and distractor explanations.
- **Active Recall Flashcards**: Question-and-answer pairs optimized for memory retention.
- **Viva Voce Prep**: High-yield oral examination questions with scoring tips and counter-questions.

### 9. Tabular Data Analysis Engine
- Locally inspects `CSV`, `TSV`, and `JSON` files.
- Computes column types, missing value percentages, distributions (min/max/mean), and categorical value frequencies.
- Produces clean Markdown tables and summary cards without executing untrusted shell scripts.

### 10. Autonomous Agent Orchestrator & Safe Tool System
- **7 Personas**: General, Researcher, Coder, Analyst, Tutor, Writer, Auditor.
- **Task Graph Execution**: Decomposes complex user instructions into discrete tasks (`Planning` ➔ `Reading` ➔ `Analyzing` ➔ `Executing` ➔ `Verifying` ➔ `Complete`).
- **9 Sandboxed Local Tools**:
  - `calculator`: Python AST mathematical evaluation.
  - `file_reader`: Non-destructive text inspection.
  - `document_search`: Hybrid RAG vector retrieval.
  - `code_analyzer`: Syntax tree analysis.
  - `data_analyzer`: Tabular statistics computation.
  - `date_time`: Local system clock and calendar.
  - `system_diagnostics`: Real hardware and engine telemetry.
  - `knowledge_search`: Global cross-entity workstation search.
  - `python_runner`: Local controlled script execution.

---

## ⚙️ Feature Verification Matrix

| Subsystem / Feature | Implementation Status | Runtime Dependencies |
| :--- | :---: | :--- |
| **CustomTkinter GUI Workstation** | ✅ Verified | Python 3.10+ & `customtkinter` |
| **USB Key Hardware Authorization** | ✅ Verified | Any USB Flash Drive |
| **Password Auth & Lock Overlay** | ✅ Verified | Local SHA-256 / PBKDF2 hash |
| **Workspace & Database Quarantine** | ✅ Verified | Built-in SQLite & Device GUID |
| **Multi-Turn Chat & Artifacts** | ✅ Verified | Local LLM / Ollama |
| **RAG & Hybrid Vector Search** | ✅ Verified | ChromaDB & Embedding engine |
| **Multi-Format Document Parsing** | ✅ Verified | PyMuPDF, python-docx, openpyxl |
| **Autonomous Task Agents & 9 Tools** | ✅ Verified | Internal Python sandboxed tools |
| **Deep Research & Self-Critique** | ✅ Verified | Internal iterative refinement engine |
| **Local Model Dynamic Router** | ✅ Verified | Ollama API endpoint (`127.0.0.1:11435` or `:11434`) |
| **Multimodal Vision** | ⚡ Optional / Hardware-Aware | Vision model (`llama3.2-vision` / `llava`) |
| **Tesseract OCR Ingestion** | ⚡ Optional / External Binary | [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Offline Voice STT (Whisper)** | ⚡ Optional / Hardware-Aware | `faster-whisper` & audio input device |
| **Offline Voice TTS (SAPI)** | ✅ Verified | Windows SAPI (built-in Windows speech) |

---

## ⌨️ Universal Keyboard Shortcuts & Command Palette

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + N` | New Chat (Clears temporary state safely) |
| `Ctrl + K` / `Ctrl + Shift + P` | Open Command Palette (Fuzzy search all 12 views) |
| `Ctrl + O` | Open Document / Attach File |
| `Ctrl + L` | Focus Message Composer |
| `Ctrl + Shift + V` | Toggle Voice Assistant |
| `Ctrl + Shift + L` | Manually Lock Private Workspace |
| `Ctrl + Enter` | Send Message |
| `Esc` | Stop Active Generation / Purge Speech Queue |

---

## 🚦 15-Point System Diagnostics Matrix

Access live telemetry anytime in the Diagnostics Workspace:
1. **Python Environment**: Active runtime path and version.
2. **Ollama Server**: Loopback daemon connection status (`127.0.0.1:11435` or `127.0.0.1:11434`).
3. **Local Models**: Inventory of installed Ollama models and local GGUFs.
4. **GPU Acceleration**: CUDA / DirectML GPU compute availability.
5. **VRAM Capacity & Usage**: Real-time dedicated VRAM allocation tracking.
6. **System RAM**: Physical RAM usage and available headroom.
7. **CPU**: Logical core count and CPU utilization percentage.
8. **SQLite Database**: Schema integrity verification (`PRAGMA integrity_check`).
9. **ChromaDB Vector Store**: Vector collection count and chunk indexing status.
10. **Tesseract OCR**: Local OCR binary path verification.
11. **Vision Engine**: Multimodal model availability.
12. **Local STT**: Speech recognition engine status.
13. **Local TTS**: Windows SAPI speech synthesis status.
14. **USB Key Authorization**: Removable drive authorization check.
15. **Storage Capacity**: Free disk space on host workstation drives.

---

## 🚀 Quickstart & Installation Guide (Windows)

### 1. Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10, 3.11, or 3.12 ([python.org](https://www.python.org/downloads/)) — Ensure **"Add Python to PATH"** is checked during installation.
- **Ollama**: [Download Ollama for Windows](https://ollama.com/download)
- *(Optional)* **Tesseract OCR**: [Tesseract installer for Windows](https://github.com/UB-Mannheim/tesseract/wiki) (for scanned image OCR)

### 2. Clone the Repository
```cmd
git clone https://github.com/jivannimase3942-boop/Infinity-ai-.git
cd Infinity-ai-
```

### 3. Setup Python Virtual Environment
```cmd
:: Create virtual environment
python -m venv .venv

:: Activate virtual environment
call .venv\Scripts\activate

:: Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r app/requirements.txt
```

### 4. Setup Local AI Models (No Weights in Git)
Infinity AI connects to your local Ollama daemon. Large model binaries are never stored in the repository.

1. Start the Ollama server:
   ```cmd
   ollama serve
   ```
2. In a separate command prompt, pull your preferred models:
   ```cmd
   :: Recommended fast text model (7B)
   ollama pull qwen2.5:7b

   :: Recommended lightweight multimodal vision model
   ollama pull llama3.2-vision

   :: Recommended compact model for low-spec machines
   ollama pull qwen2.5:3b
   ```
3. *(Optional)* If using standalone GGUF model files, place them in the `models/` directory.

### 5. Setup USB Security Key
1. Insert any USB flash drive into your computer (e.g. drive `E:`).
2. Create an empty authorization key file in the root directory of the USB drive:
   ```cmd
   type nul > E:\.infinity-ai-authorized
   ```
*(Note: If you launch without a USB drive, Infinity AI allows you to set a local workspace password as a fallback).*

### 6. Launch Infinity AI
```cmd
:: Make sure the virtual environment is activated
call .venv\Scripts\activate

:: Launch the workstation
cd app
python app.py
```
*Alternatively, double-click `app/run.bat`.*

---

## 💾 Backup, Recovery & Troubleshooting

### Local Private Data Locations
Your private data is stored exclusively on your host machine inside the application memory structure:
- **SQLite Database**: `app/data/ai_cache.db`
- **Vector Embeddings**: `app/chroma_db/` or `data/chroma/`
- **Workspace Auth Tokens**: `app/data/.workspace_identity.json`

### Creating a Manual Backup
To back up your private conversations and indexed documents safely:
```cmd
:: From the project root, copy the data folder to your backup location
mkdir C:\InfinityAI_Backups\backup_YYYYMMDD
xcopy /E /I /H app\data C:\InfinityAI_Backups\backup_YYYYMMDD\data
xcopy /E /I /H app\chroma_db C:\InfinityAI_Backups\backup_YYYYMMDD\chroma_db
```

### Restoring from Backup
1. Close Infinity AI.
2. Copy the backed-up `ai_cache.db` back into `app/data/ai_cache.db`.
3. Verify database integrity:
   ```cmd
   python -c "import sqlite3; con=sqlite3.connect('app/data/ai_cache.db'); print('DB Status:', con.execute('PRAGMA integrity_check').fetchall())"
   ```
4. Restart Infinity AI.

### Common Troubleshooting
- **Ollama Not Responding**: Ensure the Ollama daemon is running with `ollama serve`. If using a custom port (e.g., `11435`), set `set OLLAMA_HOST=127.0.0.1:11435`.
- **Workspace Locked Unexpectedly**: Ensure your authorized USB key is plugged in with `.infinity-ai-authorized` present, or unlock using your configured master password.
- **Microphone Unavailable**: Verify Windows Microphone permissions under `Settings > Privacy & Security > Microphone`. Infinity AI cleanly falls back to text mode if audio devices are unavailable.

---

## 🧪 Automated Verification & Testing

Infinity AI includes comprehensive automated test suites covering all core subsystems, security boundaries, and user workflows.

To run the test suites, open a terminal at the repository root, activate your virtual environment, and execute:

```cmd
:: Activate virtual environment
call .venv\Scripts\activate

:: 1. Master Production Verification Suite (50 validation criteria)
python app/test_master_production_suite.py

:: 2. Customer Acceptance Suite (End-to-end user workflows)
python app/test_final_customer_acceptance.py

:: 3. Capability & Regression Suite (32 subsystem capabilities)
python app/test_upgrade_suite.py

:: 4. Autonomous Task Agent & Tools Suite
python app/test_upgrade_tasks_suite.py

:: 5. Password Security & Workspace Lock Suite
python app/test_password_security.py

:: 6. Reliability & Edge Case Suite
python app/test_reliability_suite.py

:: 7. Startup Flow & Quarantine Isolation Suite
python app/test_startup_flow.py

:: 8. Dynamic Recommendations Engine Suite
python app/test_recommendations.py

:: 9. GUI Integration & Headless Mock Suite
python app/test_gui_integration.py

:: 10. UI Theme & Visual Polish Suite
python app/test_final_polish_suite.py
```

---

## 🛡️ Privacy & Data Preservation Principles
- **Non-Destructive Design**: Workstation operations are architected to prevent accidental overwriting or deletion of user documents, conversations, and model weights.
- **Preserved Migration History**: Database schema migrations are structured to non-destructively preserve historical SQLite records and cached answers.
- **Persistent Local Embeddings**: ChromaDB vector collections remain strictly stored on local disk across sessions.
- **Air-Gapped Operation**: Designed for offline execution with zero telemetry or required cloud dependencies.
