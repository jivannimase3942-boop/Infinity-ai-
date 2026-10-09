"""
Infinity AI - Adaptive Intelligence & Local Preference Engine
Learns useful workflow preferences locally:
- response style (concise vs detailed)
- preferred programming language (Python, TypeScript, etc.)
- answer depth (rigorous, summary, beginner-friendly)
- study format (SPPU exam style with Definition, Explanation, Example, Diagram, Conclusion)
- coding style (clean typing, unit tests, diffs)
- recurring task patterns
100% Local. Transparent. Editable. User can reset preferences anytime.
Never infers sensitive personal data. Never sends preferences to the cloud.
"""

import sqlite3
import re
from typing import Dict, Any, List, Optional
from backend.db import get_connection

DEFAULT_PREFERENCES = {
    "response_style": "balanced",
    "preferred_language": "python",
    "answer_depth": "detailed",
    "study_format": "standard",
    "coding_style": "typed_modular",
    "citation_style": "page_numbered"
}

class AdaptivePreferenceEngine:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS adaptive_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_all_preferences(self) -> Dict[str, str]:
        prefs = dict(DEFAULT_PREFERENCES)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM adaptive_preferences")
            for row in cur.fetchall():
                prefs[row[0]] = row[1]
        return prefs

    def get_preference(self, key: str, default: Optional[str] = None) -> str:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM adaptive_preferences WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                return row[0]
        return default or DEFAULT_PREFERENCES.get(key, "")

    def set_preference(self, key: str, value: str, category: str = "general", confidence: float = 1.0):
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO adaptive_preferences (key, value, category, confidence, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, value, category, confidence))
            conn.commit()

    def reset_preferences(self):
        """Clears all learned preferences back to defaults."""
        with get_connection() as conn:
            conn.execute("DELETE FROM adaptive_preferences")
            conn.commit()

    def observe_user_interaction(self, query: str):
        """
        Observes user query patterns to safely adapt style preferences locally.
        Transparent & deterministic rule detection.
        """
        q_lower = query.lower()

        # 1. Study format preference: SPPU exam style
        if any(w in q_lower for w in ["sppu style", "sppu exam", "sppu format", "university exam style"]):
            self.set_preference("study_format", "sppu_exam", category="study")

        # 2. Preferred programming language
        if "in python" in q_lower or "using python" in q_lower:
            self.set_preference("preferred_language", "python", category="coding")
        elif "in typescript" in q_lower or "in ts" in q_lower:
            self.set_preference("preferred_language", "typescript", category="coding")
        elif "in rust" in q_lower:
            self.set_preference("preferred_language", "rust", category="coding")
        elif "in java" in q_lower:
            self.set_preference("preferred_language", "java", category="coding")
        elif "in c++" in q_lower or "in cpp" in q_lower:
            self.set_preference("preferred_language", "cpp", category="coding")

        # 3. Response depth / style
        if any(w in q_lower for w in ["keep it brief", "briefly", "short summary", "tldr"]):
            self.set_preference("response_style", "concise", category="style")
        elif any(w in q_lower for w in ["in detail", "elaborate", "comprehensive", "deep dive"]):
            self.set_preference("response_style", "in_depth", category="style")

    def build_preference_system_instruction(self, intent_type: str = "general") -> str:
        """Injects learned preference rules into generation prompts."""
        prefs = self.get_all_preferences()
        instructions = []

        if prefs.get("study_format") == "sppu_exam" and intent_type in ["study", "academic", "exam"]:
            instructions.append(
                "ADAPTIVE PREFERENCE (Academic Format):\n"
                "Format academic and exam answers following SPPU standards:\n"
                "1. Definition\n"
                "2. Detailed Explanation\n"
                "3. Real-world / Technical Example\n"
                "4. ASCII / Conceptual Diagram representation where applicable\n"
                "5. Conclusion / Summary"
            )

        if prefs.get("response_style") == "concise":
            instructions.append("ADAPTIVE PREFERENCE: Keep explanations direct, concise, and focused.")
        elif prefs.get("response_style") == "in_depth":
            instructions.append("ADAPTIVE PREFERENCE: Provide comprehensive, detailed explanations with depth.")

        if intent_type == "coding" and prefs.get("preferred_language"):
            instructions.append(f"ADAPTIVE PREFERENCE: Default code examples to {prefs.get('preferred_language').title()} unless requested otherwise.")

        return "\n\n".join(instructions)

# Global instance
adaptive_preference_engine = AdaptivePreferenceEngine()
