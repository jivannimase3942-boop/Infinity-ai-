"""
Infinity AI - Persistent Database & Storage Manager
Preserves existing SQLite database (ai_cache.db) and provides versioned schema
for conversations, messages, projects, memory, and settings.
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_cache.db"
DB_PATH.parent.mkdir(exist_ok=True, parents=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    """Initializes tables without touching existing tables or data."""
    with get_connection() as conn:
        # 1. Projects
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                system_instructions TEXT,
                model_preference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Default projects if not already seeded
        default_projects = [
            ("default", "General Workspace", "Default workspace for general AI tasks and PDF queries.", "You are Infinity AI, an expert, thoughtful, private, offline-first assistant.", "Balanced"),
            ("study_personal", "Study & Revision", "Dedicated academic preparation, question banks, and flashcards.", "Act as an academic professor. Provide rigorous explanations, quizzes, and viva preparation.", "Fast"),
            ("coding_ws", "Coding & Systems", "Senior software engineering, refactoring, and code review.", "Senior software architect. Propose clean code, unified diffs, and verification steps.", "Coding"),
            ("research_ws", "Research & Evidence", "Grounded academic investigation with evidence citations.", "Research scientist. Strictly ground claims in document evidence, evaluate caveats, and rate confidence.", "Balanced"),
            ("documents_ws", "Document Intelligence", "Deep multi-document analysis, synthesis, and summarization.", "Document specialist. Extract insights, cite pages accurately, and refuse unsupported claims.", "Balanced"),
            ("complaint_mgmt", "AI Complaint Management", "SPPU student complaint classification and resolution system.", "This project is an AI-based complaint management system. Use Python/FastAPI terminology. Prioritize SPPU project requirements.", "Balanced"),
            ("manak_ai", "ManakAI", "Smart compliance, standards, and regulatory intelligence system.", "Expert on BIS, ISO, Indian standards, and technical specifications.", "Advanced"),
            ("disaster_mgmt", "Smart Disaster Management", "Disaster prediction, resource allocation, and emergency response.", "Expert on disaster management, rescue logistics, and meteorological data.", "Advanced"),
        ]
        for pid, pname, pdesc, pinst, ppref in default_projects:
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, description, system_instructions, model_preference) VALUES (?, ?, ?, ?, ?)",
                (pid, pname, pdesc, pinst, ppref)
            )

        # 2. Conversations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                project_id TEXT DEFAULT 'default',
                title TEXT NOT NULL,
                model TEXT,
                mode TEXT,
                pinned INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET DEFAULT
            )
        """)

        # Additive migration: check if pinned/archived exist in conversations
        cur = conn.execute("PRAGMA table_info(conversations)")
        c_cols = [r[1] for r in cur.fetchall()]
        if "pinned" not in c_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER DEFAULT 0")
        if "archived" not in c_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0")

        # Additive migration: check if temperature/context_size exist in projects
        cur_p = conn.execute("PRAGMA table_info(projects)")
        p_cols = [r[1] for r in cur_p.fetchall()]
        if "temperature" not in p_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN temperature REAL DEFAULT 0.7")
        if "context_size" not in p_cols:
            conn.execute("ALTER TABLE projects ADD COLUMN context_size INTEGER DEFAULT 4096")

        # 3. Messages
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                mode TEXT,
                model TEXT,
                citations TEXT,
                token_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        # 4. Project Files & Knowledge
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT,
                doc_id TEXT,
                file_type TEXT,
                size_bytes INTEGER,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)

        # 5. Memory Layers (Short, Project, Long-term)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                project_id TEXT DEFAULT 'default',
                category TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                approved INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Artifacts (Claude-style Documents, Code, Reports, Notes)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                project_id TEXT DEFAULT 'default',
                title TEXT NOT NULL,
                artifact_type TEXT DEFAULT 'document',
                language TEXT DEFAULT 'markdown',
                content TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET DEFAULT
            )
        """)

        # 7. Tool Logs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tools_log (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                parameters TEXT,
                result TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 8. System Settings
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # 9. Workspace Metadata & Device Binding
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_metadata (
                workspace_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                device_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schema_version INTEGER DEFAULT 1
            )
        """)

        # 10. Answer Cache
        conn.execute("""
            CREATE TABLE IF NOT EXISTS answer_cache (
                cache_key TEXT PRIMARY KEY,
                doc_hash TEXT,
                query TEXT,
                mode TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 11. AI Workspace Memory Graph (Requirement 23)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_memory_graph (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                relationship TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 12. Adaptive Preferences (Requirement 24)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                confidence REAL DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 13. Password Authentication Credentials (Local Workspace Only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workspace_password_auth (
                id TEXT PRIMARY KEY,
                version INTEGER DEFAULT 1,
                algorithm TEXT NOT NULL,
                salt TEXT NOT NULL,
                hash TEXT NOT NULL,
                parameters TEXT NOT NULL,
                recovery_hash TEXT,
                recovery_salt TEXT,
                failed_attempts INTEGER DEFAULT 0,
                lockout_until TEXT,
                last_failed_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def verify_and_isolate_database(current_device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Checks if the local SQLite database is bound to the current machine.
    If the database is from another computer (e.g. copied from Laptop A to Laptop B):
    - DOES NOT delete or overwrite the foreign database.
    - Quarantines it safely to ai_cache_quarantined_<foreign_id>_<timestamp>.db.
    - Initializes a fresh, clean local workspace database for this computer.
    - Returns report details.
    """
    from backend.security import get_device_id, get_workspace_id
    dev_id = current_device_id or get_device_id()
    ws_id = get_workspace_id()

    if not DB_PATH.exists():
        init_db()
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workspace_metadata (workspace_id, device_id, device_name) VALUES (?, ?, ?)",
                (ws_id, dev_id, platform.node())
            )
            conn.commit()
        return {"status": "initialized", "workspace_id": ws_id, "device_id": dev_id}

    # Database exists. Inspect workspace_metadata
    foreign_dev_id = None
    conn = get_connection()
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workspace_metadata'")
        has_table = cur.fetchone() is not None

        if not has_table:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_metadata (
                    workspace_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    device_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    schema_version INTEGER DEFAULT 1
                )
            """)
            conn.execute(
                "INSERT INTO workspace_metadata (workspace_id, device_id, device_name) VALUES (?, ?, ?)",
                (ws_id, dev_id, platform.node())
            )
            conn.commit()
            return {"status": "migrated_and_bound", "workspace_id": ws_id, "device_id": dev_id}

        cur = conn.execute("SELECT workspace_id, device_id FROM workspace_metadata LIMIT 1")
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT INTO workspace_metadata (workspace_id, device_id, device_name) VALUES (?, ?, ?)",
                (ws_id, dev_id, platform.node())
            )
            conn.commit()
            return {"status": "bound", "workspace_id": ws_id, "device_id": dev_id}

        foreign_dev_id = row["device_id"]
        if foreign_dev_id == dev_id:
            return {"status": "valid", "workspace_id": row["workspace_id"], "device_id": dev_id}

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()

    # FOREIGN DATABASE DETECTED! (foreign_dev_id != dev_id)
    # Quarantine foreign database safely without deletion
    ts = time.strftime("%Y%m%d_%H%M%S")
    quarantine_name = f"ai_cache_quarantined_{foreign_dev_id[:8]}_{ts}.db"
    quarantine_path = DB_PATH.parent / quarantine_name

    try:
        # Move wal / shm first if they exist
        for ext in ["-wal", "-shm"]:
            sidecar = Path(str(DB_PATH) + ext)
            if sidecar.exists():
                shutil.move(str(sidecar), str(DB_PATH.parent / (quarantine_name + ext)))
        shutil.move(str(DB_PATH), str(quarantine_path))
    except Exception as q_err:
        pass

    # Log quarantine event
    q_log = DB_PATH.parent / ".quarantine_log.json"
    q_entries = []
    if q_log.exists():
        try:
            with open(q_log, "r", encoding="utf-8") as f:
                q_entries = json.load(f)
        except Exception:
            pass
    q_entries.append({
        "timestamp": ts,
        "foreign_device_id": foreign_dev_id,
        "current_device_id": dev_id,
        "quarantined_file": quarantine_name,
        "action": "Quarantined foreign database to preserve privacy and prevent data cross-contamination."
    })
    try:
        with open(q_log, "w", encoding="utf-8") as f:
            json.dump(q_entries, f, indent=2)
    except Exception:
        pass

    # Create fresh local database for this machine
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO workspace_metadata (workspace_id, device_id, device_name) VALUES (?, ?, ?)",
            (ws_id, dev_id, platform.node())
        )
        conn.commit()

    return {
        "status": "quarantined_foreign_workspace",
        "foreign_device_id": foreign_dev_id,
        "current_device_id": dev_id,
        "quarantine_path": str(quarantine_path)
    }


# --- Conversations API ---

def create_conversation(title: str = "New Chat", project_id: str = "default", model: str = "qwen2.5:1.5b", mode: str = "Balanced", cid: Optional[str] = None) -> str:
    cid = cid or str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, project_id, title, model, mode) VALUES (?, ?, ?, ?, ?)",
            (cid, project_id, title, model, mode)
        )
        conn.commit()
    return cid


def get_conversations(project_id: Optional[str] = None, include_empty: bool = False, include_internal: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        filters = []
        if not include_empty:
            filters.append("(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) > 0")
        if not include_internal:
            filters.append("c.title NOT LIKE '# Comprehensive%'")
            filters.append("LOWER(c.title) NOT LIKE '%internal test%'")
            filters.append("LOWER(c.title) NOT LIKE '%developer test%'")
            filters.append("LOWER(c.title) NOT LIKE '%demo chat%'")
            filters.append("LOWER(c.title) NOT LIKE '%validation test%'")
            # If title is default New Chat / Untitled, only include if genuine messages exist
            filters.append("(c.title NOT IN ('New Chat', 'New Conversation', 'Untitled') OR (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.role = 'user') > 0)")
        if project_id:
            filters.append("c.project_id = ?")

        where_clause = (" WHERE " + " AND ".join(filters)) if filters else ""
        query = f"SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count FROM conversations c{where_clause} ORDER BY c.updated_at DESC"
        params = (project_id,) if project_id else ()
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_conversation(cid: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
        return dict(row) if row else None


def update_conversation_title(cid: str, title: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, cid)
        )
        conn.commit()


def delete_conversation(cid: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
        conn.commit()


def rename_conversation(cid: str, title: str):
    update_conversation_title(cid, title)


def pin_conversation(cid: str, pinned: bool = True):
    with get_connection() as conn:
        conn.execute("UPDATE conversations SET pinned = ? WHERE id = ?", (1 if pinned else 0, cid))
        conn.commit()


def archive_conversation(cid: str, archived: bool = True):
    with get_connection() as conn:
        conn.execute("UPDATE conversations SET archived = ? WHERE id = ?", (1 if archived else 0, cid))
        conn.commit()


def search_conversations(query: str, project_id: Optional[str] = None, include_empty: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        sql = """
            SELECT DISTINCT c.id, c.title, c.project_id, c.pinned, c.archived, c.updated_at
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE (c.title LIKE ? OR m.content LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%"]
        if not include_empty:
            sql += " AND (SELECT COUNT(*) FROM messages msg WHERE msg.conversation_id = c.id) > 0"
            sql += " AND c.title NOT LIKE '# Comprehensive%'"
            sql += " AND LOWER(c.title) NOT LIKE '%internal test%'"
        if project_id:
            sql += " AND c.project_id = ?"
            params.append(project_id)
        sql += " ORDER BY c.pinned DESC, c.updated_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_grouped_conversations(project_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups conversations into:
    - Today
    - Yesterday
    - Older
    Automatically supplies friendly title if default.
    """
    convs = get_conversations(project_id)
    today_dt = date.today()
    yesterday_dt = today_dt - timedelta(days=1)

    grouped = {
        "Today": [],
        "Yesterday": [],
        "Older": []
    }

    for c in convs:
        up_str = c.get("updated_at") or c.get("created_at") or ""
        group_key = "Older"
        if up_str:
            try:
                dt_part = up_str.split()[0]
                c_date = datetime.strptime(dt_part, "%Y-%m-%d").date()
                if c_date == today_dt:
                    group_key = "Today"
                elif c_date == yesterday_dt:
                    group_key = "Yesterday"
                else:
                    group_key = "Older"
            except Exception:
                group_key = "Older"

        title = c.get("title", "Conversation")
        if title in ["New Chat", "New Conversation"]:
            try:
                with get_connection() as conn:
                    m_row = conn.execute(
                        "SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY created_at ASC LIMIT 1",
                        (c["id"],)
                    ).fetchone()
                    if m_row and m_row["content"]:
                        title = generate_friendly_title(m_row["content"])
            except Exception:
                pass

        c_clean = dict(c)
        c_clean["title"] = title
        grouped[group_key].append(c_clean)

    return grouped


def search_workspace(query: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Unified workspace search across Chats, Projects, and Documents.
    Returns grouped matches with friendly descriptions.
    """
    q = query.strip()
    if not q:
        return {"chats": [], "projects": [], "documents": []}

    chats = search_conversations(q)
    clean_chats = []
    for c in chats[:10]:
        title = c.get("title", "Conversation")
        clean_chats.append({
            "id": c["id"],
            "title": title,
            "category": "Chat",
            "snippet": f"Updated {c.get('updated_at', '')[:10]}"
        })

    projects = []
    with get_connection() as conn:
        try:
            p_rows = conn.execute(
                "SELECT id, name, description, updated_at FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 10",
                (f"%{q}%", f"%{q}%")
            ).fetchall()
            for p in p_rows:
                projects.append({
                    "id": p["id"],
                    "title": p["name"],
                    "category": "Project",
                    "snippet": p["description"] or "AI workspace project"
                })
        except Exception:
            pass

    documents = []
    with get_connection() as conn:
        try:
            d_rows = conn.execute(
                "SELECT id, filename, file_type, created_at FROM documents WHERE filename LIKE ? LIMIT 10",
                (f"%{q}%",)
            ).fetchall()
            for d in d_rows:
                documents.append({
                    "id": d["id"],
                    "title": d["filename"],
                    "category": "Document",
                    "snippet": f"{d.get('file_type', 'File').upper()} document"
                })
        except Exception:
            pass

    return {
        "chats": clean_chats,
        "projects": projects,
        "documents": documents
    }


def export_conversation(cid: str, fmt: str = "markdown") -> str:
    conv = get_conversation(cid)
    if not conv:
        return ""
    msgs = get_messages(cid)
    if fmt == "json":
        return json.dumps({"conversation": conv, "messages": msgs}, indent=2)
    elif fmt in ["txt", "text"]:
        lines = [f"Title: {conv['title']}", f"Model: {conv.get('model', 'Auto')}", f"Date: {conv['created_at']}", "=" * 50, ""]
        for m in msgs:
            role = "USER" if m["role"] == "user" else "INFINITY AI"
            lines.append(f"[{role}]:\n{m['content']}\n")
        return "\n".join(lines)
    else:  # markdown default
        lines = [f"# {conv['title']}", f"*Exported from Infinity AI on {datetime.now().strftime('%Y-%m-%d %H:%M')}*", "---", ""]
        for m in msgs:
            if m["role"] == "user":
                lines.append(f"### 👤 You\n\n{m['content']}\n")
            else:
                lines.append(f"### ♾️ Infinity AI ({m.get('model', 'Local AI')})\n\n{m['content']}\n")
                if m.get("citations"):
                    lines.append("**Sources & Citations:**")
                    for c in m["citations"]:
                        lines.append(f"- {c.get('document', 'Doc')} (Page {c.get('page', 1)})")
                    lines.append("")
            lines.append("---\n")
        return "\n".join(lines)


def generate_friendly_title(query: str) -> str:
    """Generates a concise, meaningful 1-3 word (max 4 words) human-friendly title from user query."""
    raw = (query or "").strip().replace("\r", " ").replace("\n", " ")
    if not raw:
        return "New Chat"

    low = raw.strip().lower()

    # 1. Greetings - instant clean title
    greetings = {"hi", "hello", "hey", "hola", "namaste", "salut", "sup", "yo"}
    if low in greetings:
        return low.capitalize()

    # 2. Devanagari / Marathi support
    if re.search(r"[\u0900-\u097F]", raw):
        stop_devanagari = {
            "मला", "कृपया", "सांगा", "माहिती", "बद्दल", "द्या", "आहे", "का",
            "पाहिजेत", "पाहिजे", "करा", "नका", "काय", "आहेत", "होते"
        }
        tokens = raw.split()
        cleaned_words = [w for w in tokens if w not in stop_devanagari and w.lower() not in {"important", "questions", "question"}]
        if not cleaned_words:
            cleaned_words = [w for w in tokens if w not in stop_devanagari]
        if not cleaned_words:
            cleaned_words = tokens
        res = " ".join(cleaned_words[:3]).strip()
        return res[:32] if res else "New Chat"

    # 3. Roman Marathi support (e.g. "mala binary search samjav")
    roman_marathi_stops = {"mala", "samjav", "samjava", "mahiti", "sanga", "dya", "pahijet", "pahije", "krupaya", "ka", "aahe", "ahe", "te", "tya", "mag"}
    words_in_raw = raw.split()
    if any(w.lower() in {"mala", "samjav", "samjava", "pahijet", "sanga"} for w in words_in_raw):
        filtered_roman = [w for w in words_in_raw if w.lower() not in roman_marathi_stops]
        if filtered_roman:
            raw = " ".join(filtered_roman)

    # 4. PDF / Document summary shortcuts
    if re.search(r"\b(?:summarise|summarize|summary)\b", raw, re.IGNORECASE) and re.search(r"\bpdf\b", raw, re.IGNORECASE):
        return "PDF Summary"
    if re.search(r"\b(?:summarise|summarize|summary)\b", raw, re.IGNORECASE) and re.search(r"\bdocument\b", raw, re.IGNORECASE):
        return "Document Summary"

    # 5. URL pattern
    url_m = re.search(r"https?://(?:www\.)?([^/\s]+)(?:/([^\s\?#]+))?", raw)
    if url_m:
        domain = url_m.group(1).split(".")[0].capitalize()
        path = url_m.group(2) or ""
        sub = path.split("/")[-1].replace("-", " ").replace("_", " ").title() if path else ""
        return f"{domain}: {sub}"[:32] if sub else f"{domain} Link"

    # 6. Coding preambles ("Write Python code for binary search" -> "Python Binary Search")
    cleaned = raw
    code_match = re.match(
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:help\s+me\s+)?(?:write|generate|create|build|implement|make|code)\s+(?:(?:a|an|the|some)\s+)?(?:([a-zA-Z\+\#]+)\s+)?(?:code|script|program|app|application|system)?\s*(?:for|to|of)?\s*",
        cleaned,
        flags=re.IGNORECASE
    )
    lang_prefix = ""
    if code_match:
        lang = code_match.group(1)
        if lang and lang.lower() not in {"a", "an", "the", "some", "clean", "good", "me", "new", "simple"}:
            lang_prefix = lang.capitalize() + " "
        cleaned = cleaned[code_match.end():]

    # 7. Strip conversational question preambles
    cleaned = re.sub(
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:tell\s+me\s+(?:about)?|explain|describe|what\s+is|what\s+are|how\s+does|how\s+to|how\s+can\s+i(?:\s+build|\s+make|\s+create|\s+do)?|how\s+do\s+i|give\s+me(?:\s+an?)?|show\s+me|summarize|summarise)\s+(?:(?:a|an|the|some)\s+)?",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # 8. Strip trailing conversational filler
    cleaned = re.sub(
        r"(?:\s+with\s+(?:an?\s+)?examples?|\s+in\s+detail|\s+step\s+by\s+step|\s+for\s+beginners|\s+please|\s+and\s+tell\s+me.*|\?)+$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # 9. Clean filler phrases: "smart ... system" -> "Disaster Management"
    cleaned = re.sub(r"^(?:smart\s+)?(.*?)(?:\s+system)?$", r"\1", cleaned, flags=re.IGNORECASE).strip()

    if not cleaned:
        cleaned = raw.strip()

    # Prefer 1-3 words (maximum 4 words)
    words = cleaned.split()
    max_words = 3
    if len(words) > 3 and lang_prefix:
        max_words = 3
    elif len(words) > 4:
        max_words = 3

    chosen_words = words[:max_words]
    title_candidate = (lang_prefix + " ".join(chosen_words)).strip()
    words = title_candidate.split()[:4]

    acronyms = {"ai": "AI", "api": "API", "pdf": "PDF", "sql": "SQL", "cpu": "CPU", "gpu": "GPU", "rag": "RAG", "ui": "UI", "dsa": "DSA", "llm": "LLM", "ml": "ML"}
    titled_words = []
    for w in words:
        lw = w.lower()
        if lw in acronyms:
            titled_words.append(acronyms[lw])
        else:
            titled_words.append(w.capitalize())

    res = " ".join(titled_words).strip()
    return res or "New Chat"


# --- Messages API ---

def add_message(conversation_id: str, role: str, content: str, mode: str = "Balanced", model: str = "", citations: Optional[List[Dict[str, Any]]] = None) -> str:
    mid = str(uuid.uuid4())
    cit_json = json.dumps(citations) if citations else "[]"
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, mode, model, citations) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, conversation_id, role, content, mode, model, cit_json)
        )
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        if role == "user":
            row = conn.execute("SELECT title FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if row and row["title"] in ["New Chat", "New Conversation"]:
                new_title = generate_friendly_title(content)
                if new_title and new_title not in ["New Chat", "New Conversation"]:
                    conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
        conn.commit()
    return mid


def get_messages(conversation_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,)
        ).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            try:
                d["citations"] = json.loads(d["citations"]) if d.get("citations") else []
            except Exception:
                d["citations"] = []
            res.append(d)
        return res


def update_message(mid: str, new_content: str):
    with get_connection() as conn:
        conn.execute("UPDATE messages SET content = ? WHERE id = ?", (new_content, mid))
        conn.commit()


# --- Projects API ---

def get_projects() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


def get_project(pid: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        return dict(row) if row else None


def save_project(pid: str, name: str, description: str, system_instructions: str, model_preference: str = "Balanced"):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO projects (id, name, description, system_instructions, model_preference, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (pid, name, description, system_instructions, model_preference))
        conn.commit()


# --- Memory API ---

def get_memories(project_id: str = "default", category: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM memory_items WHERE (project_id = ? OR project_id = 'global') AND category = ? ORDER BY updated_at DESC",
                (project_id, category)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_items WHERE project_id = ? OR project_id = 'global' ORDER BY updated_at DESC",
                (project_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def save_memory(key: str, value: str, project_id: str = "default", category: str = "user_preference", approved: bool = True) -> str:
    mid = str(uuid.uuid4())
    with get_connection() as conn:
        # Check if key exists
        existing = conn.execute("SELECT id FROM memory_items WHERE project_id = ? AND memory_key = ?", (project_id, key)).fetchone()
        if existing:
            conn.execute(
                "UPDATE memory_items SET memory_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (value, existing[0])
            )
            mid = existing[0]
        else:
            conn.execute(
                "INSERT INTO memory_items (id, project_id, category, memory_key, memory_value, approved) VALUES (?, ?, ?, ?, ?, ?)",
                (mid, project_id, category, key, value, 1 if approved else 0)
            )
        conn.commit()
    return mid


def delete_memory(mid: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM memory_items WHERE id = ?", (mid,))
        conn.commit()


def clear_project_memories(project_id: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM memory_items WHERE project_id = ?", (project_id,))
        conn.commit()


# --- Artifacts API (Claude-style Documents, Code, Reports) ---

def save_artifact(
    title: str,
    content: str,
    artifact_type: str = "document",
    language: str = "markdown",
    conversation_id: Optional[str] = None,
    project_id: str = "default",
    artifact_id: Optional[str] = None
) -> str:
    aid = artifact_id or str(uuid.uuid4())
    with get_connection() as conn:
        existing = conn.execute("SELECT id, version FROM artifacts WHERE id = ?", (aid,)).fetchone()
        if existing:
            new_v = existing["version"] + 1
            conn.execute("""
                UPDATE artifacts SET title = ?, content = ?, artifact_type = ?, language = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, content, artifact_type, language, new_v, aid))
        else:
            conn.execute("""
                INSERT INTO artifacts (id, conversation_id, project_id, title, artifact_type, language, content, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (aid, conversation_id, project_id, title, artifact_type, language, content))
        conn.commit()
    return aid


def get_artifacts(project_id: Optional[str] = None, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        if conversation_id:
            rows = conn.execute("SELECT * FROM artifacts WHERE conversation_id = ? ORDER BY updated_at DESC", (conversation_id,)).fetchall()
        elif project_id:
            rows = conn.execute("SELECT * FROM artifacts WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM artifacts ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_artifact(artifact_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return dict(row) if row else None


def delete_artifact(artifact_id: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
        conn.commit()


# --- Global Local Knowledge Search ---

def search_knowledge_global(query: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Searches across conversations, messages, memories, project files, and artifacts."""
    results = []
    q_pattern = f"%{query}%"
    with get_connection() as conn:
        # 1. Search Messages & Conversations
        sql_m = """
            SELECT m.id, m.content, m.created_at, c.title as doc_title, c.project_id
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.content LIKE ?
        """
        params_m = [q_pattern]
        if project_id:
            sql_m += " AND c.project_id = ?"
            params_m.append(project_id)
        sql_m += " LIMIT 10"
        for r in conn.execute(sql_m, params_m).fetchall():
            results.append({
                "source": "Chat Message",
                "title": r["doc_title"],
                "snippet": r["content"][:200] + "...",
                "project": r["project_id"],
                "date": str(r["created_at"]),
                "relevance": "High"
            })

        # 2. Search Memories
        sql_mem = "SELECT * FROM memory_items WHERE (memory_key LIKE ? OR memory_value LIKE ?)"
        params_mem = [q_pattern, q_pattern]
        if project_id:
            sql_mem += " AND (project_id = ? OR project_id = 'global')"
            params_mem.append(project_id)
        sql_mem += " LIMIT 10"
        for r in conn.execute(sql_mem, params_mem).fetchall():
            results.append({
                "source": "Memory Item",
                "title": f"Key: {r['memory_key']}",
                "snippet": r["memory_value"][:200],
                "project": r["project_id"],
                "date": str(r["updated_at"]),
                "relevance": "Direct"
            })

        # 3. Search Project Files
        sql_f = "SELECT * FROM project_files WHERE file_name LIKE ?"
        params_f = [q_pattern]
        if project_id:
            sql_f += " AND project_id = ?"
            params_f.append(project_id)
        sql_f += " LIMIT 10"
        for r in conn.execute(sql_f, params_f).fetchall():
            results.append({
                "source": "Document / File",
                "title": r["file_name"],
                "snippet": f"Path: {r['file_path']} ({r.get('file_type', 'file')})",
                "project": r["project_id"],
                "date": str(r["indexed_at"]),
                "relevance": "Catalog"
            })

        # 4. Search Artifacts
        sql_a = "SELECT * FROM artifacts WHERE (title LIKE ? OR content LIKE ?)"
        params_a = [q_pattern, q_pattern]
        if project_id:
            sql_a += " AND project_id = ?"
            params_a.append(project_id)
        sql_a += " LIMIT 10"
        for r in conn.execute(sql_a, params_a).fetchall():
            results.append({
                "source": "Artifact",
                "title": r["title"],
                "snippet": r["content"][:200] + "...",
                "project": r["project_id"],
                "date": str(r["updated_at"]),
                "relevance": "Generated"
            })

    return results


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve persistent setting from SQLite system_settings table."""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    """Save persistent setting into SQLite system_settings table."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value))
            )
    except Exception:
        pass


# Initialize database schemas safely
init_db()
